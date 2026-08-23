import json
import time
from pathlib import Path

import pytest

from prguard.cli import main
from prguard.harness import verify_manifest
from prguard.implementer.errors import ProviderError
from prguard.review import ReviewRunner
from prguard.reviewer import ScriptedReviewerProvider
from prguard.schemas import (
    AgentToolCall,
    CommandSpec,
    FindingCategory,
    FixTask,
    ProviderFailureEvidence,
    ReviewerSubmission,
    ReviewFinding,
    ReviewTask,
    Severity,
    TokenUsage,
    Verdict,
)
from tests.conftest import run_git


class SlowReviewerProvider:
    name = "slow-reviewer"
    model = "deterministic-sleeper"

    def review(self, request, tools):
        time.sleep(0.6)
        return ScriptedReviewerProvider(
            ReviewerSubmission(summary="No defects found.", findings=[])
        ).review(request, tools)


class EvidenceFailureReviewer:
    name = "evidence-failure-reviewer"
    model = "deterministic-fixture"

    def review(self, request, tools):
        raise ProviderError(
            "Reviewer tool-call budget exhausted",
            evidence=ProviderFailureEvidence(
                provider=self.name,
                model=self.model,
                response_id="partial-review",
                token_usage=TokenUsage(input_tokens=77, output_tokens=9, cached_tokens=20),
                tool_calls=[
                    AgentToolCall(
                        sequence=0,
                        name="read_file",
                        arguments={"path": "calc.py", "start_line": 1, "end_line": 20},
                        succeeded=True,
                        output_bytes=64,
                    )
                ],
            ),
        )


class NeverCalledReviewer:
    name = "never-called-reviewer"
    model = "deterministic-fixture"

    def __init__(self) -> None:
        self.calls = 0

    def review(self, request, tools):
        self.calls += 1
        raise AssertionError("Reviewer must not run when the Base Commit gate is unhealthy")


def write_patch(path: Path, value: str) -> Path:
    path.write_text(value, encoding="utf-8")
    return path


def review_task(repo: Path, commit: str, patch: Path, case_id: str) -> ReviewTask:
    return ReviewTask(
        case_id=case_id,
        repository=repo,
        base_commit=commit,
        issue="Preserve normalization while accepting None.",
        candidate_patch=patch,
        commands=[CommandSpec(argv=["pytest", "-q", "tests"], kind="pytest")],
        allowed_commands=[["pytest", "-q", "tests"]],
        protected_paths=["pyproject.toml"],
        command_timeout_seconds=5,
        task_timeout_seconds=30,
    )


@pytest.mark.integration
def test_reviewer_finding_and_failed_test_request_changes(make_repo, tmp_path: Path) -> None:
    repo, commit = make_repo(
        {
            "service.py": "def normalize(value: str) -> str:\n    return value.strip().lower()\n",
            "tests/test_service.py": (
                "from service import normalize\n\n"
                "def test_regression():\n    assert normalize(' HELLO ') == 'hello'\n\n"
                "def test_none():\n    assert normalize(None) == ''\n"
            ),
        }
    )
    patch = write_patch(
        tmp_path / "candidate.patch",
        "diff --git a/service.py b/service.py\n--- a/service.py\n+++ b/service.py\n"
        "@@ -1,2 +1,4 @@\n def normalize(value: str) -> str:\n"
        "-    return value.strip().lower()\n+    if value is None:\n+        return ''\n"
        "+    return value.strip()\n",
    )
    submission = ReviewerSubmission(
        summary="The None behavior is added but lowercase normalization regresses.",
        findings=[
            ReviewFinding(
                severity=Severity.P1,
                category=FindingCategory.REGRESSION,
                file="service.py",
                line=4,
                symbol="normalize",
                claim="The patch stops lowercasing non-None values.",
                evidence="The changed return uses strip() only and the regression test fails.",
                verification="Run pytest -q tests and observe test_regression.",
                confidence=0.99,
            )
        ],
    )
    report = ReviewRunner(
        tmp_path / "review-artifacts", ScriptedReviewerProvider(submission)
    ).run(review_task(repo, commit, patch, "review-regression"))

    assert report.verdict is Verdict.REQUEST_CHANGES
    assert report.review.submission.findings[0].file == "service.py"
    assert report.verification.commands[0].passed is False
    manifest = verify_manifest(Path(report.artifact_directory) / "review-manifest.json")
    assert manifest.run_id == report.run_id
    assert run_git(repo, "status", "--porcelain") == ""


