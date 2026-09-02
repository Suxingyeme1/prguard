"""Shared schema primitives."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1.0.0"
HARNESS_VERSION = "0.1.0"
POLICY_VERSION = "argv-v3"
FIX_WORKFLOW_VERSION = "fix-v3"
ISSUE_TO_PR_WORKFLOW_VERSION = "issue-to-pr-v4"
PATCH_POLICY_VERSION = "patch-v2"
REVIEW_WORKFLOW_VERSION = "review-v2"
REVIEW_REPAIR_WORKFLOW_VERSION = "review-repair-v3"
REVIEW_ROUTING_POLICY_VERSION = "review-routing-v2"


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


class ExecutionBackend(StrEnum):
    HOST = "host"
    CONTAINER = "container"


class ContainerExecutionSpec(StrictModel):
    """Fail-closed Docker controls for deterministic verification commands."""

    engine: Literal["docker"] = "docker"
    image: str = Field(min_length=71, max_length=512)
    python_executable: Literal["python", "python3", "python3.12"] = "python3"
    network: Literal["none"] = "none"
    read_only_root: Literal[True] = True
    read_only_worktree: Literal[True] = True
    user: str = Field(default="65532:65532", pattern=r"^[0-9]+:[0-9]+$")
    memory_mb: int = Field(default=1024, ge=128, le=32768)
    cpus: float = Field(default=1.0, ge=0.1, le=16)
    pids_limit: int = Field(default=128, ge=16, le=4096)

    @field_validator("image")
    @classmethod
    def immutable_image_reference(cls, value: str) -> str:
        reference, separator, digest = value.rpartition("@")
        if not separator:
            digest = value
            reference = ""
        if len(digest) != 71 or not digest.startswith("sha256:"):
            raise ValueError("container image must use an immutable sha256 digest or image ID")
        if any(character not in "0123456789abcdef" for character in digest[7:]):
            raise ValueError("container image sha256 must be lowercase hexadecimal")
        if any(character.isspace() or ord(character) < 32 for character in value):
            raise ValueError("container image contains whitespace or control characters")
        if reference and re.fullmatch(r"[a-z0-9]+(?:[._:/-][a-z0-9]+)*", reference) is None:
            raise ValueError("container image repository reference is malformed")
        return value

    @field_validator("user")
    @classmethod
    def non_root_numeric_user(cls, value: str) -> str:
        uid, gid = (int(part) for part in value.split(":"))
        if uid == 0 or gid == 0 or uid > 4_294_967_294 or gid > 4_294_967_294:
            raise ValueError("container user and group must be valid non-root numeric IDs")
        return value


class RuntimeFileSpec(StrictModel):
    """Deterministic, non-deliverable file required only by the test runtime."""

    path: str = Field(min_length=1, max_length=1000)
    content: str = Field(max_length=100_000)
    reason: Literal["hatch_vcs_version_file"]

    @field_validator("path")
    @classmethod
    def repository_relative_path(cls, value: str) -> str:
        path = Path(value)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.parts
            or any(character in value for character in "\r\n\x00")
        ):
            raise ValueError("runtime file path must be safe and repository-relative")
        return value


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
