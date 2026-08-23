import json
from pathlib import Path

import pytest

from prguard.cli import main
from prguard.harness import verify_manifest
from prguard.implementer.errors import ProviderError
from prguard.implementer.providers import ProviderRequest, ScriptedProvider
from prguard.implementer.tools import RepositoryTools
from prguard.review import ReviewRepairRunner
from prguard.reviewer import ScriptedReviewerProvider
from prguard.schemas import (
    AgentToolCall,
    CommandSpec,
    FindingCategory,
    ImplementerProposal,
    ProviderFailureEvidence,
    ReviewerSubmission,
    ReviewFinding,
    ReviewRepairOutcome,
    ReviewRepairTask,
    RunOutcome,
    Severity,
    TokenUsage,
    Verdict,
)
from tests.conftest import run_git


def _write_patch(path: Path, value: str) -> Path:
    path.write_text(value, encoding="utf-8")
    return path


def _task(repo: Path, commit: str, patch: Path, case_id: str) -> ReviewRepairTask:
    return ReviewRepairTask(
        case_id=case_id,
        repository=repo,
        base_commit=commit,
        issue="Accept None without changing normalization of non-None values.",
        candidate_patch=patch,
        commands=[CommandSpec(argv=["pytest", "-q", "tests"], kind="pytest")],
        allowed_commands=[["pytest", "-q", "tests"]],
        writable_paths=["service.py"],
        protected_paths=["pyproject.toml"],
        command_timeout_seconds=5,
        task_timeout_seconds=30,
        review_timeout_seconds=10,
    )


def _regression_case(make_repo, tmp_path: Path):
    repo, commit = make_repo(
        {
            "service.py": (
                "def normalize(value: str) -> str:\n    return value.strip().lower()\n"
            ),
            "tests/test_service.py": (
                "from service import normalize\n\n"
                "def test_regression():\n    assert normalize(' HELLO ') == 'hello'\n\n"
                "def test_none():\n    assert normalize(None) == ''\n"
            ),
        }
    )
    candidate = _write_patch(
        tmp_path / "candidate.patch",
        "diff --git a/service.py b/service.py\n--- a/service.py\n+++ b/service.py\n"
        "@@ -1,2 +1,4 @@\n def normalize(value: str) -> str:\n"
        "-    return value.strip().lower()\n+    if value is None:\n+        return ''\n"
        "+    return value.strip()\n",
    )
    finding = ReviewFinding(
        severity=Severity.P2,
        category=FindingCategory.REGRESSION,
        file="service.py",
        line=4,
        symbol="normalize",
        claim="The candidate stops lowercasing non-None input.",
        evidence="The new return calls strip() but not lower(), and test_regression fails.",
        verification="Run pytest -q tests and observe test_regression.",
        confidence=0.99,
    )
    reviewer = ScriptedReviewerProvider(
        ReviewerSubmission(summary="One normalization regression.", findings=[finding])
    )
    return repo, commit, candidate, reviewer


def _proposal(patch: str, summary: str = "Preserve both required behaviors."):
    return ImplementerProposal(
        plan=["Replace the candidate with a base-relative minimal correction"],
        summary=summary,
        patch=patch,
        tests_changed=False,
    )


def _correct_replacement() -> str:
    return (
        "diff --git a/service.py b/service.py\n--- a/service.py\n+++ b/service.py\n"
        "@@ -1,2 +1,4 @@\n def normalize(value: str) -> str:\n"
        "-    return value.strip().lower()\n+    if value is None:\n+        return ''\n"
        "+    return value.strip().lower()\n"
    )


class RecordingProvider:
    name = "recording-scripted"
    model = "deterministic-fixture"

    def __init__(self, proposal: ImplementerProposal) -> None:
        self.inner = ScriptedProvider([proposal])
        self.requests: list[ProviderRequest] = []

    def propose(self, request: ProviderRequest, tools: RepositoryTools):
        self.requests.append(request)
        return self.inner.propose(request, tools)