@pytest.mark.integration
def test_clean_patch_and_empty_review_accept(make_repo, tmp_path: Path) -> None:
    repo, commit = make_repo(
        {
            "calc.py": "def add(a: int, b: int) -> int:\n    return a - b\n",
            "tests/test_calc.py": (
                "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
            ),
        }
    )
    patch = write_patch(
        tmp_path / "candidate.patch",
        "diff --git a/calc.py b/calc.py\n--- a/calc.py\n+++ b/calc.py\n"
        "@@ -1,2 +1,2 @@\n def add(a: int, b: int) -> int:\n"
        "-    return a - b\n+    return a + b\n",
    )
    report = ReviewRunner(
        tmp_path / "review-artifacts",
        ScriptedReviewerProvider(
            ReviewerSubmission(summary="No evidence-backed defects.", findings=[])
        ),
    ).run(review_task(repo, commit, patch, "review-clean"))

    assert report.verdict is Verdict.ACCEPT
    assert report.verification.commands[0].passed is True
    assert report.review.submission.findings == []


@pytest.mark.integration
def test_review_provider_failure_artifact_preserves_partial_evidence(
    make_repo, tmp_path: Path
) -> None:
    repo, commit = make_repo({"calc.py": "VALUE = 1\n"})
    patch = write_patch(
        tmp_path / "candidate.patch",
        "diff --git a/calc.py b/calc.py\n--- a/calc.py\n+++ b/calc.py\n"
        "@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n",
    )
    task = ReviewTask(
        case_id="review-partial-evidence",
        repository=repo,
        base_commit=commit,
        issue="Set VALUE to two.",
        candidate_patch=patch,
        commands=[],
        allowed_commands=[],
    )
    report = ReviewRunner(
        tmp_path / "review-artifacts", EvidenceFailureReviewer()
    ).run(task)

    assert report.outcome.value == "reviewer_failed"
    assert report.token_usage.input_tokens == 77
    assert report.provider_failure is not None
    artifact_root = Path(report.artifact_directory)
    artifact = artifact_root / "provider-failure.json"
    assert json.loads(artifact.read_text())["response_id"] == "partial-review"
    manifest = verify_manifest(artifact_root / "review-manifest.json")
    assert artifact.name in {entry.path for entry in manifest.artifacts}


@pytest.mark.integration
def test_review_blocks_before_provider_when_base_non_pytest_gate_fails(
    make_repo, tmp_path: Path
) -> None:
    repo, commit = make_repo({"bad.py": "import os\n"})
    patch = write_patch(
        tmp_path / "candidate.patch",
        "diff --git a/bad.py b/bad.py\n--- a/bad.py\n+++ b/bad.py\n"
        "@@ -1 +1,2 @@\n import os\n+VALUE = 1\n",
    )
    command = ["ruff", "check", "--no-fix", "."]
    task = ReviewTask(
        case_id="review-unhealthy-base-lint",
        repository=repo,
        base_commit=commit,
        issue="Add VALUE.",
        candidate_patch=patch,
        commands=[CommandSpec(argv=command, kind="ruff")],
        allowed_commands=[command],
    )
    provider = NeverCalledReviewer()

    report = ReviewRunner(tmp_path / "review-artifacts", provider).run(task)

    assert report.outcome.value == "preflight_failed"
    assert provider.calls == 0
    assert report.readiness is not None
    assert report.verification is None
    assert "non-pytest gate is not ready" in report.error


