"""Read-only repository tools and proposed-patch policy."""

from __future__ import annotations

import fnmatch
import hashlib
import io
import os
import re
import tokenize
from pathlib import Path, PurePosixPath
from typing import Protocol

from prguard.implementer.ast_index import PythonAstIndex, PythonSource
from prguard.implementer.errors import PatchPolicyError, RepositoryAccessError
from prguard.schemas import FixTask

_DENIED_PARTS = {
    ".git",
    ".ssh",
    ".aws",
    ".gnupg",
    "node_modules",
    ".venv",
    "__pycache__",
}
_DENIED_NAMES = {
    ".env",
    ".env.local",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
}
_SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
_MAX_AST_FILES = 2_000
_MAX_AST_SOURCE_BYTES = 20_000_000


class RepositoryReadLimits(Protocol):
    max_file_bytes: int
    max_context_bytes: int


def _safe_relative(value: str) -> PurePosixPath:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise RepositoryAccessError("path must remain repository-relative")
    if any(part in _DENIED_PARTS for part in path.parts):
        raise RepositoryAccessError("path enters a denied repository directory")
    name = path.name.lower()
    if name in _DENIED_NAMES or name.startswith(".env") or path.suffix.lower() in _SECRET_SUFFIXES:
        raise RepositoryAccessError("credential-like files are not readable")
    return path


def _is_probably_binary(data: bytes) -> bool:
    sample = data[:4096]
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


