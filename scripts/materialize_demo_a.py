"""Materialize the frozen Humanize #366 live Demo A task."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

UPSTREAM_URL = "https://github.com/python-humanize/humanize.git"
UPSTREAM_COMMIT = "ce4147b6c8f8a132f772be0929d58305eb22c5d9"
EVALUATION_COMMIT = "431dbbed77d867519447e02eebf1a14879b80603"
EVALUATION_DATE = "2026-08-19T18:10:23+08:00"


def _git(*argv: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        ["git", *argv],
        cwd=cwd,
        env=env,
        check=True,
        shell=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def materialize(output: Path, source: str = UPSTREAM_URL) -> Path:
    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing Demo A directory: {output}")
    output.mkdir(parents=True)
    repository = output / "repo"
    patch = (
        Path(__file__).resolve().parents[1]
        / "benchmark"
        / "demo-a"
        / "humanize-366-evaluation.patch"
    )

    _git("clone", "--no-hardlinks", "--no-checkout", source, str(repository))
    _git("checkout", "--detach", UPSTREAM_COMMIT, cwd=repository)
    _git("apply", "--index", str(patch), cwd=repository)
    commit_env = os.environ.copy()
    commit_env.update(
        {
            "GIT_AUTHOR_DATE": EVALUATION_DATE,
            "GIT_COMMITTER_DATE": EVALUATION_DATE,
        }
    )
    _git(
        "-c",
        "user.name=PRGuard Evaluation",
        "-c",
        "user.email=prguard-eval@users.noreply.github.com",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "test: add public reproduction for issue 366",
        cwd=repository,
        env=commit_env,
    )
    actual_commit = _git("rev-parse", "HEAD", cwd=repository)
    if actual_commit != EVALUATION_COMMIT:
        raise RuntimeError(
            f"evaluation Base Commit mismatch: expected {EVALUATION_COMMIT}, got {actual_commit}"
        )

    task = {
        "schema_version": "1.0.0",
        "case_id": "demo-a-humanize-366",
        "repository": str(repository),
        "base_commit": EVALUATION_COMMIT,
        "issue": (
            "humanize.naturalsize() should support a custom numeric format string that contains "
            "surrounding text. Reproduction: naturalsize(999_999, gnu=True, "
            'format="Size: %.1f") currently raises ValueError. Expected result: "Size: 976.6K". '
            "Preserve the existing behavior of ordinary format strings and GNU suffixes."
        ),
        "commands": [
            {"argv": ["pytest", "-q", "tests/test_prguard_issue_366.py"], "kind": "pytest"},
            {"argv": ["pytest", "-q", "tests/test_filesize.py"], "kind": "pytest"},
            {"argv": ["ruff", "check", "src/humanize/filesize.py"], "kind": "lint"},
        ],
        "allowed_commands": [
            ["pytest", "-q", "tests/test_prguard_issue_366.py"],
            ["pytest", "-q", "tests/test_filesize.py"],
            ["ruff", "check", "src/humanize/filesize.py"],
        ],
        "writable_paths": ["src/humanize/filesize.py"],
        "protected_paths": ["tests/**", ".github/**", "pyproject.toml", "uv.lock", "LICENSE*"],
        "command_timeout_seconds": 120,
        "task_timeout_seconds": 500,
        "max_output_bytes": 300000,
        "max_tool_calls": 30,
        "max_file_bytes": 200000,
        "max_context_bytes": 500000,
        "max_patch_bytes": 100000,
        "max_changed_files": 2,
        "max_repair_attempts": 1,
    }
    task_path = output / "task.json"
    task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    print(f"Demo A materialized at {output}")
    print(f"Base Commit verified: {actual_commit}")
    print(f"Task: {task_path}")
    return task_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("work/demo-a-humanize-366"))
    parser.add_argument(
        "--source",
        default=UPSTREAM_URL,
        help="Git URL or local Humanize clone (default: frozen upstream GitHub repository)",
    )
    args = parser.parse_args()
    materialize(args.output, args.source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
