from pathlib import Path

import pytest
from pydantic import ValidationError

from prguard.schemas import (
    CodingTaskState,
    FindingCategory,
    ReviewFinding,
    Severity,
    Task,
    TaskMode,
)


def task_payload() -> dict[str, object]:
    return {
        "case_id": "case-1",
        "repository": "/tmp/repo",
        "base_commit": "a" * 40,
        "issue": "Fix the edge case.",
        "commands": [],
        "allowed_commands": [],
    }


def test_task_forbids_evaluator_only_fields() -> None:
    payload = task_payload() | {"gold_patch": "secret", "hidden_tests": ["test_secret"]}
    with pytest.raises(ValidationError):
        Task.model_validate(payload)


def test_task_public_context_has_no_evaluator_secrets() -> None:
    context = Task.model_validate(task_payload()).public_context()
    assert "gold_patch" not in context
    assert "hidden_tests" not in context
    assert "defects" not in context


def test_task_rejects_parent_protected_path() -> None:
    with pytest.raises(ValidationError):
        Task.model_validate(task_payload() | {"protected_paths": ["../secret"]})


def test_finding_requires_evidence_and_relative_source_anchor() -> None:
    valid = {
        "severity": Severity.P1,
        "category": FindingCategory.CORRECTNESS,
        "file": "src/service.py",
        "line": 10,
        "claim": "The branch returns the wrong value.",
        "evidence": "The changed branch returns -1 for an input specified as zero.",
        "verification": "Run pytest tests/test_service.py.",
        "confidence": 0.9,
    }
    finding = ReviewFinding.model_validate(valid)
    assert finding.line == 10
    with pytest.raises(ValidationError):
        ReviewFinding.model_validate(valid | {"evidence": ""})
    with pytest.raises(ValidationError):
        ReviewFinding.model_validate(valid | {"file": "../service.py"})


def test_state_mutable_defaults_are_not_shared() -> None:
    values = {
        "case_id": "case-1",
        "mode": TaskMode.REVIEW,
        "repository": Path("/tmp/repo"),
        "base_commit": "a" * 40,
        "issue": "Issue",
    }
    first = CodingTaskState(**values)
    second = CodingTaskState(**values)
    first.changed_files.append("src/a.py")
    assert second.changed_files == []