class RepositoryTools:
    """A byte-budgeted, read-only view over one detached base worktree."""

    def __init__(self, root: Path, task: RepositoryReadLimits) -> None:
        self.root = root.resolve()
        self.max_file_bytes = task.max_file_bytes
        self.remaining_context_bytes = task.max_context_bytes
        self._python_ast_index: PythonAstIndex | None = None

    def _resolve(self, relative: str) -> Path:
        safe = _safe_relative(relative)
        candidate = self.root / safe.as_posix()
        try:
            candidate.resolve(strict=False).relative_to(self.root)
        except ValueError as exc:
            raise RepositoryAccessError("path resolves outside the repository") from exc
        return candidate

    def _charge(self, value: object) -> object:
        size = len(str(value).encode("utf-8"))
        if size > self.remaining_context_bytes:
            raise RepositoryAccessError("repository context byte budget exhausted")
        self.remaining_context_bytes -= size
        return value

    def list_files(self, pattern: str = "**", max_results: int = 200) -> dict[str, object]:
        if max_results < 1 or max_results > 500:
            raise RepositoryAccessError("max_results must be between 1 and 500")
        if Path(pattern).is_absolute() or ".." in PurePosixPath(pattern).parts:
            raise RepositoryAccessError("file pattern must remain repository-relative")
        matches: list[str] = []
        for current, dirs, files in os.walk(self.root, topdown=True, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name not in _DENIED_PARTS)
            for name in sorted(files):
                path = Path(current) / name
                relative = path.relative_to(self.root).as_posix()
                try:
                    _safe_relative(relative)
                except RepositoryAccessError:
                    continue
                matches_pattern = fnmatch.fnmatchcase(relative, pattern)
                if pattern.startswith("**/"):
                    matches_pattern = matches_pattern or fnmatch.fnmatchcase(relative, pattern[3:])
                if matches_pattern or pattern == "**":
                    matches.append(relative)
                    if len(matches) >= max_results:
                        return self._charge({"files": matches, "truncated": True})  # type: ignore[return-value]
        return self._charge({"files": matches, "truncated": False})  # type: ignore[return-value]

    def search_text(
        self,
        query: str,
        pattern: str = "**",
        max_results: int = 100,
    ) -> dict[str, object]:
        if not query or len(query) > 500:
            raise RepositoryAccessError("query must contain 1 to 500 characters")
        if max_results < 1 or max_results > 200:
            raise RepositoryAccessError("max_results must be between 1 and 200")
        files = self.list_files(pattern=pattern, max_results=500)["files"]
        results: list[dict[str, object]] = []
        for relative in files:
            path = self._resolve(str(relative))
            if not path.is_file() or path.is_symlink() or path.stat().st_size > self.max_file_bytes:
                continue
            data = path.read_bytes()
            if _is_probably_binary(data):
                continue
            for line_number, line in enumerate(
                data.decode("utf-8", errors="replace").splitlines(), 1
            ):
                if query.casefold() in line.casefold():
                    results.append({"path": relative, "line": line_number, "text": line[:500]})
                    if len(results) >= max_results:
                        return self._charge({"matches": results, "truncated": True})  # type: ignore[return-value]
        return self._charge({"matches": results, "truncated": False})  # type: ignore[return-value]

    def read_file(self, path: str, start_line: int = 1, end_line: int = 400) -> dict[str, object]:
        if start_line < 1 or end_line < start_line or end_line - start_line > 1000:
            raise RepositoryAccessError("line range is invalid or exceeds 1001 lines")
        candidate = self._resolve(path)
        if candidate.is_symlink() or not candidate.is_file():
            raise RepositoryAccessError("path must identify a regular repository file")
        if candidate.stat().st_size > self.max_file_bytes:
            raise RepositoryAccessError("file exceeds the configured read limit")
        data = candidate.read_bytes()
        if _is_probably_binary(data):
            raise RepositoryAccessError("binary files are not readable")
        text = data.decode("utf-8", errors="replace")
        raw_lines = text.splitlines(keepends=True)
        selected_raw = "".join(raw_lines[start_line - 1 : end_line])
        selected = selected_raw.splitlines()
        content = "\n".join(f"{start_line + index}: {line}" for index, line in enumerate(selected))
        return self._charge(
            {
                "path": path,
                "start_line": start_line,
                "end_line": start_line + len(selected) - 1,
                "content": content,
                "content_sha256": hashlib.sha256(selected_raw.encode("utf-8")).hexdigest(),
                "truncated": end_line < len(raw_lines),
            }
        )  # type: ignore[return-value]

    def _build_python_ast_index(self) -> PythonAstIndex:
        if self._python_ast_index is not None:
            return self._python_ast_index
        sources: list[PythonSource] = []
        total_bytes = 0
        skipped_large_files = 0
        truncated = False
        for current, dirs, files in os.walk(self.root, topdown=True, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name not in _DENIED_PARTS)
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                path = Path(current) / name
                relative = path.relative_to(self.root).as_posix()
                try:
                    _safe_relative(relative)
                except RepositoryAccessError:
                    continue
                if path.is_symlink() or not path.is_file():
                    continue
                size = path.stat().st_size
                if size > self.max_file_bytes:
                    skipped_large_files += 1
                    continue
                if len(sources) >= _MAX_AST_FILES or total_bytes + size > _MAX_AST_SOURCE_BYTES:
                    truncated = True
                    continue
                data = path.read_bytes()
                if _is_probably_binary(data):
                    continue
                try:
                    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
                    content = data.decode(encoding)
                except (SyntaxError, UnicodeDecodeError, LookupError):
                    content = data.decode("utf-8", errors="replace")
                sources.append(PythonSource(path=relative, content=content))
                total_bytes += size
        self._python_ast_index = PythonAstIndex(
            sources,
            truncated=truncated,
            skipped_large_files=skipped_large_files,
        )
        return self._python_ast_index

    @staticmethod
    def _validate_ast_query(value: str, max_results: int) -> None:
        if not value.strip() or len(value) > 500 or any(char in value for char in "\r\n\x00"):
            raise RepositoryAccessError("AST query must contain 1 to 500 safe characters")
        if max_results < 1 or max_results > 200:
            raise RepositoryAccessError("max_results must be between 1 and 200")

    def find_symbols(self, query: str, max_results: int = 50) -> dict[str, object]:
        self._validate_ast_query(query, max_results)
        return self._charge(  # type: ignore[return-value]
            self._build_python_ast_index().find_symbols(query, max_results)
        )

    def list_imports(self, path: str, max_results: int = 100) -> dict[str, object]:
        self._validate_ast_query(path, max_results)
        safe = _safe_relative(path).as_posix()
        if not safe.endswith(".py"):
            raise RepositoryAccessError("import analysis requires a Python file")
        return self._charge(  # type: ignore[return-value]
            self._build_python_ast_index().list_imports(safe, max_results)
        )

    def find_callers(self, symbol: str, max_results: int = 100) -> dict[str, object]:
        self._validate_ast_query(symbol, max_results)
        return self._charge(  # type: ignore[return-value]
            self._build_python_ast_index().find_callers(symbol, max_results)
        )

    def find_callees(self, symbol: str, max_results: int = 100) -> dict[str, object]:
        self._validate_ast_query(symbol, max_results)
        return self._charge(  # type: ignore[return-value]
            self._build_python_ast_index().find_callees(symbol, max_results)
        )

    def trace_call_graph(
        self,
        symbol: str,
        direction: str = "both",
        max_depth: int = 2,
        max_results: int = 100,
    ) -> dict[str, object]:
        self._validate_ast_query(symbol, max_results)
        if direction not in {"callers", "callees", "both"}:
            raise RepositoryAccessError("call graph direction must be callers, callees, or both")
        if max_depth < 1 or max_depth > 3:
            raise RepositoryAccessError("call graph max_depth must be between 1 and 3")
        return self._charge(  # type: ignore[return-value]
            self._build_python_ast_index().trace_call_graph(
                symbol,
                direction,
                max_depth,
                max_results,
            )
        )

    def find_references(self, symbol: str, max_results: int = 100) -> dict[str, object]:
        self._validate_ast_query(symbol, max_results)
        return self._charge(  # type: ignore[return-value]
            self._build_python_ast_index().find_references(symbol, max_results)
        )

    def find_related_tests(self, target: str, max_results: int = 50) -> dict[str, object]:
        self._validate_ast_query(target, max_results)
        if target.endswith(".py") or "/" in target or "\\" in target:
            target = _safe_relative(target).as_posix()
        return self._charge(  # type: ignore[return-value]
            self._build_python_ast_index().find_related_tests(target, max_results)
        )


