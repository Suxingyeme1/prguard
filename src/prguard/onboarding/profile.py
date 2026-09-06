"""Deterministic, fail-closed discovery of a Python repository execution profile."""

from __future__ import annotations

import json
import os
import re
import tomllib
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

from prguard.harness.errors import CommandPolicyError, PreflightError
from prguard.harness.git import GitRepository
from prguard.harness.policy import CommandPolicy
from prguard.implementer.errors import RepositoryAccessError
from prguard.implementer.tools import RepositoryTools
from prguard.onboarding.errors import ProjectDiscoveryError
from prguard.schemas import (
    CommandSpec,
    DiscoveredProjectPolicy,
    ProjectConfig,
    ProjectPolicyInspection,
    RuntimeFileSpec,
)

DEFAULT_PROTECTED_PATHS = (
    ".git/**",
    ".github/**",
    ".prguard.toml",
    ".env",
    ".env.*",
    "**/*.pem",
    "**/*.key",
    "**/*.p12",
    "**/*.pfx",
    "**/credentials.json",
)
_TEST_SCAN_EXCLUDED = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "build",
    "dist",
    "docs",
    "examples",
    "node_modules",
    "site-packages",
    "venv",
}
_MAX_TEST_SCAN_FILES = 10_000
_MAX_TEST_SCAN_DEPTH = 6


def render_project_config(config: ProjectConfig) -> str:
    """Render a deterministic, reviewable `.prguard.toml` candidate."""

    def value(item: object) -> str:
        return json.dumps(item, ensure_ascii=False, separators=(", ", ": "))

    return "\n".join(
        (
            "# Generated as a review candidate; commit only after checking every scope and gate.",
            f"version = {config.version}",
            f"verification_commands = {value(config.verification_commands)}",
            f"writable_paths = {value(config.writable_paths)}",
            f"protected_paths = {value(config.protected_paths)}",
            f"command_timeout_seconds = {config.command_timeout_seconds:g}",
            f"task_timeout_seconds = {config.task_timeout_seconds:g}",
            f"max_repair_attempts = {config.max_repair_attempts}",
            "",
        )
    )


def _load_project_config_path(path: Path, *, label: str) -> ProjectConfig:
    if not path.is_file():
        raise ProjectDiscoveryError(f"{label} must be a regular file")
    if path.is_symlink() or path.stat().st_size > 100_000:
        raise ProjectDiscoveryError(f"{label} must be a small regular non-symlink file")
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
        return ProjectConfig.model_validate(payload)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, ValidationError) as exc:
        raise ProjectDiscoveryError(f"invalid {label}: {exc}") from exc


def load_project_config(repository: Path) -> tuple[ProjectConfig | None, Path | None]:
    path = repository / ".prguard.toml"
    if not path.is_file():
        return None, None
    return _load_project_config_path(path, label=".prguard.toml"), path


def load_operator_project_config(path: Path) -> ProjectConfig:
    """Load one explicitly selected policy without trusting repository code."""

    supplied = path.expanduser()
    if supplied.is_symlink():
        raise ProjectDiscoveryError(
            "operator policy must be a small regular non-symlink file"
        )
    return _load_project_config_path(
        supplied.resolve(strict=False),
        label="operator policy",
    )


def _command_kind(argv: list[str]) -> str:
    if argv[0] in {"pytest", "ruff"}:
        return argv[0]
    return argv[2]


def _validate_commands(values: list[list[str]]) -> list[CommandSpec]:
    try:
        CommandPolicy(values)
    except CommandPolicyError as exc:
        raise ProjectDiscoveryError(f"unsafe verification command: {exc}") from exc
    return [CommandSpec(argv=argv, kind=_command_kind(argv)) for argv in values]


def _load_pyproject(repository: Path) -> dict[str, object]:
    path = repository / "pyproject.toml"
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 1_000_000:
        return {}
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _discover_commands(
    repository: Path,
    pyproject: dict[str, object],
    pytest_targets: list[str],
    nested_test_roots: list[str],
) -> list[list[str]]:
    tool = pyproject.get("tool")
    tool = tool if isinstance(tool, dict) else {}
    commands: list[list[str]] = []
    if (repository / "tests").is_dir() or "pytest" in tool or (repository / "pytest.ini").is_file():
        commands.append(["pytest", "-q", *pytest_targets])
    elif len(nested_test_roots) == 1:
        root = nested_test_roots[0]
        scoped_targets = [
            target
            for target in pytest_targets
            if target == root or target.startswith(f"{root}/")
        ]
        commands.append(["pytest", "-q", *(scoped_targets or [root])])
    return commands


