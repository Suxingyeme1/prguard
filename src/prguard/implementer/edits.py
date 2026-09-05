"""Deterministic application of model-submitted structured text edits."""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import shutil
from pathlib import Path

from prguard.harness.git import GitRepository, final_diff
from prguard.implementer.errors import (
    EditConflictError,
    PatchPolicyError,
    RepositoryAccessError,
)
from prguard.implementer.tools import (
    _is_probably_binary,
    _safe_relative,
    validate_proposed_patch,
)
from prguard.schemas import (
    CreateFileEdit,
    FixTask,
    ImplementerProposal,
    ReplaceLinesEdit,
    ReplacePythonSymbolEdit,
    ReplaceTextEdit,
    TextEdit,
)


def _validated_edit_path(root: Path, task: FixTask, value: str) -> tuple[str, Path]:
    try:
        relative = _safe_relative(value).as_posix()
    except RepositoryAccessError as exc:
        raise PatchPolicyError(str(exc)) from exc
    if any(fnmatch.fnmatchcase(relative, pattern) for pattern in task.protected_paths):
        raise PatchPolicyError(f"structured edit modifies protected path: {relative}")
    if not any(fnmatch.fnmatchcase(relative, pattern) for pattern in task.writable_paths):
        raise PatchPolicyError(f"structured edit is outside writable scope: {relative}")
    candidate = root / relative
    try:
        candidate.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise PatchPolicyError("structured edit resolves outside the worktree") from exc
    return relative, candidate


def _read_editable_text(path: Path, task: FixTask) -> str:
    if path.is_symlink() or not path.is_file():
        raise PatchPolicyError("replace_text path must be a regular existing file")
    if path.stat().st_size > task.max_file_bytes:
        raise PatchPolicyError("replace_text file exceeds the configured file limit")
    data = path.read_bytes()
    if _is_probably_binary(data):
        raise PatchPolicyError("structured edits support UTF-8 text files only")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PatchPolicyError("structured edits support UTF-8 text files only") from exc


