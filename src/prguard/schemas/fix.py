"""Issue-to-Patch workflow contracts."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from prguard.schemas.common import (
    FIX_WORKFLOW_VERSION,
    SCHEMA_VERSION,
    CommandSpec,
    ContainerExecutionSpec,
    RuntimeFileSpec,
    StrictModel,
    TokenUsage,
)
from prguard.schemas.results import HarnessReport


class FixOutcome(StrEnum):
    ACCEPTED = "accepted"
    FAILED_VERIFICATION = "failed_verification"
    AGENT_FAILED = "agent_failed"
    POLICY_BLOCKED = "policy_blocked"
    PREFLIGHT_FAILED = "preflight_failed"


class FixTask(StrictModel):
    schema_version: str = SCHEMA_VERSION
    case_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    repository: Path
    base_commit: str = Field(min_length=7, max_length=64, pattern=r"^[0-9a-fA-F]+$")
    issue: str = Field(min_length=1, max_length=50_000)
    commands: list[CommandSpec] = Field(min_length=1, max_length=32)
    allowed_commands: list[list[str]] = Field(min_length=1, max_length=32)
    writable_paths: list[str] = Field(min_length=1, max_length=128)
    protected_paths: list[str] = Field(default_factory=list, max_length=128)
    command_timeout_seconds: float = Field(default=120, gt=0, le=3600)
    task_timeout_seconds: float = Field(default=900, gt=0, le=7200)
    max_output_bytes: int = Field(default=200_000, ge=1024, le=10_000_000)
    max_tool_calls: int = Field(default=24, ge=1, le=100)
    max_file_bytes: int = Field(default=100_000, ge=1024, le=1_000_000)
    max_context_bytes: int = Field(default=500_000, ge=4096, le=5_000_000)
    max_patch_bytes: int = Field(default=200_000, ge=128, le=2_000_000)
    max_changed_files: int = Field(default=12, ge=1, le=100)
    max_repair_attempts: int = Field(default=1, ge=0, le=1)
    container: ContainerExecutionSpec | None = None
    runtime_files: list[RuntimeFileSpec] = Field(default_factory=list, max_length=16)

    @field_validator("writable_paths", "protected_paths")
    @classmethod
    def relative_path_patterns(cls, values: list[str]) -> list[str]:
        for value in values:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts or not value.strip():
                raise ValueError("path patterns must be non-empty and repository-relative")
        return values

    @model_validator(mode="after")
    def commands_must_be_allowlisted(self) -> FixTask:
        allowed = {tuple(argv) for argv in self.allowed_commands}
        if any(tuple(command.argv) not in allowed for command in self.commands):
            raise ValueError("every verification command must be in allowed_commands")
        return self


class ReplaceTextEdit(StrictModel):
    operation: Literal["replace_text"]
    path: str = Field(min_length=1, max_length=1000)
    old_text: str = Field(min_length=1, max_length=200_000)
    new_text: str = Field(max_length=200_000)

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        path = Path(value)
        if (
            path.is_absolute()
            or ".." in path.parts
            or any(char in value for char in "\r\n\x00")
        ):
            raise ValueError("edit path must be safe and repository-relative")
        return value


class CreateFileEdit(StrictModel):
    operation: Literal["create_file"]
    path: str = Field(min_length=1, max_length=1000)
    content: str = Field(max_length=200_000)

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        path = Path(value)
        if (
            path.is_absolute()
            or ".." in path.parts
            or any(char in value for char in "\r\n\x00")
        ):
            raise ValueError("edit path must be safe and repository-relative")
        return value


TextEdit = Annotated[ReplaceTextEdit | CreateFileEdit, Field(discriminator="operation")]


class ImplementerProposal(StrictModel):
    plan: list[str] = Field(min_length=1, max_length=12)
    summary: str = Field(min_length=1, max_length=4000)
    patch: str | None = Field(default=None, min_length=1)
    edits: list[TextEdit] = Field(default_factory=list, max_length=32)
    tests_changed: bool

    @model_validator(mode="after")
    def exactly_one_edit_format(self) -> ImplementerProposal:
        if (self.patch is not None) == bool(self.edits):
            raise ValueError("proposal must contain exactly one of patch or structured edits")
        return self


class AgentToolCall(StrictModel):
    sequence: int = Field(ge=0)
    name: str
    arguments: dict[str, object] = Field(default_factory=dict)
    succeeded: bool
    output_bytes: int = Field(ge=0)
    error: str | None = None


class ProposalEnvelope(StrictModel):
    proposal: ImplementerProposal
    provider: str
    model: str
    response_id: str | None = None
    provider_metadata: dict[str, str] = Field(default_factory=dict)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    tool_calls: list[AgentToolCall] = Field(default_factory=list)


class FixAttempt(StrictModel):
    attempt: int = Field(ge=0, le=1)
    proposal: ProposalEnvelope | None = None
    verification: HarnessReport | None = None
    error: str | None = None


class FixReport(StrictModel):
    schema_version: str = SCHEMA_VERSION
    workflow_version: str = FIX_WORKFLOW_VERSION
    run_id: str
    case_id: str
    resolved_base_commit: str | None = None
    outcome: FixOutcome
    attempts: list[FixAttempt] = Field(default_factory=list, max_length=2)
    final_patch: Path | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    duration_seconds: float = Field(ge=0)
    artifact_directory: Path
