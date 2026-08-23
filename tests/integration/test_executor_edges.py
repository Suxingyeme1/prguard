import os
import sys
from pathlib import Path

import pytest

from prguard.harness import VerificationHarness
from prguard.schemas import (
    CommandSpec,
    ContainerExecutionSpec,
    RunOutcome,
    RuntimeFileSpec,
    Task,
)


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
    command = ["ruff", "check", "--no-fix", "."]
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
def test_verification_command_cannot_modify_candidate_worktree(
    make_repo, tmp_path: Path
) -> None:
    repo, commit = make_repo(
        {
            "value.py": "VALUE = 1\n",
            "tests/test_mutation.py": (
                "from pathlib import Path\n\n"
                "def test_mutation():\n"
                "    Path(__file__).parents[1].joinpath('value.py').write_text('VALUE = 3\\n')\n"
            ),
        }
    )
    patch = tmp_path / "candidate.patch"
    patch.write_text(
        "diff --git a/value.py b/value.py\n--- a/value.py\n+++ b/value.py\n"
        "@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    )
    command = ["pytest", "-q", "tests/test_mutation.py"]
    task = Task(
        case_id="verification-mutates-worktree",
        repository=repo,
        base_commit=commit,
        issue="Verification must be read-only with respect to the candidate.",
        candidate_patch=patch,
        commands=[CommandSpec(argv=command)],
        allowed_commands=[command],
    )

    report = VerificationHarness(tmp_path / "mutation-artifacts").run(task)

    assert report.outcome is RunOutcome.POLICY_BLOCKED
    violation = next(
        item
        for item in report.policy_violations
        if item.code == "verification_modified_worktree"
    )
    assert violation.paths == ["value.py"]


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
def test_runtime_scaffold_is_available_but_excluded_from_delivered_diff(
    make_repo, tmp_path: Path
) -> None:
    repo, commit = make_repo(
        {
            "src/example_pkg/__init__.py": "from ._version import __version__\n",
            "tests/test_version.py": (
                "from example_pkg import __version__\n\n"
                "def test_version():\n    assert __version__ == '0+prguard'\n"
            ),
        }
    )
    command = ["pytest", "-q", "tests/test_version.py"]
    task = Task(
        case_id="runtime-scaffold",
        repository=repo,
        base_commit=commit,
        issue="Verify generated version import.",
        commands=[CommandSpec(argv=command)],
        allowed_commands=[command],
        runtime_files=[
            RuntimeFileSpec(
                path="src/example_pkg/_version.py",
                content='__version__ = "0+prguard"\n',
                reason="hatch_vcs_version_file",
            )
        ],
    )

    report = VerificationHarness(tmp_path / "runtime-artifacts").run(task)

    assert report.outcome is RunOutcome.PASSED
    assert report.changed_files == []
    root = Path(report.artifact_directory)
    assert "_version.py" not in (root / "final.diff").read_text()
    assert not (repo / "src/example_pkg/_version.py").exists()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("assertion", "expected_outcome"),
    [("True", RunOutcome.PASSED), ("False", RunOutcome.FAILED_VERIFICATION)],
)
def test_changed_python_tests_are_added_to_the_deterministic_gate(
    assertion: str,
    expected_outcome: RunOutcome,
    make_repo,
    tmp_path: Path,
) -> None:
    repo, commit = make_repo(
        {"tests/test_existing.py": "def test_existing():\n    assert True\n"}
    )
    patch = tmp_path / f"generated-{assertion}.patch"
    patch.write_text(
        "diff --git a/tests/test_generated.py b/tests/test_generated.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/tests/test_generated.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def test_generated():\n"
        f"+    assert {assertion}\n",
        encoding="utf-8",
    )
    command = ["pytest", "-q", "tests/test_existing.py"]
    task = Task(
        case_id=f"generated-test-{assertion.lower()}",
        repository=repo,
        base_commit=commit,
        issue="Add a generated regression test.",
        candidate_patch=patch,
        commands=[CommandSpec(argv=command)],
        allowed_commands=[command],
    )

    report = VerificationHarness(tmp_path / f"generated-{assertion}-artifacts").run(task)

    assert report.outcome is expected_outcome
    assert report.commands[-1].kind == "pytest_changed_tests"
    assert report.commands[-1].argv == ["pytest", "-q", "tests/test_generated.py"]
    assert report.commands[-1].passed is (expected_outcome is RunOutcome.PASSED)
    assert any(event.kind == "verification.derived" for event in report.trace_events)


@pytest.mark.integration
def test_changed_python_tests_require_declared_pytest_capability(
    make_repo, tmp_path: Path
) -> None:
    repo, commit = make_repo({"clean.py": "VALUE = 1\n"})
    patch = tmp_path / "unverified-test.patch"
    patch.write_text(
        "diff --git a/tests/test_generated.py b/tests/test_generated.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/tests/test_generated.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def test_generated():\n"
        "+    assert True\n",
        encoding="utf-8",
    )
    command = ["ruff", "check", "--no-fix", "."]
    task = Task(
        case_id="changed-test-without-pytest",
        repository=repo,
        base_commit=commit,
        issue="Do not accept an unexecuted generated test.",
        candidate_patch=patch,
        commands=[CommandSpec(argv=command, kind="ruff")],
        allowed_commands=[command],
    )

    report = VerificationHarness(tmp_path / "unverified-test-artifacts").run(task)

    assert report.outcome is RunOutcome.POLICY_BLOCKED
    assert report.commands == []
    assert [violation.code for violation in report.policy_violations] == [
        "changed_tests_without_pytest"
    ]


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
