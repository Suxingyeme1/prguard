"""Deterministic, fail-safe routing for optional Independent Review."""

from __future__ import annotations

import ast
import hashlib
import io
import shutil
import time
import tokenize
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from prguard.harness.artifacts import canonical_json, sha256_file, verify_manifest
from prguard.harness.errors import ArtifactIntegrityError, PreflightError
from prguard.harness.git import (
    GitRepository,
    apply_patch,
    changed_files,
    run_git,
)
from prguard.implementer.errors import RepositoryAccessError
from prguard.implementer.tools import RepositoryTools
from prguard.schemas import (
    FixOutcome,
    FixReport,
    FixTask,
    IssueToPRTask,
    ReviewRiskFactor,
    ReviewRoute,
    ReviewRoutingMode,
    ReviewRoutingResult,
    ReviewSymbolImpact,
    RunOutcome,
)

_REVIEW_THRESHOLD = 5
_ROUTING_TIMEOUT_SECONDS = 30.0
_MAX_CHANGED_SYMBOLS = 12
_GRAPH_DEPTH = 2
_GRAPH_RESULTS = 80
_MAX_FACTOR_EVIDENCE = 100
_MAX_RESULT_TEST_PATHS = 200
_MAX_ANALYSIS_NOTES = 100

_TEST_CONFIG_NAMES = {
    "conftest.py",
    "pytest.ini",
    "tox.ini",
    "noxfile.py",
    "setup.cfg",
}
_DEPENDENCY_OR_BUILD_NAMES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "uv.lock",
    "poetry.lock",
    "pdm.lock",
    "pipfile",
    "pipfile.lock",
    "dockerfile",
    "compose.yml",
    "compose.yaml",
}
_SENSITIVE_PARTS = {
    "auth",
    "authentication",
    "authorization",
    "crypto",
    "migration",
    "migrations",
    "permissions",
    "security",
}
_SENSITIVE_NAME_FRAGMENTS = {
    "credential",
    "permission",
    "secret",
    "token",
}
_NON_PYTHON_CODE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
}
_DOC_SUFFIXES = {".md", ".rst", ".adoc"}
_PYTEST_FILTER_FLAGS = {
    "-k",
    "-m",
    "--deselect",
    "--ignore",
    "--ignore-glob",
    "--lf",
    "--ff",
    "--failed-first",
    "--last-failed",
    "--new-first",
    "--stepwise",
    "--sw",
}
_PYTEST_NON_EXECUTION_FLAGS = {
    "--co",
    "--collect-only",
    "--fixtures",
    "--fixtures-per-test",
    "--help",
    "--markers",
    "--setup-only",
    "--setup-plan",
    "--version",
}
_NORMAL_GIT_MODE_TRANSITIONS = {
    ("000000", "100644"),
    ("100644", "000000"),
    ("100644", "100644"),
}


@dataclass(frozen=True)
class _SymbolFingerprint:
    symbol: str
    path: str
    digest: str


def _module_name(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[0] in {"src", "lib", "test", "tests"}:
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _is_test_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        path.name == "conftest.py"
        or bool({"test", "tests"} & set(path.parts[:-1]))
        or path.name.startswith("test_")
        or path.name.endswith("_test.py")
    )


def _is_documentation_path(value: str) -> bool:
    path = PurePosixPath(value)
    lowered = path.name.casefold()
    suffix = path.suffix.casefold()
    return (
        suffix in _DOC_SUFFIXES
        or (
            suffix == ""
            and lowered.startswith(("readme", "changelog", "contributing", "license"))
        )
    )


def _is_sensitive_path(value: str) -> bool:
    path = PurePosixPath(value)
    lowered_parts = {part.casefold() for part in path.parts}
    name = path.name.casefold()
    stem_parts = set(path.stem.casefold().replace("-", "_").split("_"))
    return (
        bool((lowered_parts | stem_parts) & _SENSITIVE_PARTS)
        or any(fragment in name for fragment in _SENSITIVE_NAME_FRAGMENTS)
        or tuple(part.casefold() for part in path.parts[:2]) == (".github", "workflows")
    )


def _is_test_or_gate_config(value: str) -> bool:
    path = PurePosixPath(value)
    name = path.name.casefold()
    return (
        name in _TEST_CONFIG_NAMES
        or name.startswith("pytest.")
        or (".github" in path.parts and "workflows" in path.parts)
    )


