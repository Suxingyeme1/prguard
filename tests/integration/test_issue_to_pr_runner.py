import json
from pathlib import Path

import pytest

from prguard.cli import main
from prguard.harness import verify_manifest
from prguard.implementer.providers import ScriptedProvider
from prguard.pipeline import IssueToPRRunner
from prguard.reviewer import ScriptedReviewerProvider
from prguard.schemas import (
    CommandSpec,
    FindingCategory,
    ImplementerProposal,
    IssueToPROutcome,
    IssueToPRTask,
    ReviewerSubmission,
    ReviewFinding,
    ReviewRepairOutcome,
    Severity,
    Verdict,
)
from tests.conftest import run_git


def _proposal(patch: str, summary: str) -> ImplementerProposal:
    return ImplementerProposal(
        plan=[summary], summary=summary, patch=patch, tests_changed=False
    )


def _candidate_regression() -> str:
    return (
        "diff --git a/service.py b/service.py\n--- a/service.py\n+++ b/service.py\n"
        "@@ -1,2 +1,4 @@\n def normalize(value: str) -> str:\n"
        "-    return value.strip().lower()\n+    if value is None:\n+        return ''\n"
        "+    return value.strip()\n"
    )


def _correct_patch() -> str:
    return (
        "diff --git a/service.py b/service.py\n--- a/service.py\n+++ b/service.py\n"
        "@@ -1,2 +1,4 @@\n def normalize(value: str) -> str:\n"
        "-    return value.strip().lower()\n+    if value is None:\n+        return ''\n"
        "+    return value.strip().lower()\n"
    )


def _task(repo: Path, commit: str, case_id: str) -> IssueToPRTask:
    return IssueToPRTask(
        case_id=case_id,
        repository=repo,
        base_commit=commit,
        issue="Accept None as empty without regressing normalization.",
        commands=[
            CommandSpec(argv=["pytest", "-q", "tests/test_new_behavior.py"], kind="pytest")
        ],
        allowed_commands=[["pytest", "-q", "tests/test_new_behavior.py"]],
        writable_paths=["service.py"],
        protected_paths=["tests/**"],
        command_timeout_seconds=5,
        task_timeout_seconds=30,
        fix_timeout_seconds=10,
        review_timeout_seconds=5,
        max_repair_attempts=0,
    )


def _repo(make_repo):
    return make_repo(
        {
            "service.py": (
                "def normalize(value: str) -> str:\n    return value.strip().lower()\n"
            ),
            "tests/test_new_behavior.py": (
                "from service import normalize\n\n"
                "def test_none():\n    assert normalize(None) == ''\n"
            ),
            "tests/test_regression.py": (
                "from service import normalize\n\n"
                "def test_normalization():\n    assert normalize(' HELLO ') == 'hello'\n"
            ),
        }
    )


def _blocking_reviewer() -> ScriptedReviewerProvider:
    finding = ReviewFinding(
        severity=Severity.P2,
        category=FindingCategory.REGRESSION,
        file="service.py",
        line=4,
        symbol="normalize",
        claim="The candidate removes lowercase normalization.",
        evidence=(
            "The patched return calls strip() without lower(); the existing test expects both."
        ),
        verification="Run pytest -q tests/test_regression.py.",
        confidence=0.99,
    )
    return ScriptedReviewerProvider(
        ReviewerSubmission(summary="One uncovered regression.", findings=[finding])
    )


class RecordingReviewer:
    name = "recording-reviewer"
    model = "deterministic-fixture"

    def __init__(self, inner: ScriptedReviewerProvider) -> None:
        self.inner = inner
        self.calls = 0

    def review(self, request, tools):
        self.calls += 1
        return self.inner.review(request, tools)


