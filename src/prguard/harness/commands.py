"""Bounded, no-shell command execution."""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from contextlib import suppress
from pathlib import Path

from prguard.harness.policy import CommandPolicy
from prguard.schemas import CommandSpec, VerificationResult


def _read_bounded(path: Path, limit: int) -> tuple[str, bool]:
    size = path.stat().st_size
    with path.open("rb") as stream:
        data = stream.read(limit)
    return data.decode("utf-8", errors="replace"), size > limit


class CommandExecutor:
    def __init__(
        self,
        *,
        worktree: Path,
        runtime_directory: Path,
        policy: CommandPolicy,
        default_timeout: float,
        max_output_bytes: int,
        task_deadline: float,
    ) -> None:
        self.worktree = worktree
        self.runtime_directory = runtime_directory
        self.policy = policy
        self.default_timeout = default_timeout
        self.max_output_bytes = max_output_bytes
        self.task_deadline = task_deadline

    def execute(self, index: int, spec: CommandSpec) -> VerificationResult:
        effective_argv = self.policy.authorize(spec.argv)
        remaining = self.task_deadline - time.monotonic()
        requested_timeout = spec.timeout_seconds or self.default_timeout
        timeout = max(0.0, min(requested_timeout, remaining))
        if timeout == 0:
            return VerificationResult(
                command_index=index,
                kind=spec.kind,
                argv=spec.argv,
                exit_code=None,
                timed_out=True,
                duration_seconds=0,
                stderr="task deadline exhausted before command launch",
                passed=False,
            )
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.fspath(self.runtime_directory / "home"),
            "TMPDIR": os.fspath(self.runtime_directory / "tmp"),
            "LC_ALL": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
        started = time.monotonic()
        with tempfile.NamedTemporaryFile(dir=self.runtime_directory, delete=False) as stdout_file:
            stdout_path = Path(stdout_file.name)
            with tempfile.NamedTemporaryFile(
                dir=self.runtime_directory, delete=False
            ) as stderr_file:
                stderr_path = Path(stderr_file.name)
                process = subprocess.Popen(
                    effective_argv,
                    cwd=self.worktree,
                    env=env,
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    start_new_session=True,
                )
                timed_out = False
                try:
                    exit_code = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                        process.wait(timeout=1)
                    except (ProcessLookupError, subprocess.TimeoutExpired):
                        with suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    exit_code = None
        duration = time.monotonic() - started
        stdout, stdout_truncated = _read_bounded(stdout_path, self.max_output_bytes)
        stderr, stderr_truncated = _read_bounded(stderr_path, self.max_output_bytes)
        stdout_path.unlink(missing_ok=True)
        stderr_path.unlink(missing_ok=True)
        return VerificationResult(
            command_index=index,
            kind=spec.kind,
            argv=spec.argv,
            exit_code=exit_code,
            timed_out=timed_out,
            duration_seconds=duration,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            passed=not timed_out and exit_code == 0,
        )