def _is_dependency_or_build_path(value: str) -> bool:
    path = PurePosixPath(value)
    name = path.name.casefold()
    return (
        name in _DEPENDENCY_OR_BUILD_NAMES
        or name.startswith("requirements")
        or name.endswith((".lock", ".toml"))
    )


def _decode_python(path: Path) -> str:
    data = path.read_bytes()
    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    return data.decode(encoding)


def _fingerprints_for_file(
    root: Path,
    relative: str,
    max_file_bytes: int,
) -> tuple[dict[str, _SymbolFingerprint], list[str]]:
    path = root / relative
    if not path.exists():
        return {}, []
    if path.is_symlink() or not path.is_file():
        return {}, [f"{relative}: changed Python path is not a regular file"]
    if path.stat().st_size > max_file_bytes:
        return {}, [f"{relative}: changed Python file exceeds analysis limit"]
    try:
        tree = ast.parse(_decode_python(path), filename=relative)
    except (OSError, SyntaxError, UnicodeError, ValueError):
        return {}, [f"{relative}: Python AST parsing failed"]

    module = _module_name(relative)
    result: dict[str, _SymbolFingerprint] = {}

    def record(symbol: str, value: object) -> None:
        digest = hashlib.sha256(repr(value).encode("utf-8")).hexdigest()
        result[symbol] = _SymbolFingerprint(symbol=symbol, path=relative, digest=digest)

    module_surface = [
        ast.dump(item, include_attributes=False)
        for item in tree.body
        if not isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    record(module or relative, ("module", module_surface))

    def walk(body: list[ast.stmt], parents: list[str]) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                qualified = ".".join(filter(None, [module, *parents, node.name]))
                class_surface = (
                    [ast.dump(item, include_attributes=False) for item in node.bases],
                    [ast.dump(item, include_attributes=False) for item in node.keywords],
                    [ast.dump(item, include_attributes=False) for item in node.decorator_list],
                    [
                        ast.dump(item, include_attributes=False)
                        for item in node.body
                        if not isinstance(
                            item,
                            (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
                        )
                    ],
                )
                record(qualified, ("class", class_surface))
                walk(node.body, [*parents, node.name])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = ".".join(filter(None, [module, *parents, node.name]))
                record(qualified, ("function", ast.dump(node, include_attributes=False)))

    walk(tree.body, [])
    return result, []


def _changed_symbol_fingerprints(
    base: Path,
    candidate: Path,
    python_paths: list[str],
    max_file_bytes: int,
) -> tuple[list[tuple[_SymbolFingerprint, str, str]], list[str]]:
    changed: list[tuple[_SymbolFingerprint, str, str]] = []
    notes: list[str] = []
    for relative in python_paths:
        base_values, base_notes = _fingerprints_for_file(base, relative, max_file_bytes)
        candidate_values, candidate_notes = _fingerprints_for_file(
            candidate, relative, max_file_bytes
        )
        notes.extend(base_notes)
        notes.extend(candidate_notes)
        for symbol in sorted(base_values.keys() | candidate_values.keys()):
            before = base_values.get(symbol)
            after = candidate_values.get(symbol)
            if before is not None and after is not None and before.digest == after.digest:
                continue
            if before is None:
                assert after is not None
                changed.append((after, "added", "candidate"))
            elif after is None:
                changed.append((before, "deleted", "base"))
            else:
                changed.append((after, "modified", "candidate"))
    return changed, sorted(set(notes))


def _stateful_factory_evidence(
    root: Path,
    python_paths: list[str],
    changed_symbols: set[str],
    max_file_bytes: int,
) -> list[str]:
    """Find changed factories that return nested classes with cross-method state writes."""

    evidence: list[str] = []
    for relative in python_paths:
        path = root / relative
        if not path.exists() or path.is_symlink() or not path.is_file():
            continue
        if path.stat().st_size > max_file_bytes:
            continue
        try:
            tree = ast.parse(_decode_python(path), filename=relative)
        except (OSError, SyntaxError, UnicodeError, ValueError):
            continue
        module = _module_name(relative)

        def walk(
            body: list[ast.stmt],
            parents: list[str],
            module_name: str = module,
        ) -> None:
            for node in body:
                if isinstance(node, ast.ClassDef):
                    walk(node.body, [*parents, node.name])
                    continue
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                symbol = ".".join(filter(None, [module_name, *parents, node.name]))
                if symbol not in changed_symbols:
                    continue
                nested_classes = {
                    item.name: item for item in node.body if isinstance(item, ast.ClassDef)
                }
                # Only a direct return from the factory body establishes the
                # factory/class relationship.  Walking the whole subtree would
                # also see returns inside the nested class's methods.
                returned_names = {
                    item.value.id
                    for item in node.body
                    if isinstance(item, ast.Return)
                    and isinstance(item.value, ast.Name)
                }
                for class_name in sorted(returned_names & nested_classes.keys()):
                    class_node = nested_classes[class_name]
                    attribute_methods: dict[str, set[str]] = {}
                    for method in class_node.body:
                        if not isinstance(
                            method,
                            (ast.FunctionDef, ast.AsyncFunctionDef),
                        ):
                            continue
                        for child in ast.walk(method):
                            if (
                                isinstance(child, ast.Attribute)
                                and isinstance(child.value, ast.Name)
                                and child.value.id == "self"
                                and isinstance(child.ctx, ast.Store)
                            ):
                                attribute_methods.setdefault(child.attr, set()).add(
                                    method.name
                                )
                    cross_method = sorted(
                        name
                        for name, methods in attribute_methods.items()
                        if len(methods) >= 2
                    )
                    if cross_method:
                        evidence.append(
                            f"{symbol}: returns nested class {class_name}; cross-method "
                            f"state={','.join(cross_method[:8])}"
                        )

        walk(tree.body, [])
    return sorted(set(evidence))


def _pytest_arguments(argv: list[str]) -> list[str] | None:
    if argv and argv[0] == "pytest":
        return argv[1:]
    if (
        len(argv) >= 3
        and argv[0] in {"python", "python3", "python3.12"}
        and argv[1:3] == ["-m", "pytest"]
    ):
        return argv[3:]
    return None


def _pytest_scope_and_targets(fix: FixReport) -> tuple[str, list[str]]:
    verification = fix.attempts[-1].verification if fix.attempts else None
    if verification is None:
        return "none", []
    saw_pytest = False
    filtered = False
    saw_unfiltered_full = False
    targets: set[str] = set()
    for command in verification.commands:
        arguments = _pytest_arguments(command.argv)
        if arguments is None:
            continue
        saw_pytest = True
        command_filtered = any(
            token in _PYTEST_FILTER_FLAGS
            or any(token.startswith(f"{flag}=") for flag in _PYTEST_FILTER_FLAGS)
            or token in _PYTEST_NON_EXECUTION_FLAGS
            or any(
                token.startswith(f"{flag}=")
                for flag in _PYTEST_NON_EXECUTION_FLAGS
            )
            or "::" in token
            for token in arguments
        )
        if command_filtered:
            filtered = True
        command_targets: set[str] = set()
        for token in arguments:
            if token.startswith("-"):
                continue
            candidate = token.split("::", 1)[0].replace("\\", "/").rstrip("/")
            path = PurePosixPath(candidate)
            if (
                candidate in {".", "test", "tests"}
                or path.suffix == ".py"
                or "test" in path.parts
                or "tests" in path.parts
            ):
                command_targets.add(candidate or ".")
        if command_targets:
            targets.update(command_targets)
        elif not command_filtered:
            # A successful unfiltered invocation with no explicit test target ran the
            # whole configured suite. Later candidate-test replays do not narrow that
            # already established coverage.
            saw_unfiltered_full = True
    if not saw_pytest:
        return "none", []
    if saw_unfiltered_full:
        return "full", []
    if filtered:
        return "filtered", sorted(targets)
    if targets:
        return "targeted", sorted(targets)
    return "targeted", []


def _target_covers(target: str, test_path: str) -> bool:
    if target == ".":
        return False
    normalized = target.split("::", 1)[0].rstrip("/")
    return test_path == normalized or test_path.startswith(f"{normalized}/")


def _patch_stats(
    worktree: Path,
    base_commit: str,
    *,
    deadline_monotonic: float,
) -> tuple[int, int, list[str], list[str]]:
    intent = run_git(
        worktree,
        "add",
        "--intent-to-add",
        "--",
        ".",
        timeout=GitRepository._timeout(deadline_monotonic),
    )
    if intent.returncode != 0:
        raise PreflightError("unable to prepare candidate Patch statistics")
    result = run_git(
        worktree,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--numstat",
        base_commit,
        "--",
        timeout=GitRepository._timeout(deadline_monotonic),
    )
    if result.returncode != 0:
        raise PreflightError("unable to calculate candidate Patch statistics")
    raw = run_git(
        worktree,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--raw",
        "--no-renames",
        base_commit,
        "--",
        timeout=GitRepository._timeout(deadline_monotonic),
    )
    if raw.returncode != 0:
        raise PreflightError("unable to calculate candidate Git modes")
    additions = 0
    deletions = 0
    notes: list[str] = []
    for line in result.stdout.splitlines():
        added, removed, _, = line.split("\t", 2)
        if added == "-" or removed == "-":
            notes.append("binary or non-text Patch statistics are unsupported")
            continue
        additions += int(added)
        deletions += int(removed)
    nonstandard_modes: list[str] = []
    for line in raw.stdout.splitlines():
        try:
            metadata, path = line.split("\t", 1)
            values = metadata.split()
            old_mode = values[0].removeprefix(":")
            new_mode = values[1]
        except (IndexError, ValueError):
            notes.append("Git mode metadata could not be parsed")
            continue
        if (old_mode, new_mode) not in _NORMAL_GIT_MODE_TRANSITIONS:
            nonstandard_modes.append(path.strip('"'))
    return additions, deletions, notes, sorted(set(nonstandard_modes))


def _factor(
    code: str,
    weight: int,
    summary: str,
    evidence: list[str] | None = None,
) -> ReviewRiskFactor:
    values = sorted(set(evidence or []))
    if len(values) > _MAX_FACTOR_EVIDENCE:
        omitted = len(values) - (_MAX_FACTOR_EVIDENCE - 1)
        values = [
            *values[: _MAX_FACTOR_EVIDENCE - 1],
            f"... {omitted} additional evidence entries omitted",
        ]
    return ReviewRiskFactor(
        code=code,
        weight=weight,
        summary=summary,
        evidence=values,
    )


def _bound_manifests(fix: FixReport) -> tuple[str, str, FixTask]:
    fix_root = Path(fix.artifact_directory).resolve()
    final_patch = Path(fix.final_patch or "").resolve()
    try:
        final_patch.relative_to(fix_root)
    except ValueError as exc:
        raise ArtifactIntegrityError("Fix final Patch escapes its artifact directory") from exc
    fix_manifest = verify_manifest(fix_root / "fix-manifest.json")
    if (
        fix_manifest.run_id != fix.run_id
        or fix_manifest.case_id != fix.case_id
        or fix_manifest.resolved_base_commit != fix.resolved_base_commit
    ):
        raise ArtifactIntegrityError("Fix manifest identity does not match Fix report")
    archived_report = FixReport.model_validate_json(
        (Path(fix.artifact_directory) / "fix-report.json").read_bytes()
    )
    if canonical_json(archived_report.model_dump(mode="json")) != canonical_json(
        fix.model_dump(mode="json")
    ):
        raise ArtifactIntegrityError("in-memory Fix report differs from verified artifact")
    archived_task = FixTask.model_validate_json(
        (Path(fix.artifact_directory) / "fix-task.json").read_bytes()
    )
    verification = fix.attempts[-1].verification if fix.attempts else None
    if verification is None or verification.artifact_directory is None:
        raise ArtifactIntegrityError("accepted Fix has no verification artifact")
    verification_root = Path(verification.artifact_directory).resolve()
    try:
        verification_root.relative_to(fix_root)
    except ValueError as exc:
        raise ArtifactIntegrityError(
            "verification artifacts escape the Fix artifact directory"
        ) from exc
    verification_manifest = verify_manifest(
        verification_root / "manifest.json"
    )
    if (
        verification_manifest.run_id != verification.run_id
        or verification_manifest.case_id != verification.case_id
        or verification_manifest.resolved_base_commit
        != verification.resolved_base_commit
    ):
        raise ArtifactIntegrityError(
            "verification manifest identity does not match verification report"
        )
    return (
        fix_manifest.manifest_sha256,
        verification_manifest.manifest_sha256,
        archived_task,
    )


def _always_result(
    task: IssueToPRTask,
    fix: FixReport,
    patch_sha256: str,
    fix_manifest_sha256: str,
    verification_manifest_sha256: str,
    duration_seconds: float,
) -> ReviewRoutingResult:
    return ReviewRoutingResult(
        mode=task.review_routing_mode,
        recommended_route=ReviewRoute.REVIEW,
        effective_route=ReviewRoute.REVIEW,
        score=_REVIEW_THRESHOLD,
        threshold=_REVIEW_THRESHOLD,
        resolved_base_commit=fix.resolved_base_commit or task.base_commit,
        patch_sha256=patch_sha256,
        fix_manifest_sha256=fix_manifest_sha256,
        verification_manifest_sha256=verification_manifest_sha256,
        changed_files=(
            fix.attempts[-1].verification.changed_files
            if fix.attempts and fix.attempts[-1].verification
            else []
        ),
        changed_python_files=[],
        changed_test_files=[],
        additions=0,
        deletions=0,
        pytest_scope="none",
        factors=[
            _factor(
                "always_review",
                _REVIEW_THRESHOLD,
                "routing mode requires Independent Review for every accepted Fix",
            )
        ],
        analysis_notes=[
            "risk analysis was intentionally skipped because always mode cannot skip review"
        ],
        duration_seconds=duration_seconds,
    )


def route_accepted_fix(
    task: IssueToPRTask,
    fix: FixReport,
    workspace: Path,
    *,
    deadline_monotonic: float | None = None,
) -> ReviewRoutingResult:
    """Bind and route one already accepted Fix without executing repository code."""

    started = time.monotonic()
    routing_deadline = started + _ROUTING_TIMEOUT_SECONDS
    if deadline_monotonic is not None:
        routing_deadline = min(routing_deadline, deadline_monotonic)
    if (
        fix.outcome is not FixOutcome.ACCEPTED
        or fix.final_patch is None
        or fix.resolved_base_commit is None
        or not fix.attempts
        or fix.attempts[-1].verification is None
        or fix.attempts[-1].verification.outcome is not RunOutcome.PASSED
    ):
        raise ValueError("Reviewer routing requires an accepted, verified Fix")
    verification = fix.attempts[-1].verification
    if verification.resolved_base_commit != fix.resolved_base_commit:
        raise ArtifactIntegrityError("Fix and verification base commits do not match")
    if verification.policy_violations:
        raise ArtifactIntegrityError("accepted Fix contains policy violations")
    (
        fix_manifest_sha256,
        verification_manifest_sha256,
        routing_task,
    ) = _bound_manifests(fix)
    patch = Path(fix.final_patch)
    patch_bytes = patch.read_bytes()
    patch_sha256 = hashlib.sha256(patch_bytes).hexdigest()
    if verification.patch.patch_sha256 != patch_sha256:
        raise ArtifactIntegrityError("Fix final Patch does not match verified Patch hash")
    if task.review_routing_mode is ReviewRoutingMode.ALWAYS:
        return _always_result(
            task,
            fix,
            patch_sha256,
            fix_manifest_sha256,
            verification_manifest_sha256,
            time.monotonic() - started,
        )

    resolved = fix.resolved_base_commit
    repository = GitRepository(routing_task.repository)
    base_worktree = workspace / "_routing_base"
    candidate_worktree = workspace / "_routing_candidate"
    patch_snapshot = workspace / "_routing_candidate.patch"
    base_registered = False
    candidate_registered = False
    analysis_notes: list[str] = []
    factors: list[ReviewRiskFactor] = []
    impacts: list[ReviewSymbolImpact] = []
    changed: list[str] = []
    python_paths: list[str] = []
    test_paths: list[str] = []
    additions = 0
    deletions = 0
    nonstandard_mode_paths: list[str] = []
    pytest_scope, pytest_targets = _pytest_scope_and_targets(fix)
    changed_symbols: list[str] = []
    covered_unchanged_tests: list[str] = []
    uncovered_reachable: list[str] = []
    uncovered_related: list[str] = []
    stateful_factory_evidence: list[str] = []
    analysis_incomplete = False
    source_changed_symbol_count = 0
    if len(pytest_targets) > _MAX_RESULT_TEST_PATHS:
        analysis_incomplete = True
        analysis_notes.append(
            "declared pytest target count exceeds the routing Artifact limit"
        )
        pytest_targets = pytest_targets[:_MAX_RESULT_TEST_PATHS]
    try:
        if time.monotonic() >= routing_deadline:
            raise TimeoutError("routing deadline expired")
        workspace.mkdir(parents=True, exist_ok=True)
        patch_snapshot.write_bytes(patch_bytes)
        patch_snapshot.chmod(0o400)
        if sha256_file(patch_snapshot) != patch_sha256:
            raise ArtifactIntegrityError("unable to freeze verified Patch for routing")
        repository.add_worktree(base_worktree, resolved, deadline=routing_deadline)
        base_registered = True
        repository.add_worktree(
            candidate_worktree,
            resolved,
            deadline=routing_deadline,
        )
        candidate_registered = True
        applied, _ = apply_patch(
            candidate_worktree,
            patch_snapshot,
            deadline=routing_deadline,
        )
        if sha256_file(patch_snapshot) != patch_sha256:
            raise ArtifactIntegrityError("routing Patch snapshot changed during replay")
        if not applied:
            raise PreflightError("verified final Patch could not be replayed for routing")
        changed = changed_files(candidate_worktree, deadline=routing_deadline)
        verification_changed = sorted(fix.attempts[-1].verification.changed_files)
        if changed != verification_changed:
            analysis_incomplete = True
            analysis_notes.append(
                "routing replay changed-file set differs from verified changed-file set"
            )
        additions, deletions, stat_notes, nonstandard_mode_paths = _patch_stats(
            candidate_worktree,
            resolved,
            deadline_monotonic=routing_deadline,
        )
        analysis_notes.extend(stat_notes)
        if stat_notes:
            analysis_incomplete = True
        python_paths = sorted(path for path in changed if path.endswith(".py"))
        test_paths = sorted(path for path in changed if _is_test_path(path))

        changed_values, symbol_notes = _changed_symbol_fingerprints(
            base_worktree,
            candidate_worktree,
            python_paths,
            routing_task.max_file_bytes,
        )
        analysis_notes.extend(symbol_notes)
        if symbol_notes:
            analysis_incomplete = True
        changed_symbols = [item.symbol for item, _, _ in changed_values]
        source_changed_symbol_count = sum(
            not _is_test_path(item.path) for item, _, _ in changed_values
        )
        stateful_factory_evidence = _stateful_factory_evidence(
            candidate_worktree,
            python_paths,
            set(changed_symbols),
            routing_task.max_file_bytes,
        )
        if len(changed_values) > _MAX_CHANGED_SYMBOLS:
            analysis_incomplete = True
            analysis_notes.append(
                f"changed symbol count exceeds {_MAX_CHANGED_SYMBOLS}-symbol analysis cap"
            )
        base_tools = RepositoryTools(base_worktree, routing_task)
        candidate_tools = RepositoryTools(candidate_worktree, routing_task)
        for fingerprint, change_kind, graph_source in changed_values[:_MAX_CHANGED_SYMBOLS]:
            if time.monotonic() >= routing_deadline:
                raise TimeoutError("routing deadline expired")
            if _is_test_path(fingerprint.path):
                continue
            tools = base_tools if graph_source == "base" else candidate_tools
            try:
                graph = tools.trace_call_graph(
                    fingerprint.symbol,
                    direction="callers",
                    max_depth=_GRAPH_DEPTH,
                    max_results=_GRAPH_RESULTS,
                )
            except RepositoryAccessError:
                analysis_incomplete = True
                analysis_notes.append(
                    f"{fingerprint.symbol}: call-graph response exceeded a read boundary"
                )
                continue
            root_resolution = str(graph["root_resolution"])
            index = graph["index"]
            graph_truncated = bool(graph["truncated"])
            if (
                root_resolution not in {"exact", "unique_suffix"}
                or graph_truncated
                or bool(index["truncated"])
                or int(index["parse_error_count"]) > 0
                or int(index["skipped_large_files"]) > 0
            ):
                analysis_incomplete = True
                analysis_notes.append(
                    f"{fingerprint.symbol}: static impact analysis is incomplete"
                )
            root = fingerprint.symbol.casefold()
            direct_callers = {
                str(edge["caller"])
                for edge in graph["edges"]
                if int(edge["depth"]) == 1
                and str(edge["callee"]).casefold() == root
                and not _is_test_path(str(edge["path"]))
            }
            transitive_callers = {
                str(node["symbol"])
                for node in graph["nodes"]
                if int(node["depth"]) > 0
                and bool(node["defined_in_repository"])
                and node["path"] is not None
                and not _is_test_path(str(node["path"]))
            }
            reachable_tests = sorted(
                {str(item["path"]) for item in graph["reachable_tests"]}
            )
            related_tests = sorted(
                {str(item["path"]) for item in graph["related_tests"]}
            )
            impacts.append(
                ReviewSymbolImpact(
                    symbol=fingerprint.symbol,
                    path=fingerprint.path,
                    change_kind=change_kind,  # type: ignore[arg-type]
                    graph_source=graph_source,  # type: ignore[arg-type]
                    root_resolution=root_resolution,  # type: ignore[arg-type]
                    direct_repository_callers=len(direct_callers),
                    transitive_repository_callers=len(transitive_callers),
                    reachable_tests=reachable_tests,
                    related_tests=related_tests,
                    graph_truncated=graph_truncated,
                )
            )

        reachable = sorted({path for impact in impacts for path in impact.reachable_tests})
        related = sorted({path for impact in impacts for path in impact.related_tests})
        unchanged_reachable = sorted(set(reachable) - set(test_paths))
        unchanged_related = sorted(set(related) - set(test_paths))
        if pytest_scope == "full":
            covered_unchanged_tests = sorted(
                set(unchanged_reachable) | set(unchanged_related)
            )
        elif pytest_scope == "targeted":
            covered_unchanged_tests = sorted(
                path
                for path in set(unchanged_reachable) | set(unchanged_related)
                if any(_target_covers(target, path) for target in pytest_targets)
            )
        uncovered_reachable = sorted(
            set(unchanged_reachable) - set(covered_unchanged_tests)
        )
        uncovered_related = sorted(
            set(unchanged_related) - set(covered_unchanged_tests)
            - set(uncovered_reachable)
        )
    except ArtifactIntegrityError:
        raise
    except Exception as exc:  # every analysis failure must conservatively require review
        analysis_incomplete = True
        analysis_notes.append(
            f"deterministic routing analysis failed closed ({type(exc).__name__})"
        )
    finally:
        if candidate_registered:
            try:
                repository.remove_worktree(candidate_worktree)
            except PreflightError:
                analysis_incomplete = True
                analysis_notes.append("candidate routing worktree cleanup failed")
        if base_registered:
            try:
                repository.remove_worktree(base_worktree)
            except PreflightError:
                analysis_incomplete = True
                analysis_notes.append("base routing worktree cleanup failed")
        shutil.rmtree(candidate_worktree, ignore_errors=True)
        shutil.rmtree(base_worktree, ignore_errors=True)
        patch_snapshot.unlink(missing_ok=True)

    if time.monotonic() >= routing_deadline:
        analysis_incomplete = True
        analysis_notes.append("routing deadline expired before the decision was finalized")

    bounded_test_lists = {
        "covered unchanged tests": covered_unchanged_tests,
        "uncovered reachable tests": uncovered_reachable,
        "uncovered related tests": uncovered_related,
    }
    for label, values in bounded_test_lists.items():
        if len(values) > _MAX_RESULT_TEST_PATHS:
            analysis_incomplete = True
            analysis_notes.append(f"{label} exceed the routing Artifact limit")

    sensitive = sorted(path for path in changed if _is_sensitive_path(path))
    test_or_gate = sorted(
        path for path in changed if _is_test_path(path) or _is_test_or_gate_config(path)
    )
    dependency_or_build = sorted(
        path for path in changed if _is_dependency_or_build_path(path)
    )
    unsupported = sorted(
        path
        for path in changed
        if not path.endswith(".py")
        and not _is_documentation_path(path)
        and (
            PurePosixPath(path).suffix.casefold() in _NON_PYTHON_CODE_SUFFIXES
            or path not in dependency_or_build
        )
    )
    source_python = sorted(path for path in python_paths if not _is_test_path(path))
    if len(fix.attempts) > 1:
        factors.append(
            _factor(
                "implementer_repair_used",
                8,
                "the accepted Fix required an evidence-guided replacement attempt",
                [f"attempts={len(fix.attempts)}"],
            )
        )
    if test_or_gate:
        factors.append(
            _factor(
                "tests_or_gate_changed",
                8,
                "candidate-controlled tests or gate configuration require independent review",
                test_or_gate,
            )
        )
    if sensitive:
        factors.append(
            _factor(
                "sensitive_path_changed",
                8,
                "security-, permission-, migration-, or workflow-sensitive paths changed",
                sensitive,
            )
        )
    if dependency_or_build:
        factors.append(
            _factor(
                "dependency_or_build_changed",
                8,
                "dependency or build policy changed outside Python symbol analysis",
                dependency_or_build,
            )
        )
    if unsupported:
        factors.append(
            _factor(
                "unsupported_source_changed",
                8,
                "changed source is outside the bounded Python AST analysis",
                unsupported,
            )
        )
    if nonstandard_mode_paths:
        factors.append(
            _factor(
                "nonstandard_git_mode",
                8,
                "executable, symlink, submodule, or other non-regular Git modes require review",
                nonstandard_mode_paths,
            )
        )
    if analysis_incomplete:
        factors.append(
            _factor(
                "analysis_incomplete",
                8,
                "static routing evidence is incomplete or could not be replayed",
                analysis_notes,
            )
        )
    if uncovered_reachable:
        factors.append(
            _factor(
                "reachable_tests_not_explicitly_covered",
                7,
                "unchanged statically reachable tests were not named by the verified pytest argv",
                uncovered_reachable,
            )
        )
    if (
        source_python
        and source_changed_symbol_count
        and not covered_unchanged_tests
        and pytest_scope != "full"
    ):
        factors.append(
            _factor(
                "no_explicit_unchanged_test_evidence",
                5,
                "no unchanged related test is explicitly bound to the verified pytest argv",
                [f"pytest_scope={pytest_scope}"],
            )
        )
    if uncovered_related:
        factors.append(
            _factor(
                "related_tests_not_explicitly_covered",
                2,
                "heuristically related unchanged tests were not named by the verified pytest argv",
                uncovered_related,
            )
        )
    if stateful_factory_evidence:
        factors.append(
            _factor(
                "stateful_nested_factory_changed",
                5,
                "a changed factory returns a nested class with cross-method instance state",
                stateful_factory_evidence,
            )
        )
    if len(source_python) >= 4 or len(changed) >= 8:
        factors.append(
            _factor(
                "broad_file_change",
                5,
                "the candidate spans a broad changed-file surface",
                [f"files={len(changed)}", f"python_source_files={len(source_python)}"],
            )
        )
    elif len(source_python) >= 2:
        factors.append(
            _factor(
                "multiple_python_source_files",
                2,
                "multiple Python source files changed",
                source_python,
            )
        )
    changed_lines = additions + deletions
    if changed_lines >= 250:
        factors.append(
            _factor(
                "large_patch",
                5,
                "the candidate exceeds the large-Patch line threshold",
                [f"changed_lines={changed_lines}"],
            )
        )
    elif changed_lines >= 80:
        factors.append(
            _factor(
                "medium_patch",
                2,
                "the candidate exceeds the medium-Patch line threshold",
                [f"changed_lines={changed_lines}"],
            )
        )
    max_direct = max(
        (impact.direct_repository_callers for impact in impacts), default=0
    )
    max_transitive = max(
        (impact.transitive_repository_callers for impact in impacts), default=0
    )
    if max_direct >= 8 or max_transitive >= 15:
        factors.append(
            _factor(
                "high_static_fan_in",
                5,
                "a changed symbol has high bounded static caller impact",
                [f"direct={max_direct}", f"transitive={max_transitive}"],
            )
        )
    elif max_direct >= 3 or max_transitive >= 6:
        factors.append(
            _factor(
                "moderate_static_fan_in",
                2,
                "a changed symbol has moderate bounded static caller impact",
                [f"direct={max_direct}", f"transitive={max_transitive}"],
            )
        )

    factors.sort(key=lambda item: (-item.weight, item.code))
    score = sum(item.weight for item in factors)
    recommended = (
        ReviewRoute.REVIEW if score >= _REVIEW_THRESHOLD else ReviewRoute.SKIP
    )
    effective = (
        recommended
        if task.review_routing_mode is ReviewRoutingMode.SELECTIVE
        else ReviewRoute.REVIEW
    )
    return ReviewRoutingResult(
        mode=task.review_routing_mode,
        recommended_route=recommended,
        effective_route=effective,
        score=score,
        threshold=_REVIEW_THRESHOLD,
        resolved_base_commit=resolved,
        patch_sha256=patch_sha256,
        fix_manifest_sha256=fix_manifest_sha256,
        verification_manifest_sha256=verification_manifest_sha256,
        changed_files=changed,
        changed_python_files=python_paths,
        changed_test_files=test_paths,
        additions=additions,
        deletions=deletions,
        pytest_scope=pytest_scope,  # type: ignore[arg-type]
        pytest_targets=pytest_targets,
        changed_symbols=sorted(changed_symbols)[:100],
        symbol_impacts=sorted(impacts, key=lambda item: (item.path, item.symbol)),
        covered_unchanged_tests=covered_unchanged_tests[:_MAX_RESULT_TEST_PATHS],
        uncovered_reachable_tests=uncovered_reachable[:_MAX_RESULT_TEST_PATHS],
        uncovered_related_tests=uncovered_related[:_MAX_RESULT_TEST_PATHS],
        analysis_incomplete=analysis_incomplete,
        analysis_notes=sorted(set(analysis_notes))[:_MAX_ANALYSIS_NOTES],
        factors=factors,
        duration_seconds=time.monotonic() - started,
    )
