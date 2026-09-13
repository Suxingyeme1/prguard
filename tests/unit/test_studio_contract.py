import pytest

from prguard.schemas import CommandSpec, FixTask
from prguard.studio import FrozenTaskEnvelope, StudioError, StudioService


def test_review_budget_preserves_total_limit_and_reserves_repair_time(tmp_path):
    task = FixTask(
        case_id="budget", repository=tmp_path, base_commit="a" * 40, issue="Fix behavior",
        commands=[CommandSpec(argv=["pytest", "-q"], kind="pytest")],
        allowed_commands=[["pytest", "-q"]], writable_paths=["src/**"],
    )
    for timeout in (15, 90, 900, 7200):
        task.task_timeout_seconds = timeout
        reviewed = StudioService._review_task(task, 7)
        assert reviewed.task_timeout_seconds == timeout
        assert reviewed.fix_timeout_seconds + reviewed.review_timeout_seconds < timeout
        assert reviewed.review_max_tool_calls == 7
        assert reviewed.commands == task.commands
        assert reviewed.protected_paths == task.protected_paths
    task.task_timeout_seconds = 2
    with pytest.raises(StudioError, match="at least 15"):
        StudioService._review_task(task, 7)


def test_review_envelope_cannot_omit_the_frozen_reviewer_configuration():
    with pytest.raises(ValueError, match="disagree"):
        FrozenTaskEnvelope(workflow="reviewed_fix", task={})
