"""Bounded, no-shell command execution."""

from __future__ import annotations

import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path

from prguard.harness.errors import PreflightError
from prguard.harness.policy import CommandPolicy
from prguard.schemas import (
    CommandSpec,
    ContainerExecutionSpec,
    ExecutionBackend,
    RuntimeIdentity,
    VerificationResult,
)

_CONTAINER_STARTUP_MARKER = "__PRGUARD_CONTAINER_PYTHON_STARTED__\n"
_CONTAINER_RUNTIME_MARKER = "__PRGUARD_CONTAINER_RUNTIME__="
_CONTAINER_STARTUP_WRAPPER = (
    "import json,os,platform,sys;"
    f"os.write(2,{_CONTAINER_STARTUP_MARKER.encode()!r});"
    "identity={'implementation':sys.implementation.name,"
    "'version':platform.python_version(),"
    "'cache_tag':sys.implementation.cache_tag,"
    "'platform':sys.platform,"
    "'architecture':platform.machine() or 'unknown',"
    "'executable_name':os.path.basename(sys.executable),"
    "'provenance':'container_process'};"
    f"os.write(2,({_CONTAINER_RUNTIME_MARKER!r}+json.dumps(identity,sort_keys=True,"
    "separators=(',',':'))+'\\n').encode());"
    "os.execv(sys.executable,[sys.executable,*sys.argv[1:]])"
)


def _host_runtime_identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        implementation=sys.implementation.name,
        version=platform.python_version(),
        cache_tag=sys.implementation.cache_tag,
        platform=sys.platform,
        architecture=platform.machine() or "unknown",
        executable_name=os.path.basename(sys.executable),
        provenance="host_process",
    )


def _extract_container_runtime(stderr: str) -> tuple[str, RuntimeIdentity | None]:
    lines = stderr.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.startswith(_CONTAINER_RUNTIME_MARKER):
            continue
        raw = line[len(_CONTAINER_RUNTIME_MARKER) :].rstrip("\r\n")
        try:
            identity = RuntimeIdentity.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValueError):
            return stderr, None
        return "".join([*lines[:index], *lines[index + 1 :]]), identity
    return stderr, None


def _read_bounded(path: Path, limit: int) -> tuple[str, bool]:
    size = path.stat().st_size
    with path.open("rb") as stream:
        data = stream.read(limit)
    return data.decode("utf-8", errors="replace"), size > limit


