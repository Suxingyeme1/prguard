from pathlib import Path

import pytest

from prguard.harness import VerificationHarness
from prguard.schemas import CommandSpec, RunOutcome, Task


@pytest.mark.integration
def test_output_is_truncated_but_command_result_remains_structured(
    make_repo, tmp_path: Path
) -> None:
    repo, commit = make_repo(
        {"tests/test_output.py": "def test_output():\n    print('x' * 5000)\n"}
    )
    command = ["pytest", "-q", "-s", "tests"]
    task = Task(
        case_id="bounded-output",
        repository=repo,
        base_commit=commit,
        issue="Bound output capture.",
        commands=[CommandSpec(argv=command)],
        allowed_commands=[command],
        max_output_bytes=1024,
    )
    report = VerificationHarness(tmp_path / "artifacts").run(task)
    assert report.outcome is RunOutcome.PASSED
    assert report.commands[0].stdout_truncated is True
    assert len(report.commands[0].stdout.encode()) <= 1024


@pytest.mark.integration
def test_ruff_result_is_structured(make_repo, tmp_path: Path) -> None:
    repo, commit = make_repo({"clean.py": "VALUE = 1\n"})
    command = ["ruff", "check", "."]
    task = Task(
        case_id="ruff-check",
        repository=repo,
        base_commit=commit,
        issue="Run lint.",
        commands=[CommandSpec(argv=command, kind="ruff")],
        allowed_commands=[command],
    )
    report = VerificationHarness(tmp_path / "artifacts").run(task)
    assert report.outcome is RunOutcome.PASSED
    assert report.commands[0].kind == "ruff"
    assert report.commands[0].exit_code == 0


@pytest.mark.integration
def test_pytest_imports_repository_src_layout(make_repo, tmp_path: Path) -> None:
    repo, commit = make_repo(
        {
            "src/example_pkg/__init__.py": "VALUE = 42\n",
            "tests/test_src_layout.py": (
                "from example_pkg import VALUE\n\n"
                "def test_value():\n"
                "    assert VALUE == 42\n"
            ),
        }
    )
    command = ["pytest", "-q", "tests/test_src_layout.py"]
    task = Task(
        case_id="src-layout-import",
        repository=repo,
        base_commit=commit,
        issue="Verify repository-local src imports.",
        commands=[CommandSpec(argv=command)],
        allowed_commands=[command],
    )
    report = VerificationHarness(tmp_path / "artifacts").run(task)
    assert report.outcome is RunOutcome.PASSED
    assert report.commands[0].passed is True
