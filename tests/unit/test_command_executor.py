import json
import os
import sys
import time
from pathlib import Path

from prguard.harness.commands import CommandExecutor, build_container_argv
from prguard.harness.policy import CommandPolicy
from prguard.schemas import CommandSpec, ContainerExecutionSpec, ExecutionBackend


def test_exhausted_task_deadline_prevents_process_launch(tmp_path: Path) -> None:
    command = ["pytest", "-q"]
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    executor = CommandExecutor(
        worktree=tmp_path,
        runtime_directory=runtime,
        policy=CommandPolicy([command]),
        default_timeout=10,
        max_output_bytes=1024,
        task_deadline=time.monotonic() - 1,
    )
    result = executor.execute(0, CommandSpec(argv=command))
    assert result.timed_out is True
    assert result.exit_code is None
    assert "task deadline" in result.stderr


def _container_spec() -> ContainerExecutionSpec:
    return ContainerExecutionSpec(image="sha256:" + "a" * 64)


def test_container_argv_is_digest_pinned_and_fail_closed(tmp_path: Path) -> None:
    digest = "sha256:" + "a" * 64
    argv = build_container_argv(
        engine_path="/usr/bin/docker",
        spec=_container_spec(),
        worktree=tmp_path,
        cidfile=tmp_path / "container.cid",
        command=["python3", "-m", "pytest", "-q"],
    )

    assert argv[:3] == ["/usr/bin/docker", "run", "--rm"]
    assert "--pull=never" in argv
    assert argv[argv.index("--network") + 1] == "none"
    assert "--read-only" in argv
    assert "--cap-drop=ALL" in argv
    assert "--security-opt=no-new-privileges" in argv
    assert "type=bind" in argv[argv.index("--mount") + 1]
    assert argv[argv.index("--mount") + 1].endswith(",readonly")
    assert argv[-3:] == ["-m", "pytest", "-q"]
    assert argv[argv.index("--entrypoint") + 2] == digest
    assert argv[argv.index("--entrypoint") + 3] == "-c"
    assert "sys.argv[1:]" in argv[argv.index("--entrypoint") + 4]
    assert all(token not in argv for token in ["sh", "bash"])


def _fake_docker(tmp_path: Path) -> Path:
    executable = tmp_path / "docker"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys, time\n"
        "args = sys.argv[1:]\n"
        "tmp = pathlib.Path(os.environ['TMPDIR'])\n"
        "if args[0] == 'rm':\n"
        "    (tmp / 'container-removed').write_text(args[-1])\n"
        "    raise SystemExit(0)\n"
        "cidfile = pathlib.Path(args[args.index('--cidfile') + 1])\n"
        "cidfile.write_text('fake-container-id')\n"
        "(tmp / 'docker-argv.json').write_text(json.dumps(args))\n"
        "sys.stderr.write('__PRGUARD_CONTAINER_PYTHON_STARTED__\\n')\n"
        "sys.stderr.flush()\n"
        "if (tmp / 'sleep').exists():\n"
        "    time.sleep(10)\n"
        "if (tmp / 'fail').exists():\n"
        "    raise SystemExit(1)\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _container_executor(tmp_path: Path, monkeypatch) -> CommandExecutor:
    runtime = tmp_path / "runtime"
    (runtime / "home").mkdir(parents=True)
    (runtime / "tmp").mkdir()
    _fake_docker(tmp_path)
    monkeypatch.setenv("PATH", os.fspath(tmp_path))
    command = ["pytest", "-q"]
    return CommandExecutor(
        worktree=tmp_path,
        runtime_directory=runtime,
        policy=CommandPolicy([command]),
        default_timeout=5,
        max_output_bytes=1024,
        task_deadline=time.monotonic() + 10,
        container=_container_spec(),
    )


def test_container_executor_preserves_reported_argv(tmp_path: Path, monkeypatch) -> None:
    executor = _container_executor(tmp_path, monkeypatch)
    result = executor.execute(0, CommandSpec(argv=["pytest", "-q"]))
    launched = json.loads((tmp_path / "runtime" / "tmp" / "docker-argv.json").read_text())

    assert result.passed is True
    assert result.execution_backend is ExecutionBackend.CONTAINER
    assert result.container_image == "sha256:" + "a" * 64
    assert result.argv == ["pytest", "-q"]
    assert result.stderr == ""
    assert launched[launched.index("--network") + 1] == "none"


def test_container_timeout_forces_daemon_cleanup(tmp_path: Path, monkeypatch) -> None:
    executor = _container_executor(tmp_path, monkeypatch)
    (tmp_path / "runtime" / "tmp" / "sleep").touch()
    result = executor.execute(
        0,
        CommandSpec(argv=["pytest", "-q"], timeout_seconds=1),
    )

    assert result.timed_out is True
    assert result.execution_backend is ExecutionBackend.CONTAINER
    assert (tmp_path / "runtime" / "tmp" / "container-removed").read_text() == (
        "fake-container-id"
    )


def test_container_test_failure_after_startup_is_not_infrastructure(
    tmp_path: Path, monkeypatch
) -> None:
    executor = _container_executor(tmp_path, monkeypatch)
    (tmp_path / "runtime" / "tmp" / "fail").touch()

    result = executor.execute(0, CommandSpec(argv=["pytest", "-q"]))

    assert result.exit_code == 1
    assert result.passed is False
    assert result.infrastructure_error is False
