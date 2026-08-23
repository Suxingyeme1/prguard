"""Deterministic, fail-closed discovery of a Python repository execution profile."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

from prguard.harness.errors import CommandPolicyError
from prguard.harness.policy import CommandPolicy
from prguard.implementer.errors import RepositoryAccessError
from prguard.implementer.tools import RepositoryTools
from prguard.onboarding.errors import ProjectDiscoveryError
from prguard.schemas import (
    CommandSpec,
    DiscoveredProjectPolicy,
    ProjectConfig,
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


def load_project_config(repository: Path) -> tuple[ProjectConfig | None, Path | None]:
    path = repository / ".prguard.toml"
    if not path.is_file():
        return None, None
    if path.is_symlink() or path.stat().st_size > 100_000:
        raise ProjectDiscoveryError(".prguard.toml must be a small regular file")
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
        config = ProjectConfig.model_validate(payload)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, ValidationError) as exc:
        raise ProjectDiscoveryError(f"invalid .prguard.toml: {exc}") from exc
    return config, path


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
) -> list[list[str]]:
    tool = pyproject.get("tool")
    tool = tool if isinstance(tool, dict) else {}
    commands: list[list[str]] = []
    if (repository / "tests").is_dir() or "pytest" in tool or (
        repository / "pytest.ini"
    ).is_file():
        commands.append(["pytest", "-q", *pytest_targets])
    if "ruff" in tool:
        commands.append(["ruff", "check", "."])
    return commands


def _issue_identifiers(issue: str) -> list[str]:
    weighted: dict[str, int] = {}
    patterns = (
        (r"`([A-Za-z_][A-Za-z0-9_]*)\s*\(", 5),
        (r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", 3),
        (r"`([A-Za-z_][A-Za-z0-9_]*)`", 2),
    )
    ignored = {"assert", "float", "format", "import", "print", "str"}
    for pattern, weight in patterns:
        for value in re.findall(pattern, issue):
            if value.casefold() not in ignored:
                weighted[value] = weighted.get(value, 0) + weight
    return [
        value
        for value, _ in sorted(
            weighted.items(), key=lambda item: (-item[1], item[0].casefold())
        )[:12]
    ]


def _discover_issue_test_targets(repository: Path, issue: str | None) -> list[str]:
    if not issue:
        return []
    limits = SimpleNamespace(max_file_bytes=100_000, max_context_bytes=2_000_000)
    tools = RepositoryTools(repository, limits)
    candidates: list[tuple[int, str]] = []
    try:
        for identifier in _issue_identifiers(issue):
            symbols = tools.find_symbols(identifier, 30)["symbols"]
            exact_sources = [
                item
                for item in symbols
                if str(item["name"]).casefold() == identifier.casefold()
                and not str(item["path"]).startswith(("test/", "tests/"))
                and not Path(str(item["path"])).name.startswith("test_")
            ]
            for symbol in exact_sources[:3]:
                related = tools.find_related_tests(str(symbol["path"]), 5)["tests"]
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
                '__version__ = "0+prguard"\n'
                '__version_tuple__ = (0, "prguard")\n'
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
    repository: Path, *, issue: str | None = None
) -> DiscoveredProjectPolicy:
    repository = repository.expanduser().resolve()
    pyproject = _load_pyproject(repository)
    runtime_files = _discover_runtime_files(repository, pyproject)
    config, _ = load_project_config(repository)
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
            source="repository_config",
            command_timeout_seconds=config.command_timeout_seconds,
            task_timeout_seconds=config.task_timeout_seconds,
            max_repair_attempts=config.max_repair_attempts,
            runtime_files=runtime_files,
            warnings=[
                "Repository-owned policy was accepted within PRGuard's fixed command and "
                "protected-path constraints."
            ],
        )
    pytest_targets = _discover_issue_test_targets(repository, issue)
    command_values = _discover_commands(repository, pyproject, pytest_targets)
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
                    "Pytest was narrowed to Issue-related public tests; use a reviewed "
                    ".prguard.toml when a wider gate is required."
                ]
                if pytest_targets
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
