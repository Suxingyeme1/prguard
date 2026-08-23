"""Materialize one immutable public GitHub checkout without executing repository hooks."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from prguard.onboarding.errors import OnboardingError
from prguard.schemas import GitHubIssueSnapshot

_SAFE_SLUG = re.compile(r"[^A-Za-z0-9._-]+")


def checkout_name(snapshot: GitHubIssueSnapshot) -> str:
    raw = (
        f"{snapshot.reference.owner}-{snapshot.reference.repository}-"
        f"{snapshot.base_commit[:12]}"
    )
    return _SAFE_SLUG.sub("-", raw).strip("-")


def _canonical_github_remote(value: str) -> str:
    return value.removesuffix(".git").removesuffix("/").lower()


def _verified_fetch_source(
    snapshot: GitHubIssueSnapshot, source_repository: Path | None
) -> str:
    if source_repository is None:
        return snapshot.clone_url
    source = source_repository.expanduser().resolve()
    if not (source / ".git").is_dir():
        raise OnboardingError("source repository cache is not a Git working tree")
    try:
        completed = subprocess.run(
            ["git", "-C", os.fspath(source), "remote", "get-url", "origin"],
            check=False,
            shell=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "LC_ALL": "C",
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_SYSTEM": os.devnull,
            },
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OnboardingError("could not validate source repository cache") from exc
    if completed.returncode != 0:
        raise OnboardingError("source repository cache has no readable origin remote")
    if _canonical_github_remote(completed.stdout.strip()) != _canonical_github_remote(
        snapshot.repository_url
    ):
        raise OnboardingError(
            "source repository cache origin does not match the GitHub Issue repository"
        )
    return os.fspath(source)


def materialize_public_checkout(
    snapshot: GitHubIssueSnapshot,
    root: Path,
    *,
    source_repository: Path | None = None,
) -> Path:
    root = root.expanduser().resolve()
    fetch_source = _verified_fetch_source(snapshot, source_repository)
    fetch_options = ["--depth=1", "--no-tags"]
    if source_repository is None:
        fetch_options.insert(1, "--filter=blob:none")
    root.mkdir(parents=True, exist_ok=True)
    destination = root / checkout_name(snapshot)
    if destination.exists():
        raise OnboardingError(f"checkout destination already exists: {destination}")
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LC_ALL": "C",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    }
    def run(argv: list[str], timeout: float = 120) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                argv,
                check=False,
                shell=False,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OnboardingError(f"Git materialization failed: {type(exc).__name__}") from exc

    destination.mkdir()
    commands = [
        ["git", "-c", "core.hooksPath=/dev/null", "init", "--template=", os.fspath(destination)],
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-C",
            os.fspath(destination),
            "remote",
            "add",
            "origin",
            snapshot.clone_url,
        ],
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-C",
            os.fspath(destination),
            "fetch",
            *fetch_options,
            fetch_source,
            snapshot.base_commit,
        ],
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-C",
            os.fspath(destination),
            "checkout",
            "--detach",
            "FETCH_HEAD",
            "--",
        ],
    ]
    try:
        for command in commands:
            completed = run(command)
            if completed.returncode != 0:
                raise OnboardingError(
                    f"Git materialization failed: {completed.stderr.strip()}"
                )
        resolved = run(
            ["git", "-C", os.fspath(destination), "rev-parse", "HEAD"], timeout=30
        )
        if resolved.returncode != 0 or resolved.stdout.strip() != snapshot.base_commit:
            raise OnboardingError("materialized checkout does not match the frozen Base Commit")
        status = run(
            ["git", "-C", os.fspath(destination), "status", "--porcelain=v1"], timeout=30
        )
        if status.returncode != 0 or status.stdout.strip():
            raise OnboardingError("materialized checkout is not clean")
    except OnboardingError:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return destination