class EvidenceFailureImplementer:
    name = "evidence-failure-repair"
    model = "deterministic-fixture"

    def propose(self, request: ProviderRequest, tools: RepositoryTools):
        raise ProviderError(
            "Implementer read-tool budget exhausted; expected terminal submission",
            evidence=ProviderFailureEvidence(
                provider=self.name,
                model=self.model,
                response_id="partial-repair",
                token_usage=TokenUsage(input_tokens=55, output_tokens=8, cached_tokens=13),
                tool_calls=[
                    AgentToolCall(
                        sequence=0,
                        name="read_file",
                        arguments={"path": "service.py", "start_line": 1, "end_line": 20},
                        succeeded=True,
                        output_bytes=64,
                    )
                ],
            ),
        )


@pytest.mark.integration
def test_blocking_review_is_repaired_and_reverified(make_repo, tmp_path: Path) -> None:
    repo, commit, candidate, reviewer = _regression_case(make_repo, tmp_path)
    implementer = RecordingProvider(_proposal(_correct_replacement()))
    report = ReviewRepairRunner(tmp_path / "artifacts", reviewer, implementer).run(
        _task(repo, commit, candidate, "review-repair-success")
    )

    assert report.outcome is ReviewRepairOutcome.ACCEPTED_AFTER_REPAIR
    assert report.verdict is Verdict.ACCEPT
    assert report.initial_review.verdict is Verdict.REQUEST_CHANGES
    assert report.final_verification.outcome is RunOutcome.PASSED
    assert report.final_patch.read_text(encoding="utf-8") == _correct_replacement()
    assert run_git(repo, "status", "--porcelain") == ""
    manifest = verify_manifest(
        Path(report.artifact_directory) / "review-repair-manifest.json"
    )
    assert manifest.run_id == report.run_id
    feedback = json.loads(implementer.requests[0].feedback)
    assert feedback["review_findings"][0]["file"] == "service.py"
    assert feedback["verification"]["failed_commands"][0]["exit_code"] == 1
    serialized = implementer.requests[0].feedback
    assert all(
        forbidden not in serialized
        for forbidden in ("gold_patch", "hidden_tests", "reviewer_reasoning")
    )


@pytest.mark.integration
def test_failed_replacement_remains_request_changes(make_repo, tmp_path: Path) -> None:
    repo, commit, candidate, reviewer = _regression_case(make_repo, tmp_path)
    broken_replacement = candidate.read_text(encoding="utf-8")
    report = ReviewRepairRunner(
        tmp_path / "artifacts", reviewer, ScriptedProvider([_proposal(broken_replacement)])
    ).run(_task(repo, commit, candidate, "review-repair-still-broken"))

    assert report.outcome is ReviewRepairOutcome.REPAIR_FAILED
    assert report.verdict is Verdict.REQUEST_CHANGES
    assert report.final_verification.outcome is RunOutcome.FAILED_VERIFICATION
    assert report.final_patch is None


@pytest.mark.integration
def test_controlled_repair_provider_failure_preserves_partial_evidence(
    make_repo, tmp_path: Path
) -> None:
    repo, commit, candidate, reviewer = _regression_case(make_repo, tmp_path)
    report = ReviewRepairRunner(
        tmp_path / "artifacts", reviewer, EvidenceFailureImplementer()
    ).run(_task(repo, commit, candidate, "review-repair-provider-failure"))

    assert report.outcome is ReviewRepairOutcome.REPAIR_FAILED
    assert report.repair_provider_failure is not None
    assert report.token_usage.input_tokens == 55
    root = Path(report.artifact_directory)
    artifact = root / "repair-provider-failure.json"
    assert json.loads(artifact.read_text())["response_id"] == "partial-repair"
    manifest = verify_manifest(root / "review-repair-manifest.json")
    assert artifact.name in {entry.path for entry in manifest.artifacts}