def _discover_nested_python_test_roots(repository: Path) -> list[str]:
    """Find one bounded non-standard pytest root without inspecting repository config code."""

    roots: set[Path] = set()
    scanned = 0
    for current, directories, files in os.walk(repository, topdown=True, followlinks=False):
        current_path = Path(current)
        relative = current_path.relative_to(repository)
        depth = len(relative.parts)
        directories[:] = sorted(
            name
            for name in directories
            if name not in _TEST_SCAN_EXCLUDED
            and not name.startswith(".")
            and not (current_path / name).is_symlink()
            and depth < _MAX_TEST_SCAN_DEPTH
        )
        scanned += len(files)
        if scanned > _MAX_TEST_SCAN_FILES:
            return []
        if not any(
            name.endswith(".py")
            and (name.startswith("test_") or name.endswith("_test.py"))
            for name in files
        ):
            continue
        test_indices = [
            index for index, part in enumerate(relative.parts) if part in {"test", "tests"}
        ]
        if test_indices:
            roots.add(Path(*relative.parts[: test_indices[0] + 1]))
    collapsed: list[Path] = []
    for candidate in sorted(roots, key=lambda value: (len(value.parts), value.as_posix())):
        if not any(candidate.is_relative_to(parent) for parent in collapsed):
            collapsed.append(candidate)
    return [path.as_posix() for path in collapsed]


