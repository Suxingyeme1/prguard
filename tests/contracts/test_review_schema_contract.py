from pathlib import Path

import pytest
from pydantic import ValidationError

from prguard.schemas import ReviewerSubmission, ReviewRepairTask, ReviewTask


def test_review_task_forbids_evaluator_and_implementer_secrets(tmp_path: Path) -> None:
    payload = {
        "case_id": "review-contract",
        "repository": tmp_path,
        "base_commit": "a" * 40,
        "issue": "Review the candidate.",
        "candidate_patch": tmp_path / "candidate.patch",
        "gold_patch": "secret",
        "implementer_reasoning": "private",
    }
    with pytest.raises(ValidationError):
        ReviewTask.model_validate(payload)


def test_reviewer_submission_requires_evidence_for_every_finding() -> None:
    with pytest.raises(ValidationError):
        ReviewerSubmission.model_validate(
            {
                "summary": "Defect found.",
                "findings": [
                    {
                        "severity": "P1",
                        "category": "regression",
                        "file": "service.py",
                        "claim": "Regression.",
                        "evidence": "",
                        "verification": "Run tests.",
                        "confidence": 0.9,
                    }
                ],
            }
        )


def test_review_repair_requires_bounded_relative_write_scope(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        ReviewRepairTask(
            case_id="review-repair-contract",
            repository=tmp_path,
            base_commit="a" * 40,
            issue="Repair only the candidate defect.",
            candidate_patch=tmp_path / "candidate.patch",
            writable_paths=["../outside.py"],
            task_timeout_seconds=30,
            review_timeout_seconds=10,
        )


def test_review_repair_reserves_time_for_implementer(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        ReviewRepairTask(
            case_id="review-repair-timeout",
            repository=tmp_path,
            base_commit="a" * 40,
            issue="Repair only the candidate defect.",
            candidate_patch=tmp_path / "candidate.patch",
            writable_paths=["src/**"],
            task_timeout_seconds=30,
            review_timeout_seconds=30,
        )