@pytest.mark.integration
def test_fix_review_and_controlled_repair_deliver_one_patch(make_repo, tmp_path: Path) -> None:
    repo, commit = _repo(make_repo)
    report = IssueToPRRunner(
        tmp_path / "artifacts",
        ScriptedProvider([_proposal(_candidate_regression(), "Implement None behavior")]),
        _blocking_reviewer(),
        ScriptedProvider([_proposal(_correct_patch(), "Restore normalization")]),
    ).run(_task(repo, commit, "issue-to-pr-review-value"))

    assert report.outcome is IssueToPROutcome.ACCEPTED
    assert report.verdict is Verdict.ACCEPT
    assert report.fix.outcome.value == "accepted"
    assert report.review_repair.outcome is ReviewRepairOutcome.ACCEPTED_AFTER_REPAIR
    assert report.final_patch.read_text(encoding="utf-8") == _correct_patch()
    assert run_git(repo, "status", "--porcelain") == ""
    manifest = verify_manifest(Path(report.artifact_directory) / "issue-to-pr-manifest.json")
    assert manifest.run_id == report.run_id
    assert any(entry.path.endswith("review-repair-manifest.json") for entry in manifest.artifacts)


@pytest.mark.integration
def test_clean_fix_is_delivered_without_review_repair(make_repo, tmp_path: Path) -> None:
    repo, commit = _repo(make_repo)
    reviewer = ScriptedReviewerProvider(
        ReviewerSubmission(summary="No evidence-backed defects.", findings=[])
    )
    repair = ScriptedProvider([_proposal(_candidate_regression(), "Must remain unused")])
    report = IssueToPRRunner(
        tmp_path / "artifacts",
        ScriptedProvider([_proposal(_correct_patch(), "Implement complete behavior")]),
        reviewer,
        repair,
    ).run(_task(repo, commit, "issue-to-pr-clean"))

    assert report.outcome is IssueToPROutcome.ACCEPTED
    assert report.review_repair.outcome is ReviewRepairOutcome.ACCEPTED_WITHOUT_REPAIR
    assert report.review_repair.repair_proposal is None
    assert report.final_patch.read_text(encoding="utf-8") == _correct_patch()


@pytest.mark.integration
def test_failed_fix_never_calls_reviewer(make_repo, tmp_path: Path) -> None:
    repo, commit = _repo(make_repo)
    failing = (
        "diff --git a/service.py b/service.py\n--- a/service.py\n+++ b/service.py\n"
        "@@ -1,2 +1,2 @@\n def normalize(value: str) -> str:\n"
        "-    return value.strip().lower()\n+    return value\n"
    )
    reviewer = RecordingReviewer(_blocking_reviewer())
    report = IssueToPRRunner(
        tmp_path / "artifacts",
        ScriptedProvider([_proposal(failing, "Incomplete implementation")]),
        reviewer,
        ScriptedProvider([_proposal(_correct_patch(), "Must remain unused")]),
    ).run(_task(repo, commit, "issue-to-pr-fix-failed"))

    assert report.outcome is IssueToPROutcome.FIX_FAILED
    assert report.review_repair is None
    assert reviewer.calls == 0
    assert report.final_patch is None


@pytest.mark.integration
def test_fix_review_cli_scripted(make_repo, tmp_path: Path, capsys) -> None:
    repo, commit = _repo(make_repo)
    task_path = tmp_path / "issue-to-pr-task.json"
    task_path.write_text(
        _task(repo, commit, "issue-to-pr-cli").model_dump_json(indent=2), encoding="utf-8"
    )
    initial_path = tmp_path / "initial.json"
    initial_path.write_text(
        json.dumps(
            [_proposal(_candidate_regression(), "Implement None behavior").model_dump()]
        ),
        encoding="utf-8",
    )
    review_path = tmp_path / "review.json"
    review_path.write_text(
        _blocking_reviewer().submission.model_dump_json(indent=2), encoding="utf-8"
    )
    repair_path = tmp_path / "repair.json"
    repair_path.write_text(
        json.dumps([_proposal(_correct_patch(), "Restore normalization").model_dump()]),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "fix",
            str(task_path),
            "--provider",
            "scripted",
            "--proposal-sequence",
            str(initial_path),
            "--review",
            "--review-provider",
            "scripted",
            "--scripted-review",
            str(review_path),
            "--review-repair-provider",
            "scripted",
            "--review-repair-proposal-sequence",
            str(repair_path),
            "--artifacts",
            str(tmp_path / "cli-artifacts"),
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["outcome"] == "accepted"
    assert output["review_repair"]["outcome"] == "accepted_after_repair"