def _issue_identifiers(issue: str) -> list[str]:
    weighted: dict[str, int] = {}
    headline = next((line for line in issue.splitlines() if line.strip()), "")
    scoped_patterns = (
        (issue, r"`([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)(?:\(\))?`", 7),
        (headline, r"\b([A-Za-z_][A-Za-z0-9_]*\.__[A-Za-z0-9_]+__)\b", 12),
        (headline, r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", 5),
    )
    ignored = {"assert", "float", "format", "import", "print", "str"}
    for scope, pattern, weight in scoped_patterns:
        for value in re.findall(pattern, scope):
            if value.casefold() not in ignored:
                weighted[value] = weighted.get(value, 0) + weight
    return [
        value
        for value, _ in sorted(weighted.items(), key=lambda item: (-item[1], item[0].casefold()))[
            :12
        ]
    ]


def _discover_issue_test_targets(repository: Path, issue: str | None) -> list[str]:
    if not issue:
        return []
    limits = SimpleNamespace(max_file_bytes=250_000, max_context_bytes=2_000_000)
    tools = RepositoryTools(repository, limits)
    candidates: list[tuple[int, str]] = []
    try:
        for identifier in _issue_identifiers(issue):
            symbols = tools.find_symbols(identifier, 30)["symbols"]
            leaf = identifier.rsplit(".", 1)[-1]
            exact_sources = [
                item
                for item in symbols
                if str(item["name"]).casefold() == leaf.casefold()
                and (
                    "." not in identifier
                    or str(item["qualified_name"]).casefold().endswith(
                        identifier.casefold()
                    )
                )
                and not str(item["path"]).startswith(("test/", "tests/"))
                and not Path(str(item["path"])).name.startswith("test_")
            ]
            if len(exact_sources) != 1:
                continue
            for symbol in exact_sources:
                related = tools.find_related_tests(str(symbol["qualified_name"]), 5)["tests"]
                for test in related:
                    candidates.append((int(test["score"]), str(test["path"])))
    except RepositoryAccessError:
        return []
    if not candidates:
        return []
    best_by_path: dict[str, int] = {}
    for score, path in candidates:
        best_by_path[path] = max(score, best_by_path.get(path, 0))
    ranked = sorted(best_by_path.items(), key=lambda item: (-item[1], item[0]))
    best_score = ranked[0][1]
    return [path for path, score in ranked if score == best_score][:3]


def _discover_runtime_files(
    repository: Path, pyproject: dict[str, object]
) -> list[RuntimeFileSpec]:
    tool = pyproject.get("tool")
    hatch = tool.get("hatch") if isinstance(tool, dict) else None
    build = hatch.get("build") if isinstance(hatch, dict) else None
    hooks = build.get("hooks") if isinstance(build, dict) else None
    vcs = hooks.get("vcs") if isinstance(hooks, dict) else None
    value = vcs.get("version-file") if isinstance(vcs, dict) else None
    if not isinstance(value, str) or not value.endswith(".py"):
        return []
    try:
        spec = RuntimeFileSpec(
            path=value,
            content=(
                '"""Runtime-only version scaffold generated by PRGuard."""\n\n'
                '__version__ = "0.0.0"\n'
                "__version_tuple__ = (0, 0, 0)\n"
                "version = __version__\n"
                "version_tuple = __version_tuple__\n"
            ),
            reason="hatch_vcs_version_file",
        )
        candidate = (repository / spec.path).resolve(strict=False)
        candidate.relative_to(repository.resolve())
    except (ValueError, OSError):
        return []
    if candidate.exists() or candidate.is_symlink():
        return []
    return [spec]


def _discover_writable_paths(repository: Path) -> list[str]:
    patterns: list[str] = []
    for directory in ("src", "tests", "test"):
        if (repository / directory).is_dir():
            patterns.append(f"{directory}/**")
    excluded = {
        "benchmark",
        "build",
        "dist",
        "docs",
        "examples",
        "scripts",
        "test",
        "tests",
    }
    if "src/**" not in patterns:
        for child in sorted(repository.iterdir(), key=lambda item: item.name):
            if (
                child.is_dir()
                and not child.is_symlink()
                and child.name not in excluded
                and not child.name.startswith(".")
                and (child / "__init__.py").is_file()
            ):
                patterns.append(f"{child.name}/**")
    if any(path.is_file() for path in repository.glob("*.py")):
        patterns.append("*.py")
    return sorted(set(patterns))


def discover_project_policy(
    repository: Path,
    *,
    issue: str | None = None,
    operator_config: ProjectConfig | None = None,
) -> DiscoveredProjectPolicy:
    repository = repository.expanduser().resolve()
    pyproject = _load_pyproject(repository)
    tool_config = pyproject.get("tool")
    ruff_configured = isinstance(tool_config, dict) and "ruff" in tool_config
    runtime_files = _discover_runtime_files(repository, pyproject)
    repository_config, _ = load_project_config(repository)
    if repository_config is not None and operator_config is not None:
        raise ProjectDiscoveryError(
            "operator policy cannot override repository-owned .prguard.toml"
        )
    config = operator_config or repository_config
    if config is not None:
        commands = _validate_commands(config.verification_commands)
        protected = sorted(
            set(DEFAULT_PROTECTED_PATHS)
            | set(config.protected_paths)
            | {item.path for item in runtime_files}
        )
        return DiscoveredProjectPolicy(
            commands=commands,
            writable_paths=config.writable_paths,
            protected_paths=protected,
            source="operator_config" if operator_config is not None else "repository_config",
            command_timeout_seconds=config.command_timeout_seconds,
            task_timeout_seconds=config.task_timeout_seconds,
            max_repair_attempts=config.max_repair_attempts,
            runtime_files=runtime_files,
            warnings=[
                f"{'Operator-supplied' if operator_config is not None else 'Repository-owned'} "
                "policy was accepted within PRGuard's fixed command and protected-path "
                "constraints."
            ],
        )
    pytest_targets = _discover_issue_test_targets(repository, issue)
    nested_test_roots = _discover_nested_python_test_roots(repository)
    command_values = _discover_commands(
        repository,
        pyproject,
        pytest_targets,
        nested_test_roots,
    )
    if not command_values:
        raise ProjectDiscoveryError(
            "no safe pytest/Ruff command was discovered; add a reviewed .prguard.toml"
        )
    writable_paths = _discover_writable_paths(repository)
    if not writable_paths:
        raise ProjectDiscoveryError(
            "no conservative Python source/test write scope was discovered; "
            "add a reviewed .prguard.toml"
        )
    return DiscoveredProjectPolicy(
        commands=_validate_commands(command_values),
        writable_paths=writable_paths,
        protected_paths=sorted(
            set(DEFAULT_PROTECTED_PATHS) | {item.path for item in runtime_files}
        ),
        source="deterministic_discovery",
        runtime_files=runtime_files,
        warnings=[
            "Verification commands and writable paths were inferred conservatively; inspect the "
            "generated Task before execution.",
            "Dependency installation and external services are not inferred or executed.",
            *(
                [
                    "Ruff configuration was detected but not treated as a repository gate; "
                    "declare `ruff check --no-fix` in a reviewed .prguard.toml to enable it."
                ]
                if ruff_configured
                else []
            ),
            *(
                [
                    "Pytest was narrowed to Issue-related public tests; use a reviewed "
                    ".prguard.toml when a wider gate is required."
                ]
                if pytest_targets
                else []
            ),
            *(
                [
                    f"Pytest uses the uniquely discovered nested test root "
                    f"{nested_test_roots[0]!r}; review and freeze it in .prguard.toml."
                ]
                if len(nested_test_roots) == 1 and not (repository / "tests").is_dir()
                else []
            ),
            *(
                [
                    "A declared Hatch VCS version file will be generated only inside "
                    "verification worktrees and excluded from the delivered Patch."
                ]
                if runtime_files
                else []
            ),
        ],
    )


def inspect_project_policy(
    repository: Path,
    *,
    issue: str | None = None,
    base_commit: str = "HEAD",
    operator_config: ProjectConfig | None = None,
    operator_config_path: Path | None = None,
) -> ProjectPolicyInspection:
    """Explain policy discovery without invoking a provider or executing repository code."""

    repository = repository.expanduser().resolve()
    try:
        resolved = GitRepository(repository).preflight(base_commit)
    except PreflightError as exc:
        raise ProjectDiscoveryError(f"repository preflight failed: {exc}") from exc

    signals: list[str] = []
    if (repository / ".prguard.toml").is_file():
        signals.append("repository .prguard.toml present")
    if (repository / "pyproject.toml").is_file():
        signals.append("pyproject.toml present")
    nested_test_roots = _discover_nested_python_test_roots(repository)
    if (repository / "pytest.ini").is_file() or (repository / "tests").is_dir():
        signals.append("pytest-compatible test layout detected")
    elif len(nested_test_roots) == 1:
        signals.append(f"unique nested Python test root detected: {nested_test_roots[0]}")
    elif len(nested_test_roots) > 1:
        signals.append("multiple nested Python test roots require reviewed configuration")
    discovered_scopes = _discover_writable_paths(repository)
    if discovered_scopes:
        signals.append("Python source/test write scopes detected")
    if issue and _issue_identifiers(issue):
        signals.append("Issue contains source-like identifiers for test targeting")

    repository_config_path = repository / ".prguard.toml"
    config_path = repository_config_path if repository_config_path.is_file() else None
    if operator_config is not None:
        signals.append("operator policy supplied explicitly")
        if operator_config_path is not None:
            config_path = operator_config_path.expanduser().resolve()
    try:
        policy = discover_project_policy(
            repository,
            issue=issue,
            operator_config=operator_config,
        )
    except ProjectDiscoveryError as exc:
        if repository_config_path.is_file():
            config_path = repository_config_path
        reason = str(exc)
        actions = []
        if "pytest/Ruff command" in reason:
            actions.append(
                "Choose an existing pytest or non-mutating Ruff gate and declare it in "
                ".prguard.toml; PRGuard will not invent a command."
            )
        if "source/test write scope" in reason:
            actions.append(
                "Declare the smallest repository-relative source and test globs in .prguard.toml."
            )
        if config_path is not None:
            actions.append("Correct the existing .prguard.toml and rerun inspect-policy.")
        if not actions:
            actions.append("Add and review a versioned .prguard.toml, then rerun inspect-policy.")
        return ProjectPolicyInspection(
            repository=repository,
            requested_base_commit=base_commit,
            base_commit=resolved,
            status="needs_config",
            config_path=config_path,
            writable_paths=discovered_scopes,
            protected_paths=list(DEFAULT_PROTECTED_PATHS),
            signals=signals,
            blocking_reasons=[reason],
            next_actions=actions,
        )

    if policy.source == "repository_config":
        config, _ = load_project_config(repository)
        assert config is not None
    elif policy.source == "operator_config":
        assert operator_config is not None
        config = operator_config
    else:
        config = ProjectConfig(
            verification_commands=[command.argv for command in policy.commands],
            writable_paths=policy.writable_paths,
            command_timeout_seconds=policy.command_timeout_seconds,
            task_timeout_seconds=policy.task_timeout_seconds,
            max_repair_attempts=policy.max_repair_attempts,
        )
    return ProjectPolicyInspection(
        repository=repository,
        requested_base_commit=base_commit,
        base_commit=resolved,
        status="ready",
        config_path=config_path,
        policy_source=policy.source,
        commands=policy.commands,
        writable_paths=policy.writable_paths,
        protected_paths=policy.protected_paths,
        runtime_files=policy.runtime_files,
        signals=signals,
        warnings=policy.warnings,
        next_actions=[
            "Review suggested_config and commit it as .prguard.toml to freeze inferred policy."
        ]
        if policy.source == "deterministic_discovery"
        else [],
        suggested_config=render_project_config(config),
    )
