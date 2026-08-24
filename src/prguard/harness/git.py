"""Git repository and detached-worktree operations."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from prguard.harness.errors import PreflightError


@dataclass(frozen=True)
class GitResult:
    returncode: int
    stdout: str
    stderr: str


def run_git(repo: Path, *args: str, timeout: float = 30) -> GitResult:
    try:
        completed = subprocess.run(
            ["git", "-C", os.fspath(repo), *args],
            check=False,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C"},
        )
    except subprocess.TimeoutExpired as exc:
        raise PreflightError(f"Git command timed out: {args[0] if args else 'git'}") from exc
    return GitResult(completed.returncode, completed.stdout, completed.stderr)


class GitRepository:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()

    @staticmethod
    def _timeout(deadline: float | None) -> float:
        if deadline is None:
            return 30
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PreflightError("task deadline expired during Git preflight")
        return min(30, remaining)

    def preflight(self, base_commit: str, *, deadline: float | None = None) -> str:
        if not self.path.is_dir():
            raise PreflightError(f"repository does not exist: {self.path}")
        top = run_git(self.path, "rev-parse", "--show-toplevel", timeout=self._timeout(deadline))
        if top.returncode != 0:
            raise PreflightError(f"not a Git repository: {top.stderr.strip()}")
        if Path(top.stdout.strip()).resolve() != self.path:
            raise PreflightError("repository must identify the Git toplevel")
        resolved = run_git(
            self.path,
            "rev-parse",
            "--verify",
            f"{base_commit}^{{commit}}",
            timeout=self._timeout(deadline),
        )
        if resolved.returncode != 0:
            raise PreflightError(f"base commit is not resolvable: {base_commit}")
        status = run_git(
            self.path,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            timeout=self._timeout(deadline),
        )
        if status.returncode != 0:
            raise PreflightError(f"unable to inspect source checkout: {status.stderr.strip()}")
        if status.stdout.strip():
            raise PreflightError("source repository must be clean before creating a worktree")
        return resolved.stdout.strip()

    def add_worktree(
        self, destination: Path, commit: str, *, deadline: float | None = None
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = run_git(
            self.path,
            "worktree",
            "add",
            "--detach",
            "--no-checkout",
            os.fspath(destination),
            commit,
            timeout=self._timeout(deadline),
        )
        if result.returncode != 0:
            raise PreflightError(f"unable to create worktree: {result.stderr.strip()}")
        checkout = run_git(
            destination, "checkout", "--detach", commit, timeout=self._timeout(deadline)
        )
        if checkout.returncode != 0:
            self.remove_worktree(destination)
            raise PreflightError(f"unable to checkout base commit: {checkout.stderr.strip()}")

    def remove_worktree(self, destination: Path) -> None:
        result = run_git(self.path, "worktree", "remove", "--force", os.fspath(destination))
        if result.returncode != 0:
            # A hostile command may remove the directory while leaving Git's registration.
            pruned = run_git(self.path, "worktree", "prune", "--expire", "now")
            if destination.exists() or pruned.returncode != 0:
                raise PreflightError(f"unable to remove worktree: {result.stderr.strip()}")


def apply_patch(
    worktree: Path, patch_path: Path, *, deadline: float | None = None
) -> tuple[bool, str]:
    timeout = GitRepository._timeout(deadline)
    checked = run_git(worktree, "apply", "--check", "--", os.fspath(patch_path), timeout=timeout)
    if checked.returncode != 0:
        return False, checked.stderr.strip()
    applied = run_git(
        worktree,
        "apply",
        "--whitespace=nowarn",
        "--",
        os.fspath(patch_path),
        timeout=GitRepository._timeout(deadline),
    )
    if applied.returncode != 0:
        return False, applied.stderr.strip()
    return True, ""


def changed_files(worktree: Path, *, deadline: float | None = None) -> list[str]:
    result = run_git(
        worktree,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        timeout=GitRepository._timeout(deadline),
    )
    if result.returncode != 0:
        raise PreflightError(f"unable to inspect worktree: {result.stderr.strip()}")
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.add(value.strip('"'))
    return sorted(paths)


def final_diff(
    worktree: Path,
    base_commit: str,
    *,
    deadline: float | None = None,
    excluded_paths: list[str] | None = None,
) -> str:
    # Intent-to-add makes untracked files visible to git diff without staging their contents.
    intent = run_git(
        worktree,
        "add",
        "--intent-to-add",
        "--",
        ".",
        timeout=GitRepository._timeout(deadline),
    )
    if intent.returncode != 0:
        raise PreflightError(f"unable to prepare final diff: {intent.stderr.strip()}")
    pathspecs = ["."]
    pathspecs.extend(f":(exclude,literal){path}" for path in excluded_paths or [])
    result = run_git(
        worktree,
        "diff",
        "--binary",
        "--no-ext-diff",
        base_commit,
        "--",
        *pathspecs,
        timeout=GitRepository._timeout(deadline),
    )
    if result.returncode != 0:
        raise PreflightError(f"unable to capture final diff: {result.stderr.strip()}")
    return result.stdout
