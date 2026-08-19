from pathlib import Path

import pytest
from pydantic import ValidationError

from prguard.schemas import IssueToPRTask


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
