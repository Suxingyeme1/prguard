"""Top-level Issue-to-PR composition contracts."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field, model_validator

from prguard.schemas.common import (
    ISSUE_TO_PR_WORKFLOW_VERSION,
    SCHEMA_VERSION,
    StrictModel,
    TokenUsage,
    Verdict,
)
from prguard.schemas.fix import FixReport, FixTask
from prguard.schemas.review import ReviewRepairReport
from prguard.schemas.routing import ReviewRoutingMode, ReviewRoutingResult


class IssueToPROutcome(StrEnum):
    ACCEPTED = "accepted"
    FIX_FAILED = "fix_failed"
    REVIEW_FAILED = "review_failed"
    POLICY_BLOCKED = "policy_blocked"
    PREFLIGHT_FAILED = "preflight_failed"


class IssueToPRTask(FixTask):
    """One bounded budget spanning implementation, review, and optional repair."""

    task_timeout_seconds: float = Field(default=1200, gt=0, le=7200)
    fix_timeout_seconds: float = Field(default=600, gt=0, le=3600)
    review_timeout_seconds: float = Field(default=300, gt=0, le=3600)
    review_max_tool_calls: int = Field(default=12, ge=1, le=100)
    review_routing_mode: ReviewRoutingMode = ReviewRoutingMode.ALWAYS

    @model_validator(mode="after")
    def stage_budgets_leave_repair_time(self) -> IssueToPRTask:
        if self.fix_timeout_seconds + self.review_timeout_seconds >= self.task_timeout_seconds:
            raise ValueError("fix and review budgets must leave time for final repair verification")
        return self


class IssueToPRReport(StrictModel):
    schema_version: str = SCHEMA_VERSION
    workflow_version: str = ISSUE_TO_PR_WORKFLOW_VERSION
    run_id: str
    case_id: str
    resolved_base_commit: str | None = None
    outcome: IssueToPROutcome
    verdict: Verdict
    fix: FixReport | None = None
    review_routing: ReviewRoutingResult | None = None
    review_repair: ReviewRepairReport | None = None
    final_patch: Path | None = None
    error: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    duration_seconds: float = Field(ge=0)
    artifact_directory: Path
