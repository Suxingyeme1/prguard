import os
import sys
from pathlib import Path

import pytest

from prguard.harness import VerificationHarness
from prguard.schemas import CommandSpec, ContainerExecutionSpec, RunOutcome, Task


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


@pytest.mark.integration
def test_container_infrastructure_error_is_not_a_test_failure(
    make_repo, tmp_path: Path, monkeypatch
) -> None:
    repo, commit = make_repo({"tests/test_ok.py": "def test_ok():\n    assert True\n"})
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "pathlib.Path(args[args.index('--cidfile') + 1]).write_text('fake-id')\n"
        "sys.stderr.write('container image is unavailable\\n')\n"
        "raise SystemExit(125)\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([os.fspath(fake_bin), os.environ["PATH"]]))
    command = ["pytest", "-q", "tests"]
    task = Task(
        case_id="container-infrastructure-error",
        repository=repo,
        base_commit=commit,
        issue="Classify container startup separately from test failure.",
        commands=[CommandSpec(argv=command)],
        allowed_commands=[command],
        container=ContainerExecutionSpec(image="sha256:" + "a" * 64),
    )

    report = VerificationHarness(tmp_path / "container-artifacts").run(task)

    assert report.outcome is RunOutcome.PREFLIGHT_FAILED
    assert report.commands[0].infrastructure_error is True
    assert report.commands[0].passed is False


@pytest.mark.integration
def test_container_missing_startup_marker_is_infrastructure_failure(
    make_repo, tmp_path: Path, monkeypatch
) -> None:
    repo, commit = make_repo({"tests/test_ok.py": "def test_ok():\n    assert True\n"})
    fake_bin = tmp_path / "fake-bin-no-marker"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "pathlib.Path(args[args.index('--cidfile') + 1]).write_text('fake-id')\n"
        "sys.stderr.write('exec python3: operation not permitted\\n')\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([os.fspath(fake_bin), os.environ["PATH"]]))
    command = ["pytest", "-q", "tests"]
    task = Task(
        case_id="container-startup-failure",
        repository=repo,
        base_commit=commit,
        issue="Distinguish runtime startup failure from a failing test.",
        commands=[CommandSpec(argv=command)],
        allowed_commands=[command],
        container=ContainerExecutionSpec(image="sha256:" + "b" * 64),
    )

    report = VerificationHarness(tmp_path / "container-startup-artifacts").run(task)

    assert report.outcome is RunOutcome.PREFLIGHT_FAILED
    assert report.commands[0].exit_code == 1
    assert report.commands[0].infrastructure_error is True