@pytest.mark.integration
def test_blocking_review_can_be_repaired_with_structured_edit(
    make_repo, tmp_path: Path
) -> None:
    repo, commit, candidate, reviewer = _regression_case(make_repo, tmp_path)
    proposal = ImplementerProposal.model_validate(
        {
            "plan": ["Restore lowercase normalization in the patched function"],
            "summary": "Preserve the None fix and restore lower().",
            "edits": [
                {
                    "operation": "replace_text",
                    "path": "service.py",
                    "old_text": "    return value.strip()\n",
                    "new_text": "    return value.strip().lower()\n",
                }
            ],
            "tests_changed": False,
        }
    )

    report = ReviewRepairRunner(
        tmp_path / "structured-artifacts",
        reviewer,
        ScriptedProvider([proposal]),
    ).run(_task(repo, commit, candidate, "review-repair-structured"))

    assert report.outcome is ReviewRepairOutcome.ACCEPTED_AFTER_REPAIR
    assert report.final_patch is not None
    final_patch = report.final_patch.read_text()
    assert "if value is None:" in final_patch
    assert "return value.strip().lower()" in final_patch


@pytest.mark.integration
def test_accepted_review_does_not_invoke_implementer(make_repo, tmp_path: Path) -> None:
    repo, commit = make_repo(
        {
            "service.py": "VALUE = 1\n",
            "tests/test_service.py": (
                "from service import VALUE\n\ndef test_value():\n    assert VALUE == 2\n"
            ),
        }
    )
    candidate = _write_patch(
        tmp_path / "candidate.patch",
        "diff --git a/service.py b/service.py\n--- a/service.py\n+++ b/service.py\n"
        "@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n",
    )
    reviewer = ScriptedReviewerProvider(
        ReviewerSubmission(summary="No evidence-backed defects.", findings=[])
    )
    implementer = RecordingProvider(_proposal(_correct_replacement()))
    report = ReviewRepairRunner(tmp_path / "artifacts", reviewer, implementer).run(
        _task(repo, commit, candidate, "review-no-repair")
    )

    assert report.outcome is ReviewRepairOutcome.ACCEPTED_WITHOUT_REPAIR
    assert report.verdict is Verdict.ACCEPT
    assert report.repair_proposal is None
    assert implementer.requests == []
    assert report.final_patch.read_bytes() == candidate.read_bytes()


@pytest.mark.integration
def test_repair_outside_writable_scope_is_policy_blocked(make_repo, tmp_path: Path) -> None:
    repo, commit, candidate, reviewer = _regression_case(make_repo, tmp_path)
    protected = (
        "diff --git a/pyproject.toml b/pyproject.toml\n"
        "--- a/pyproject.toml\n+++ b/pyproject.toml\n@@ -1 +1 @@\n-a\n+b\n"
    )
    report = ReviewRepairRunner(
        tmp_path / "artifacts", reviewer, ScriptedProvider([_proposal(protected)])
    ).run(_task(repo, commit, candidate, "review-repair-policy"))

    assert report.outcome is ReviewRepairOutcome.POLICY_BLOCKED
    assert report.repair_proposal is not None
    assert report.final_verification is None
    artifact_directory = Path(report.artifact_directory)
    assert (artifact_directory / "repair.patch").read_text(encoding="utf-8") == protected
    assert (artifact_directory / "repair-proposal.json").is_file()


@pytest.mark.integration
def test_review_repair_cli_scripted(make_repo, tmp_path: Path, capsys) -> None:
    repo, commit, candidate, _reviewer = _regression_case(make_repo, tmp_path)
    task_path = tmp_path / "review-repair-task.json"
    task_path.write_text(
        _task(repo, commit, candidate, "review-repair-cli").model_dump_json(indent=2),
        encoding="utf-8",
    )
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "summary": "The candidate regresses lowercase normalization.",
                "findings": [
                    {
                        "severity": "P2",
                        "category": "regression",
                        "file": "service.py",
                        "line": 4,
                        "symbol": "normalize",
                        "claim": "The lower() call was removed.",
                        "evidence": "The changed line calls only strip().",
                        "verification": "Run pytest -q tests.",
                        "confidence": 0.99,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    proposals_path = tmp_path / "proposals.json"
    proposals_path.write_text(
        json.dumps([_proposal(_correct_replacement()).model_dump(mode="json")]),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "review",
            str(task_path),
            "--provider",
            "scripted",
            "--scripted-review",
            str(review_path),
            "--repair",
            "--repair-provider",
            "scripted",
            "--repair-proposal-sequence",
            str(proposals_path),
            "--artifacts",
            str(tmp_path / "cli-artifacts"),
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["outcome"] == "accepted_after_repair"
