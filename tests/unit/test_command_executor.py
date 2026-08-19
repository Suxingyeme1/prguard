import time
from pathlib import Path

from prguard.harness.commands import CommandExecutor
from prguard.harness.policy import CommandPolicy
from prguard.schemas import CommandSpec


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