_DIFF_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$")
_FILE_HEADER = re.compile(r"^(?:---|\+\+\+) (?:[ab]/)?(.+?)(?:\t.*)?$")


def validate_proposed_patch(task: FixTask, patch: str) -> list[str]:
    encoded = patch.encode("utf-8")
    if len(encoded) > task.max_patch_bytes:
        raise PatchPolicyError("proposal exceeds the patch byte budget")
    if "GIT binary patch" in patch or "Binary files " in patch:
        raise PatchPolicyError("binary patches are not supported by the MVP")
    if any(
        line.startswith(("rename from ", "rename to ", "copy from ", "copy to "))
        for line in patch.splitlines()
    ):
        raise PatchPolicyError("rename and copy patches are not supported by the MVP")
    paths: set[str] = set()
    file_headers: set[str] = set()
    for line in patch.splitlines():
        match = _DIFF_HEADER.match(line)
        values: tuple[str, ...] = match.groups() if match else ()
        file_match = _FILE_HEADER.match(line)
        if file_match and file_match.group(1) != "/dev/null":
            values += (file_match.group(1),)
        for value in values:
            try:
                path = _safe_relative(value)
            except RepositoryAccessError as exc:
                raise PatchPolicyError(str(exc)) from exc
            if match:
                paths.add(path.as_posix())
            else:
                file_headers.add(path.as_posix())
    if not paths:
        raise PatchPolicyError("proposal contains no standard unified-diff file headers")
    if len(paths) > task.max_changed_files:
        raise PatchPolicyError("proposal exceeds the changed-file budget")
    undeclared = sorted(file_headers - paths)
    if undeclared:
        raise PatchPolicyError(f"file headers are not declared by diff --git: {undeclared}")
    blocked = sorted(
        path
        for path in paths
        if any(fnmatch.fnmatchcase(path, pattern) for pattern in task.protected_paths)
    )
    if blocked:
        raise PatchPolicyError(f"proposal modifies protected paths: {blocked}")
    outside = sorted(
        path
        for path in paths
        if not any(fnmatch.fnmatchcase(path, pattern) for pattern in task.writable_paths)
    )
    if outside:
        raise PatchPolicyError(f"proposal modifies paths outside writable scope: {outside}")
    return sorted(paths)