@pytest.mark.integration
def test_reviewer_result_returned_after_deadline_fails_closed(make_repo, tmp_path: Path) -> None:
    repo, commit = make_repo(
        {
            "calc.py": "def add(a: int, b: int) -> int:\n    return a - b\n",
        }
    )
    patch = write_patch(
        tmp_path / "candidate.patch",
        "diff --git a/calc.py b/calc.py\n--- a/calc.py\n+++ b/calc.py\n"
        "@@ -1,2 +1,2 @@\n def add(a: int, b: int) -> int:\n"
        "-    return a - b\n+    return a + b\n",
    )
    task = ReviewTask(
        case_id="reviewer-deadline",
        repository=repo,
        base_commit=commit,
        issue="Correct addition.",
        candidate_patch=patch,
        commands=[],
        allowed_commands=[],
        protected_paths=[],
        command_timeout_seconds=1,
        task_timeout_seconds=0.5,
    )

    report = ReviewRunner(tmp_path / "review-artifacts", SlowReviewerProvider()).run(task)

    assert report.outcome.value == "reviewer_failed"
    assert report.verdict is Verdict.FAILED
    assert report.error == "task deadline expired during Reviewer call"


@pytest.mark.integration
def test_review_cli_scripted(make_repo, tmp_path: Path, capsys) -> None:
    repo, commit = make_repo(
        {
            "value.py": "VALUE = 1\n",
            "tests/test_value.py": (
                "from value import VALUE\n\ndef test_value():\n    assert VALUE == 2\n"
            ),
        }
    )
    patch = write_patch(
        tmp_path / "candidate.patch",
        "diff --git a/value.py b/value.py\n--- a/value.py\n+++ b/value.py\n"
        "@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n",
    )
    task = review_task(repo, commit, patch, "review-cli")
    task_path = tmp_path / "review-task.json"
    task_path.write_text(task.model_dump_json(indent=2), encoding="utf-8")
    review_path = tmp_path / "scripted-review.json"
    review_path.write_text(
        json.dumps({"summary": "No defects found.", "findings": []}), encoding="utf-8"
    )

    exit_code = main(
        [
            "review",
            str(task_path),
            "--provider",
            "scripted",
            "--scripted-review",
            str(review_path),
            "--artifacts",
            str(tmp_path / "cli-artifacts"),
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["verdict"] == "accept"


@pytest.mark.integration
def test_review_cli_reuses_frozen_fix_task_with_candidate_patch(
    make_repo, tmp_path: Path, capsys
) -> None:
    repo, commit = make_repo(
        {
            "value.py": "VALUE = 1\n",
            "tests/test_value.py": (
                "from value import VALUE\n\ndef test_value():\n    assert VALUE == 2\n"
            ),
        }
    )
    patch = write_patch(
        tmp_path / "candidate.patch",
        "diff --git a/value.py b/value.py\n--- a/value.py\n+++ b/value.py\n"
        "@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n",
    )
    command = ["pytest", "-q", "tests/test_value.py"]
    fix_task = FixTask(
        case_id="review-from-fix-task",
        repository=repo,
        base_commit=commit,
        issue="Set the value to two.",
        commands=[CommandSpec(argv=command, kind="pytest")],
        allowed_commands=[command],
        writable_paths=["value.py", "tests/**"],
    )
    task_path = tmp_path / "fix-task.json"
    task_path.write_text(fix_task.model_dump_json(indent=2), encoding="utf-8")
    review_path = tmp_path / "scripted-review.json"
    review_path.write_text(
        json.dumps({"summary": "No defects found.", "findings": []}),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "review",
            str(task_path),
            "--candidate-patch",
            str(patch),
            "--provider",
            "scripted",
            "--scripted-review",
            str(review_path),
            "--artifacts",
            str(tmp_path / "review-from-fix-artifacts"),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["case_id"] == "review-from-fix-task-review"
    assert output["verdict"] == "accept"
