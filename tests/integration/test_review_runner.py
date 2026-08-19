import json
from pathlib import Path

import pytest

from prguard.cli import main
from prguard.harness import verify_manifest
from prguard.review import ReviewRunner
from prguard.reviewer import ScriptedReviewerProvider
from prguard.schemas import (
    CommandSpec,
    FindingCategory,
    ReviewerSubmission,
    ReviewFinding,
    ReviewTask,
    Severity,
    Verdict,
)
from tests.conftest import run_git


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
