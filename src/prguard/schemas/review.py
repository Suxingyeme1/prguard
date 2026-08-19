"""Independent Reviewer workflow contracts."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator, model_validator

from prguard.schemas.common import (
    REVIEW_REPAIR_WORKFLOW_VERSION,
    REVIEW_WORKFLOW_VERSION,
    SCHEMA_VERSION,
    CommandSpec,
    StrictModel,
    TokenUsage,
    Verdict,
)
from prguard.schemas.findings import ReviewFinding
from prguard.schemas.fix import AgentToolCall, ProposalEnvelope
from prguard.schemas.results import HarnessReport


class ReviewOutcome(StrEnum):
    REVIEWED = "reviewed"
    REVIEWER_FAILED = "reviewer_failed"
    PATCH_FAILED = "patch_failed"
    POLICY_BLOCKED = "policy_blocked"
    PREFLIGHT_FAILED = "preflight_failed"


class ReviewTask(StrictModel):
    schema_version: str = SCHEMA_VERSION
    case_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    repository: Path
    base_commit: str = Field(min_length=7, max_length=64, pattern=r"^[0-9a-fA-F]+$")
    issue: str = Field(min_length=1, max_length=50_000)
    candidate_patch: Path
    commands: list[CommandSpec] = Field(default_factory=list, max_length=32)
    allowed_commands: list[list[str]] = Field(default_factory=list, max_length=32)
    protected_paths: list[str] = Field(default_factory=list, max_length=128)
    command_timeout_seconds: float = Field(default=120, gt=0, le=3600)
    task_timeout_seconds: float = Field(default=900, gt=0, le=7200)
    max_output_bytes: int = Field(default=200_000, ge=1024, le=10_000_000)
    max_tool_calls: int = Field(default=24, ge=1, le=100)
    max_file_bytes: int = Field(default=100_000, ge=1024, le=1_000_000)
    max_context_bytes: int = Field(default=500_000, ge=4096, le=5_000_000)

    @field_validator("protected_paths")
    @classmethod
    def relative_protected_paths(cls, values: list[str]) -> list[str]:
        for value in values:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts or not value.strip():
                raise ValueError("protected paths must be non-empty and repository-relative")
        return values

    @model_validator(mode="after")
    def commands_must_be_allowlisted(self) -> ReviewTask:
        allowed = {tuple(argv) for argv in self.allowed_commands}
        if any(tuple(command.argv) not in allowed for command in self.commands):
            raise ValueError("every verification command must be in allowed_commands")
        return self


class ReviewRepairTask(ReviewTask):
    """Candidate-review task that grants one bounded replacement-patch attempt."""

    writable_paths: list[str] = Field(min_length=1, max_length=128)
    max_patch_bytes: int = Field(default=200_000, ge=128, le=2_000_000)
    max_changed_files: int = Field(default=12, ge=1, le=100)
    review_timeout_seconds: float = Field(default=300, gt=0, le=3600)

    @field_validator("writable_paths")
    @classmethod
    def relative_writable_paths(cls, values: list[str]) -> list[str]:
        for value in values:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts or not value.strip():
                raise ValueError("writable paths must be non-empty and repository-relative")
        return values

    @model_validator(mode="after")
    def review_timeout_within_task_timeout(self) -> ReviewRepairTask:
        if self.review_timeout_seconds >= self.task_timeout_seconds:
            raise ValueError("review_timeout_seconds must leave time for controlled repair")
        return self


class ReviewerSubmission(StrictModel):
    summary: str = Field(min_length=1, max_length=4000)
    findings: list[ReviewFinding] = Field(default_factory=list, max_length=50)


class ReviewEnvelope(StrictModel):
    submission: ReviewerSubmission
    provider: str
    model: str
    response_id: str | None = None
    provider_metadata: dict[str, str] = Field(default_factory=dict)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    tool_calls: list[AgentToolCall] = Field(default_factory=list)


class ReviewReport(StrictModel):
    schema_version: str = SCHEMA_VERSION
    workflow_version: str = REVIEW_WORKFLOW_VERSION
    run_id: str
    case_id: str
    resolved_base_commit: str | None = None
    outcome: ReviewOutcome
    verdict: Verdict
    verification: HarnessReport | None = None
    review: ReviewEnvelope | None = None
    error: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    duration_seconds: float = Field(ge=0)
    artifact_directory: Path


class ReviewRepairOutcome(StrEnum):
    ACCEPTED_WITHOUT_REPAIR = "accepted_without_repair"
    ACCEPTED_AFTER_REPAIR = "accepted_after_repair"
    REPAIR_FAILED = "repair_failed"
    REVIEW_FAILED = "review_failed"
    POLICY_BLOCKED = "policy_blocked"
    PREFLIGHT_FAILED = "preflight_failed"


class ReviewRepairReport(StrictModel):
    schema_version: str = SCHEMA_VERSION
    workflow_version: str = REVIEW_REPAIR_WORKFLOW_VERSION
    run_id: str
    case_id: str
    resolved_base_commit: str | None = None
    outcome: ReviewRepairOutcome
    verdict: Verdict
    initial_review: ReviewReport | None = None
    repair_proposal: ProposalEnvelope | None = None
    final_verification: HarnessReport | None = None
    final_patch: Path | None = None
    error: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    duration_seconds: float = Field(ge=0)
    artifact_directory: Path
