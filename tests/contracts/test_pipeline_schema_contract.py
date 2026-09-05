from pathlib import Path

import pytest
from pydantic import ValidationError

from prguard.schemas import (
    ISSUE_TO_PR_WORKFLOW_VERSION,
    IssueToPRTask,
    ReviewRoutingMode,
)


def _task(tmp_path: Path, **overrides: object) -> IssueToPRTask:
    values: dict[str, object] = {
        "case_id": "pipeline-contract",
        "repository": tmp_path,
        "base_commit": "a" * 40,
        "issue": "Implement and review the change.",
        "commands": [{"argv": ["pytest", "-q"], "kind": "pytest"}],
        "allowed_commands": [["pytest", "-q"]],
        "writable_paths": ["src/**"],
        "task_timeout_seconds": 30,
        "fix_timeout_seconds": 15,
        "review_timeout_seconds": 10,
    }
    values.update(overrides)
    return IssueToPRTask.model_validate(values)


def test_issue_to_pr_defaults_to_compatible_always_review(tmp_path: Path) -> None:
    task = _task(tmp_path)

    assert task.review_routing_mode is ReviewRoutingMode.ALWAYS
    assert ISSUE_TO_PR_WORKFLOW_VERSION == "issue-to-pr-v6"


@pytest.mark.parametrize("mode", list(ReviewRoutingMode))
def test_issue_to_pr_accepts_versioned_review_routing_modes(
    tmp_path: Path, mode: ReviewRoutingMode
) -> None:
    assert _task(tmp_path, review_routing_mode=mode).review_routing_mode is mode


def test_issue_to_pr_stage_budgets_leave_repair_time(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        IssueToPRTask(
            case_id="pipeline-budget",
            repository=tmp_path,
            base_commit="a" * 40,
            issue="Implement and review the change.",
            writable_paths=["src/**"],
            task_timeout_seconds=30,
            fix_timeout_seconds=20,
            review_timeout_seconds=10,
        )