def build_container_argv(
    *,
    engine_path: str,
    spec: ContainerExecutionSpec,
    worktree: Path,
    cidfile: Path,
    command: list[str],
) -> list[str]:
    source = os.fspath(worktree.resolve())
    uid, gid = spec.user.split(":")
    if "," in source:
        raise PreflightError("container worktree path cannot contain a comma")
    return [
        engine_path,
        "run",
        "--rm",
        "--pull=never",
        "--cidfile",
        os.fspath(cidfile),
        "--network",
        spec.network,
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit",
        str(spec.pids_limit),
        "--memory",
        f"{spec.memory_mb}m",
        "--cpus",
        str(spec.cpus),
        "--user",
        spec.user,
        "--workdir",
        "/workspace",
        "--mount",
        f"type=bind,source={source},target=/workspace,readonly",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777",
        "--tmpfs",
        f"/home/prguard:rw,nosuid,nodev,size=64m,mode=700,uid={uid},gid={gid}",
        "--env",
        "HOME=/home/prguard",
        "--env",
        "TMPDIR=/tmp",
        "--env",
        "LC_ALL=C.UTF-8",
        "--env",
        "PYTHONPATH=/workspace/src:/workspace",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--env",
        "PYTHONNOUSERSITE=1",
        "--entrypoint",
        command[0],
        spec.image,
        "-c",
        _CONTAINER_STARTUP_WRAPPER,
        *command[1:],
    ]


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
        container: ContainerExecutionSpec | None = None,
    ) -> None:
        self.worktree = worktree
        self.runtime_directory = runtime_directory
        self.policy = policy
        self.default_timeout = default_timeout
        self.max_output_bytes = max_output_bytes
        self.task_deadline = task_deadline
        self.container = container
        self.engine_path: str | None = None
        if container is not None:
            self.engine_path = shutil.which(container.engine)
            if self.engine_path is None:
                raise PreflightError("configured container engine is not installed")

    def _remove_container(self, cidfile: Path, env: dict[str, str]) -> None:
        if self.engine_path is None or not cidfile.is_file():
            return
        container_id = cidfile.read_text(encoding="utf-8", errors="replace").strip()
        if container_id:
            with suppress(OSError, subprocess.SubprocessError):
                subprocess.run(
                    [self.engine_path, "rm", "--force", container_id],
                    env=env,
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )

    @staticmethod
    def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
        """Kill descendants that outlive an otherwise completed host command."""

        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                return
            except PermissionError:
                # SIGTERM was already delivered. A post-reap permission failure can mean
                # macOS has made the numeric group inaccessible (or reused it); do not risk
                # signalling a group we can no longer identify as the command's descendant.
                return
            time.sleep(0.01)
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)

    def execute(self, index: int, spec: CommandSpec) -> VerificationResult:
        if self.container is None:
            effective_argv = self.policy.authorize(spec.argv)
            backend = ExecutionBackend.HOST
            runtime_identity = _host_runtime_identity()
        else:
            effective_argv = self.policy.authorize_container(
                spec.argv, self.container.python_executable
            )
            backend = ExecutionBackend.CONTAINER
            runtime_identity = None
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
                execution_backend=backend,
                container_image=self.container.image if self.container else None,
                runtime=runtime_identity,
            )
        env = {
            "PATH": os.pathsep.join(
                [
                    os.fspath(Path(sys.executable).absolute().parent),
                    os.environ.get("PATH", "/usr/bin:/bin"),
                ]
            ),
            "HOME": os.fspath(self.runtime_directory / "home"),
            "TMPDIR": os.fspath(self.runtime_directory / "tmp"),
            "LC_ALL": "C.UTF-8",
            "PYTHONPATH": os.pathsep.join(
                [os.fspath(self.worktree / "src"), os.fspath(self.worktree)]
            ),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
        started = time.monotonic()
        cidfile = self.runtime_directory / f"container-{index}.cid"
        launch_argv = effective_argv
        if self.container is not None:
            assert self.engine_path is not None
            launch_argv = build_container_argv(
                engine_path=self.engine_path,
                spec=self.container,
                worktree=self.worktree,
                cidfile=cidfile,
                command=effective_argv,
            )
        with tempfile.NamedTemporaryFile(dir=self.runtime_directory, delete=False) as stdout_file:
            stdout_path = Path(stdout_file.name)
            with tempfile.NamedTemporaryFile(
                dir=self.runtime_directory, delete=False
            ) as stderr_file:
                stderr_path = Path(stderr_file.name)
                process = subprocess.Popen(
                    launch_argv,
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
                    self._remove_container(cidfile, env)
                    exit_code = None
                else:
                    self._terminate_process_group(process)
                    if self.container is not None:
                        self._remove_container(cidfile, env)
        duration = time.monotonic() - started
        stdout, stdout_truncated = _read_bounded(stdout_path, self.max_output_bytes)
        stderr, stderr_truncated = _read_bounded(stderr_path, self.max_output_bytes)
        stdout_path.unlink(missing_ok=True)
        stderr_path.unlink(missing_ok=True)
        cidfile.unlink(missing_ok=True)
        container_started = _CONTAINER_STARTUP_MARKER in stderr
        if container_started:
            stderr = stderr.replace(_CONTAINER_STARTUP_MARKER, "", 1)
            stderr, runtime_identity = _extract_container_runtime(stderr)
        infrastructure_error = (
            backend is ExecutionBackend.CONTAINER
            and not timed_out
            and (
                exit_code in {125, 126, 127}
                or not container_started
                or runtime_identity is None
            )
        )
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
            execution_backend=backend,
            container_image=self.container.image if self.container else None,
            runtime=runtime_identity,
            infrastructure_error=infrastructure_error,
            passed=not timed_out and not infrastructure_error and exit_code == 0,
        )