def _write_bounded_text(path: Path, content: str, task: FixTask) -> None:
    payload = content.encode("utf-8")
    if len(payload) > task.max_file_bytes:
        raise PatchPolicyError("structured edit output exceeds the configured file limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(content)


def _line_segment(content: str, start_line: int, end_line: int) -> tuple[str, str, str]:
    lines = content.splitlines(keepends=True)
    if start_line > len(lines) or end_line > len(lines):
        raise EditConflictError(
            f"line edit range {start_line}-{end_line} exceeds {len(lines)} source lines"
        )
    start = start_line - 1
    return "".join(lines[:start]), "".join(lines[start:end_line]), "".join(lines[end_line:])


def _verify_segment_hash(segment: str, expected: str, *, description: str) -> None:
    actual = hashlib.sha256(segment.encode("utf-8")).hexdigest()
    if actual != expected:
        raise EditConflictError(
            f"{description} content hash changed; read the current source before editing"
        )


class _DefinitionRanges(ast.NodeVisitor):
    def __init__(self) -> None:
        self.parents: list[str] = []
        self.ranges: list[tuple[str, int, int]] = []

    def _visit_definition(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        qualified = ".".join([*self.parents, node.name])
        self.ranges.append((qualified, node.lineno, node.end_lineno or node.lineno))
        self.parents.append(node.name)
        self.generic_visit(node)
        self.parents.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_definition(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_definition(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_definition(node)


def _module_name(path: str) -> str:
    parts = list(Path(path).with_suffix("").parts)
    if parts and parts[0] in {"src", "lib", "test", "tests"}:
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _python_symbol_range(content: str, path: str, symbol: str) -> tuple[int, int]:
    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError as exc:
        raise EditConflictError(
            f"cannot edit symbols in invalid Python source: {path}"
        ) from exc
    visitor = _DefinitionRanges()
    visitor.visit(tree)
    module = _module_name(path)
    matches = [
        (start_line, end_line)
        for name, start_line, end_line in visitor.ranges
        if symbol == name or (module and symbol == f"{module}.{name}")
    ]
    if len(matches) != 1:
        raise EditConflictError(
            f"replace_python_symbol requires one exact symbol in {path}; found {len(matches)}"
        )
    return matches[0]


def apply_structured_edits(worktree: Path, task: FixTask, edits: list[TextEdit]) -> list[str]:
    """Apply exact, bounded text operations inside an owned detached worktree."""

    root = worktree.resolve()
    if not edits:
        raise PatchPolicyError("structured proposal contains no edits")
    payload_bytes = sum(
        len(edit.content.encode("utf-8"))
        if isinstance(edit, CreateFileEdit)
        else (
            len(edit.old_text.encode("utf-8")) + len(edit.new_text.encode("utf-8"))
            if isinstance(edit, ReplaceTextEdit)
            else len(edit.new_text.encode("utf-8"))
        )
        for edit in edits
    )
    if payload_bytes > task.max_patch_bytes * 2:
        raise PatchPolicyError("structured edit payload exceeds the task byte budget")
    validated = [_validated_edit_path(root, task, edit.path) for edit in edits]
    paths = {relative for relative, _ in validated}
    if len(paths) > task.max_changed_files:
        raise PatchPolicyError("structured proposal exceeds the changed-file budget")
    created: set[str] = set()
    for edit, (relative, candidate) in zip(edits, validated, strict=True):
        if isinstance(edit, CreateFileEdit):
            if relative in created or candidate.exists() or candidate.is_symlink():
                raise EditConflictError("create_file path must not already exist")
            _write_bounded_text(candidate, edit.content, task)
            created.add(relative)
            continue
        if isinstance(edit, ReplaceTextEdit):
            if relative in created:
                raise PatchPolicyError("replace_text cannot target a file created in this proposal")
            content = _read_editable_text(candidate, task)
            occurrences = content.count(edit.old_text)
            if occurrences != 1:
                raise EditConflictError(
                    "replace_text old_text must match exactly once; "
                    f"found {occurrences} matches in {relative}"
                )
            updated = content.replace(edit.old_text, edit.new_text, 1)
            if updated == content:
                raise EditConflictError("replace_text must change file content")
            _write_bounded_text(candidate, updated, task)
            continue
        if isinstance(edit, ReplaceLinesEdit):
            if relative in created:
                raise PatchPolicyError(
                    "replace_lines cannot target a file created in this proposal"
                )
            content = _read_editable_text(candidate, task)
            before, segment, after = _line_segment(content, edit.start_line, edit.end_line)
            _verify_segment_hash(
                segment,
                edit.expected_sha256,
                description=f"line range {edit.start_line}-{edit.end_line} in {relative}",
            )
            updated = f"{before}{edit.new_text}{after}"
            if updated == content:
                raise EditConflictError("replace_lines must change file content")
            _write_bounded_text(candidate, updated, task)
            continue
        if isinstance(edit, ReplacePythonSymbolEdit):
            if relative in created:
                raise PatchPolicyError(
                    "replace_python_symbol cannot target a file created in this proposal"
                )
            content = _read_editable_text(candidate, task)
            start_line, end_line = _python_symbol_range(content, relative, edit.symbol)
            before, segment, after = _line_segment(content, start_line, end_line)
            _verify_segment_hash(
                segment,
                edit.expected_sha256,
                description=f"Python symbol {edit.symbol} in {relative}",
            )
            updated = f"{before}{edit.new_text}{after}"
            if updated == content:
                raise EditConflictError("replace_python_symbol must change file content")
            try:
                ast.parse(updated, filename=relative)
            except SyntaxError as exc:
                raise EditConflictError(
                    "replace_python_symbol produced invalid Python syntax"
                ) from exc
            _write_bounded_text(candidate, updated, task)
            continue
        raise PatchPolicyError("unsupported structured edit operation")
    return sorted(paths)


def materialize_proposal_patch(
    repository: GitRepository,
    worktree: Path,
    base_commit: str,
    task: FixTask,
    proposal: ImplementerProposal,
    *,
    deadline: float | None = None,
) -> str:
    """Turn structured edits into a Git-authored Patch in an isolated worktree."""

    if proposal.patch is not None:
        validate_proposed_patch(task, proposal.patch)
        return proposal.patch
    registered = False
    try:
        repository.add_worktree(worktree, base_commit, deadline=deadline)
        registered = True
        apply_structured_edits(worktree, task, proposal.edits)
        patch = final_diff(worktree, base_commit, deadline=deadline)
        if not patch.strip():
            raise PatchPolicyError("structured edits generated an empty Patch")
        validate_proposed_patch(task, patch)
        return patch
    finally:
        if registered:
            try:
                repository.remove_worktree(worktree)
            except Exception as exc:
                raise PatchPolicyError(f"structured-edit worktree cleanup failed: {exc}") from exc
        shutil.rmtree(worktree, ignore_errors=True)
