from pathlib import Path

import pytest

from prguard.harness import VerificationHarness, verify_manifest
from prguard.schemas import RunOutcome
from tests.conftest import read_expected, run_git


@pytest.mark.integration
@pytest.mark.parametrize(
    "case_name",
    ["correct-patch", "wrong-patch", "regression", "patch-apply-failure", "command-timeout"],
)
def test_minimal_fixture_case(
    case_name: str,
    materialized_cases: dict[str, Path],
    task_for_case,
    tmp_path: Path,
) -> None:
    task = task_for_case(case_name)
    expected = read_expected(materialized_cases[case_name])
    report = VerificationHarness(tmp_path / "artifacts").run(task)

    assert report.outcome.value == expected["outcome"]
    expected_commands = expected.get("command_passed")
    if expected_commands is not None:
        assert [result.passed for result in report.commands] == expected_commands
    assert not (Path(report.artifact_directory) / "worktree").exists()
    assert run_git(task.repository, "status", "--porcelain") == ""
    manifest = verify_manifest(Path(report.artifact_directory) / "manifest.json")
    assert manifest.run_id == report.run_id


@pytest.mark.integration
def test_final_diff_and_structured_pytest_output(task_for_case, tmp_path: Path) -> None:
    report = VerificationHarness(tmp_path / "artifacts").run(task_for_case("correct-patch"))
    run_directory = Path(report.artifact_directory)
    assert report.outcome is RunOutcome.PASSED
    assert report.commands[0].kind == "pytest"
    assert report.commands[0].exit_code == 0
    assert "1 passed" in report.commands[0].stdout or "2 passed" in report.commands[0].stdout
    assert "if count == 0" in (run_directory / "final.diff").read_text(encoding="utf-8")
