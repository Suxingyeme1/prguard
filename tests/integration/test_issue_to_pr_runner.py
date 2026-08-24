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
    ReviewRoute,
    ReviewRoutingMode,
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


def _task(
    repo: Path,
    commit: str,
    case_id: str,
    *,
    routing: ReviewRoutingMode = ReviewRoutingMode.ALWAYS,
) -> IssueToPRTask:
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
        review_routing_mode=routing,
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
    assert report.review_routing.mode is ReviewRoutingMode.ALWAYS
    assert report.review_routing.effective_route is ReviewRoute.REVIEW
    assert report.review_repair.outcome is ReviewRepairOutcome.ACCEPTED_AFTER_REPAIR
    assert report.final_patch.read_text(encoding="utf-8") == _correct_patch()
    assert run_git(repo, "status", "--porcelain") == ""
    manifest = verify_manifest(Path(report.artifact_directory) / "issue-to-pr-manifest.json")
    assert manifest.run_id == report.run_id
    assert any(entry.path.endswith("review-repair-manifest.json") for entry in manifest.artifacts)
    assert any(entry.path == "review-routing.json" for entry in manifest.artifacts)


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


def _low_risk_repo(make_repo):
    return make_repo(
        {
            "math_service.py": "def double(value: int) -> int:\n    return value * 2\n",
            "tests/test_math_service.py": (
                "from math_service import double\n\n"
                "def test_double():\n"
                "    assert double(3) == 6\n"
            ),
        }
    )


def _low_risk_patch() -> str:
    return (
        "diff --git a/math_service.py b/math_service.py\n"
        "--- a/math_service.py\n"
        "+++ b/math_service.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def double(value: int) -> int:\n"
        "-    return value * 2\n"
        "+    return value + value\n"
    )


def _low_risk_task(
    repo: Path, commit: str, routing: ReviewRoutingMode
) -> IssueToPRTask:
    return IssueToPRTask(
        case_id=f"low-risk-{routing.value}",
        repository=repo,
        base_commit=commit,
        issue="Keep doubling behavior with an equivalent implementation.",
        commands=[
            CommandSpec(argv=["pytest", "-q", "tests/test_math_service.py"], kind="pytest")
        ],
        allowed_commands=[["pytest", "-q", "tests/test_math_service.py"]],
        writable_paths=["math_service.py"],
        protected_paths=["tests/**"],
        command_timeout_seconds=5,
        task_timeout_seconds=30,
        fix_timeout_seconds=10,
        review_timeout_seconds=5,
        max_repair_attempts=0,
        review_routing_mode=routing,
    )


@pytest.mark.integration
def test_selective_low_risk_fix_skips_provider_construction_and_review(
    make_repo, tmp_path: Path
) -> None:
    repo, commit = _low_risk_repo(make_repo)
    provider_constructions = {"reviewer": 0, "repair": 0}

    def reviewer_factory():
        provider_constructions["reviewer"] += 1
        raise AssertionError("selective skip must not construct a Reviewer")

    def repair_factory():
        provider_constructions["repair"] += 1
        raise AssertionError("selective skip must not construct a repair Implementer")

    report = IssueToPRRunner(
        tmp_path / "artifacts",
        ScriptedProvider([_proposal(_low_risk_patch(), "Preserve behavior")]),
        reviewer_factory,
        repair_factory,
    ).run(_low_risk_task(repo, commit, ReviewRoutingMode.SELECTIVE))

    assert report.outcome is IssueToPROutcome.ACCEPTED
    assert report.review_routing.recommended_route is ReviewRoute.SKIP
    assert report.review_routing.effective_route is ReviewRoute.SKIP
    assert report.review_routing.score < report.review_routing.threshold
    assert report.review_repair is None
    assert provider_constructions == {"reviewer": 0, "repair": 0}
    assert report.final_patch.read_bytes() == report.fix.final_patch.read_bytes()
    manifest = verify_manifest(Path(report.artifact_directory) / "issue-to-pr-manifest.json")
    paths = {entry.path for entry in manifest.artifacts}
    assert "review-routing.json" in paths
    assert not any(path.startswith("review/") for path in paths)


@pytest.mark.integration
def test_shadow_low_risk_fix_records_skip_recommendation_but_still_reviews(
    make_repo, tmp_path: Path
) -> None:
    repo, commit = _low_risk_repo(make_repo)
    reviewer = RecordingReviewer(
        ScriptedReviewerProvider(
            ReviewerSubmission(summary="No evidence-backed defects.", findings=[])
        )
    )
    report = IssueToPRRunner(
        tmp_path / "artifacts",
        ScriptedProvider([_proposal(_low_risk_patch(), "Preserve behavior")]),
        reviewer,
        ScriptedProvider([_proposal(_low_risk_patch(), "Must remain unused")]),
    ).run(_low_risk_task(repo, commit, ReviewRoutingMode.SHADOW))

    assert report.outcome is IssueToPROutcome.ACCEPTED
    assert report.review_routing.recommended_route is ReviewRoute.SKIP
    assert report.review_routing.effective_route is ReviewRoute.REVIEW
    assert reviewer.calls == 1
    assert report.review_repair.outcome is ReviewRepairOutcome.ACCEPTED_WITHOUT_REPAIR


@pytest.mark.integration
def test_selective_narrow_gate_with_unselected_reachable_test_routes_to_review(
    make_repo, tmp_path: Path
) -> None:
    repo, commit = _repo(make_repo)
    reviewer = RecordingReviewer(_blocking_reviewer())
    report = IssueToPRRunner(
        tmp_path / "artifacts",
        ScriptedProvider([_proposal(_candidate_regression(), "Implement None behavior")]),
        reviewer,
        ScriptedProvider([_proposal(_correct_patch(), "Restore normalization")]),
    ).run(
        _task(
            repo,
            commit,
            "selective-regression",
            routing=ReviewRoutingMode.SELECTIVE,
        )
    )

    assert report.outcome is IssueToPROutcome.ACCEPTED
    assert report.review_routing.effective_route is ReviewRoute.REVIEW
    codes = {factor.code for factor in report.review_routing.factors}
    assert "reachable_tests_not_explicitly_covered" in codes
    assert "tests/test_regression.py" in report.review_routing.uncovered_reachable_tests
    assert reviewer.calls == 1
    assert report.review_repair.outcome is ReviewRepairOutcome.ACCEPTED_AFTER_REPAIR


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


@pytest.mark.integration
def test_selective_cli_skip_needs_no_reviewer_key_or_repair_fixture(
    make_repo,
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    repo, commit = _low_risk_repo(make_repo)
    task_path = tmp_path / "low-risk-task.json"
    task_path.write_text(
        _low_risk_task(repo, commit, ReviewRoutingMode.ALWAYS).model_dump_json(indent=2),
        encoding="utf-8",
    )
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(
        json.dumps([_proposal(_low_risk_patch(), "Preserve behavior").model_dump()]),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "fix",
            str(task_path),
            "--provider",
            "scripted",
            "--proposal-sequence",
            str(proposal_path),
            "--review",
            "--review-policy",
            "selective",
            "--review-provider",
            "deepseek",
            "--artifacts",
            str(tmp_path / "cli-artifacts"),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["review_routing"]["effective_route"] == "skip"
    assert output["review_repair"] is None


def test_review_policy_without_review_is_rejected(capsys) -> None:
    exit_code = main(["fix", "unused.json", "--review-policy", "selective"])

    assert exit_code == 2
    assert "--review-policy requires --review" in capsys.readouterr().err
