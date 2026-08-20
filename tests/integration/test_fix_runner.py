import json
from pathlib import Path

import pytest

from prguard.cli import load_fix_task, main
from prguard.fix import FixRunner
from prguard.harness import verify_manifest
from prguard.implementer.providers import ProviderRequest, ScriptedProvider
from prguard.implementer.tools import RepositoryTools
from prguard.schemas import FixOutcome, ImplementerProposal, RunOutcome
from tests.conftest import run_git


def load_provider(case_path: Path) -> ScriptedProvider:
    return ScriptedProvider.from_file(case_path.parent / "proposals.json")


@pytest.mark.integration
@pytest.mark.parametrize("case_name", ["direct-success", "repair-once"])
def test_issue_to_patch_fixture(
    case_name: str, materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case_path = materialized_fix_cases[case_name]
    task = load_fix_task(case_path)
    expected = json.loads((case_path.parent / "expected.json").read_text(encoding="utf-8"))
    report = FixRunner(tmp_path / "fix-artifacts", load_provider(case_path)).run(task)
    assert report.outcome.value == expected["outcome"]
    assert len(report.attempts) == expected["attempts"]
    assert report.final_patch and report.final_patch.is_file()
    assert run_git(task.repository, "status", "--porcelain") == ""
    manifest = verify_manifest(Path(report.artifact_directory) / "fix-manifest.json")
    assert manifest.run_id == report.run_id
    assert all(attempt.proposal.tool_calls for attempt in report.attempts if attempt.proposal)
    if case_name == "repair-once":
        assert report.attempts[0].verification.outcome is RunOutcome.FAILED_VERIFICATION
        assert report.attempts[1].verification.outcome is RunOutcome.PASSED
        assert "max(lower, min(value, upper))" in report.final_patch.read_text(encoding="utf-8")


@pytest.mark.integration
def test_fix_without_repair_budget_preserves_failure(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case_path = materialized_fix_cases["repair-once"]
    task = load_fix_task(case_path).model_copy(update={"max_repair_attempts": 0})
    report = FixRunner(tmp_path / "fix-artifacts", load_provider(case_path)).run(task)
    assert report.outcome is FixOutcome.FAILED_VERIFICATION
    assert len(report.attempts) == 1
    assert report.final_patch is None


@pytest.mark.integration
def test_protected_proposal_is_blocked_before_verification(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case_path = materialized_fix_cases["direct-success"]
    task = load_fix_task(case_path)
    proposal = ImplementerProposal(
        plan=["Tamper with protected configuration"],
        summary="Invalid proposal.",
        patch=(
            "diff --git a/pyproject.toml b/pyproject.toml\n"
            "--- a/pyproject.toml\n+++ b/pyproject.toml\n"
            "@@ -1 +1 @@\n-a\n+b\n"
        ),
        tests_changed=False,
    )
    report = FixRunner(tmp_path / "fix-artifacts", ScriptedProvider([proposal])).run(task)
    assert report.outcome is FixOutcome.POLICY_BLOCKED
    assert report.attempts[0].proposal is not None
    assert report.attempts[0].verification is None
    artifact_directory = Path(report.artifact_directory)
    assert (artifact_directory / "attempt-0.patch").read_text(encoding="utf-8") == proposal.patch
    assert (artifact_directory / "attempt-0-proposal.json").is_file()
    assert not (artifact_directory / "verification").exists()


class RecordingProvider:
    name = "recording-scripted"
    model = "deterministic-fixture"

    def __init__(self, inner: ScriptedProvider) -> None:
        self.inner = inner
        self.requests: list[ProviderRequest] = []

    def propose(self, request: ProviderRequest, tools: RepositoryTools):
        self.requests.append(request)
        return self.inner.propose(request, tools)


@pytest.mark.integration
def test_repair_receives_only_structured_failure_evidence(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case = materialized_fix_cases["repair-once"]
    provider = RecordingProvider(load_provider(case))
    report = FixRunner(tmp_path / "artifacts", provider).run(load_fix_task(case))
    assert report.outcome is FixOutcome.ACCEPTED
    feedback = json.loads(provider.requests[1].feedback)
    assert feedback["outcome"] == "failed_verification"
    assert feedback["commands"][0]["exit_code"] == 1
    assert "previous_patch" in feedback
    assert "gold_patch" not in provider.requests[1].feedback


@pytest.mark.integration
def test_fix_cli_runs_scripted_issue_to_patch(
    materialized_fix_cases: dict[str, Path], tmp_path: Path, capsys
) -> None:
    case = materialized_fix_cases["direct-success"]
    exit_code = main(
        [
            "fix",
            str(case),
            "--provider",
            "scripted",
            "--proposal-sequence",
            str(case.parent / "proposals.json"),
            "--artifacts",
            str(tmp_path / "cli-artifacts"),
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["outcome"] == "accepted"


def test_fix_cli_progress_uses_stderr_without_breaking_json_stdout(
    materialized_fix_cases: dict[str, Path], tmp_path: Path, capsys
) -> None:
    case = materialized_fix_cases["direct-success"]

    exit_code = main(
        [
            "fix",
            str(case),
            "--provider",
            "scripted",
            "--proposal-sequence",
            str(case.parent / "proposals.json"),
            "--artifacts",
            str(tmp_path / "cli-progress-artifacts"),
            "--progress",
        ]
    )

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["outcome"] == "accepted"
    assert "[prguard] Implementer working — attempt 0" in captured.err
    assert "[prguard] verification completed — passed" in captured.err
    assert "[prguard] run completed — accepted" in captured.err


def test_progress_observer_failure_cannot_change_fix_outcome(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case = materialized_fix_cases["direct-success"]

    def broken_observer(_event: str, _data: dict[str, object]) -> None:
        raise RuntimeError("presentation failure")

    report = FixRunner(
        tmp_path / "observer-artifacts",
        load_provider(case),
        progress=broken_observer,
    ).run(load_fix_task(case))

    assert report.outcome is FixOutcome.ACCEPTED
    assert report.final_patch is not None


def test_fix_runner_structures_repository_preflight_failure(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case = materialized_fix_cases["direct-success"]
    task = load_fix_task(case).model_copy(update={"repository": tmp_path / "missing-repository"})

    report = FixRunner(tmp_path / "preflight-artifacts", load_provider(case)).run(task)

    assert report.outcome is FixOutcome.PREFLIGHT_FAILED
    assert report.attempts[0].error is not None
    assert "repository does not exist" in report.attempts[0].error
