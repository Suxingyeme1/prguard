"""Shared schema primitives."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1.0.0"
HARNESS_VERSION = "0.1.0"
POLICY_VERSION = "argv-v1"
FIX_WORKFLOW_VERSION = "fix-v1"
ISSUE_TO_PR_WORKFLOW_VERSION = "issue-to-pr-v1"
PATCH_POLICY_VERSION = "patch-v1"
REVIEW_WORKFLOW_VERSION = "review-v1"
REVIEW_REPAIR_WORKFLOW_VERSION = "review-repair-v1"


def utc_now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class TaskMode(StrEnum):
    REVIEW = "review"
    REVIEW_REPAIR = "review_repair"
    ISSUE_TO_PR = "issue_to_pr"


class Verdict(StrEnum):
    PENDING = "pending"
    ACCEPT = "accept"
    REQUEST_CHANGES = "request_changes"
    ESCALATE = "escalate"
    FAILED = "failed"


class RunOutcome(StrEnum):
    PASSED = "passed"
    FAILED_VERIFICATION = "failed_verification"
    PATCH_FAILED = "patch_failed"
    TIMED_OUT = "timed_out"
    POLICY_BLOCKED = "policy_blocked"
    PREFLIGHT_FAILED = "preflight_failed"


class TraceEvent(StrictModel):
    sequence: int = Field(ge=0)
    timestamp: datetime = Field(default_factory=utc_now)
    kind: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=1000)
    data: dict[str, Any] = Field(default_factory=dict)


class TokenUsage(StrictModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0, ge=0)


class CommandSpec(StrictModel):
    argv: list[str] = Field(min_length=1, max_length=64)
    kind: str = Field(default="test", min_length=1, max_length=40)
    timeout_seconds: float | None = Field(default=None, gt=0, le=3600)

    @field_validator("argv")
    @classmethod
    def validate_argv(cls, argv: list[str]) -> list[str]:
        if any(not item or "\x00" in item for item in argv):
            raise ValueError("argv entries must be non-empty and contain no NUL bytes")
        return argv


class ArtifactEntry(StrictModel):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class PolicyViolation(StrictModel):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=1000)
    paths: list[str] = Field(default_factory=list)
