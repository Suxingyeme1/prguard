"""Command and filesystem policy."""

from __future__ import annotations

import fnmatch
import hashlib
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from prguard.harness.errors import CommandPolicyError
from prguard.schemas import PolicyViolation

_DIRECT_TOOLS = {"pytest", "ruff"}
_PYTHON_TOOLS = {"python", "python3", "python3.12"}
_SHELL_TOKENS = ("&&", "||", "$(`", "$(", "`", ";", "|", ">", "<")


class CommandPolicy:
    """Validate a narrow capability: pytest/ruff argv, exact-task allowlisting."""

    def __init__(self, allowed_commands: list[list[str]]) -> None:
        self.allowed = {tuple(argv) for argv in allowed_commands}
        for argv in allowed_commands:
            self.validate_shape(argv)

    def authorize(self, argv: list[str]) -> list[str]:
        self.validate_shape(argv)
        if tuple(argv) not in self.allowed:
            raise CommandPolicyError("command is not present in the task allowlist")
        if argv[0] in _DIRECT_TOOLS:
            return [sys.executable, "-m", argv[0], *argv[1:]]
        return [sys.executable, *argv[1:]]

    @staticmethod
    def validate_shape(argv: list[str]) -> None:
        if not argv or any(not isinstance(item, str) or not item for item in argv):
            raise CommandPolicyError("command must be a non-empty argv list")
        tool = argv[0]
        if os.path.basename(tool) != tool:
            raise CommandPolicyError("executable must be a bare allowlisted name")
        if tool in _DIRECT_TOOLS:
            module = tool
        elif tool in _PYTHON_TOOLS and len(argv) >= 3 and argv[1] == "-m":
            module = argv[2]
            if module not in _DIRECT_TOOLS:
                raise CommandPolicyError("python -m is limited to pytest and ruff")
        else:
            raise CommandPolicyError("only pytest and ruff command forms are supported")
        if module == "ruff" and len(argv) < (2 if tool == "ruff" else 4):
            raise CommandPolicyError("ruff requires an explicit subcommand")
        for token in argv[1:]:
            if "\x00" in token or any(marker in token for marker in _SHELL_TOKENS):
                raise CommandPolicyError("shell syntax is not accepted in argv")
            candidate = token.split("=", 1)[-1] if "=" in token else token
            path = PurePosixPath(candidate.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise CommandPolicyError(
                    "absolute and parent-traversing command arguments are forbidden"
                )


def protected_path_violations(
    worktree: Path, paths: list[str], patterns: list[str]
) -> list[PolicyViolation]:
    protected = sorted(
        path for path in paths if any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)
    )
    violations: list[PolicyViolation] = []
    if protected:
        violations.append(
            PolicyViolation(
                code="protected_path_modified",
                message="candidate changes include protected paths",
                paths=protected,
            )
        )
    escaped_links: list[str] = []
    root = worktree.resolve()
    for relative in paths:
        candidate = worktree / relative
        if candidate.is_symlink():
            try:
                candidate.resolve(strict=False).relative_to(root)
            except ValueError:
                escaped_links.append(relative)
    if escaped_links:
        violations.append(
            PolicyViolation(
                code="escaping_symlink",
                message="changed symlink resolves outside the isolated worktree",
                paths=sorted(escaped_links),
            )
        )
    return violations


@dataclass(frozen=True)
class FileFingerprint:
    kind: str
    digest: str


def snapshot_tree(root: Path, excluded_names: set[str] | None = None) -> dict[str, FileFingerprint]:
    excluded_names = excluded_names or set()
    result: dict[str, FileFingerprint] = {}
    if not root.exists():
        return result
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        dirs[:] = [name for name in dirs if name not in excluded_names]
        for name in sorted(files):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                result[relative] = FileFingerprint("symlink", os.readlink(path))
            else:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                result[relative] = FileFingerprint("file", digest)
    return result


def snapshot_changes(
    before: dict[str, FileFingerprint], after: dict[str, FileFingerprint]
) -> list[str]:
    return sorted(
        path for path in before.keys() | after.keys() if before.get(path) != after.get(path)
    )


def remove_owned_audit_paths(root: Path, relative_paths: list[str]) -> None:
    """Remove detected writes only from the harness-owned run directory."""
    resolved_root = root.resolve()
    parents: set[Path] = set()
    for relative in relative_paths:
        candidate = root / relative
        try:
            candidate.parent.resolve().relative_to(resolved_root)
        except ValueError:
            continue
        if candidate.is_symlink() or candidate.is_file():
            candidate.unlink(missing_ok=True)
        elif candidate.is_dir():
            shutil.rmtree(candidate)
        parents.add(candidate.parent)
    for parent in sorted(parents, key=lambda value: len(value.parts), reverse=True):
        while parent != root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
