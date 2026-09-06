"""Input Task and mutable workflow State contracts."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from prguard.schemas.common import (
    SCHEMA_VERSION,
    CommandSpec,
    ContainerExecutionSpec,
    RuntimeFileSpec,
    StrictModel,
    TaskMode,
    TokenUsage,
    TraceEvent,
    Verdict,
)


class Task(StrictModel):
    schema_version: str = Field(default=SCHEMA_VERSION)
    case_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    mode: TaskMode = TaskMode.REVIEW
    repository: Path
    base_commit: str = Field(min_length=7, max_length=64, pattern=r"^[0-9a-fA-F]+$")
    issue: str = Field(min_length=1, max_length=50_000)
    candidate_patch: Path | None = None
    commands: list[CommandSpec] = Field(default_factory=list, max_length=32)
    allowed_commands: list[list[str]] = Field(default_factory=list, max_length=32)
    writable_paths: list[str] = Field(default_factory=list, max_length=128)
    protected_paths: list[str] = Field(default_factory=list, max_length=128)
    command_timeout_seconds: float = Field(default=120, gt=0, le=3600)
    task_timeout_seconds: float = Field(default=600, gt=0, le=7200)
    max_output_bytes: int = Field(default=200_000, ge=1024, le=10_000_000)
    require_changed_tests_fail_on_base: bool = False
    container: ContainerExecutionSpec | None = None
    runtime_files: list[RuntimeFileSpec] = Field(default_factory=list, max_length=16)

    @field_validator("writable_paths", "protected_paths")
    @classmethod
    def relative_policy_paths(cls, values: list[str]) -> list[str]:
        for value in values:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts or not value.strip():
                raise ValueError("policy paths must be non-empty and repository-relative")
        return values

    def public_context(self) -> dict[str, object]:
        """Return the only Task payload later agents may receive."""
        return self.model_dump(mode="json")


class CodingTaskState(StrictModel):
    schema_version: str = Field(default=SCHEMA_VERSION)
    run_id: UUID = Field(default_factory=uuid4)
    case_id: str
    mode: TaskMode
    repository: Path
    base_commit: str
    issue: str
    candidate_patch: Path | None = None
    changed_files: list[str] = Field(default_factory=list)
    allowed_commands: list[list[str]] = Field(default_factory=list)
    implementation_attempts: int = Field(default=0, ge=0)
    review_attempts: int = Field(default=0, ge=0)
    verification_results: list[VerificationResult] = Field(default_factory=list)
    container: ContainerExecutionSpec | None = None
    findings: list[ReviewFinding] = Field(default_factory=list)
    verdict: Verdict = Verdict.PENDING
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    trace_events: list[TraceEvent] = Field(default_factory=list)


from prguard.schemas.findings import ReviewFinding  # noqa: E402
from prguard.schemas.results import VerificationResult  # noqa: E402

CodingTaskState.model_rebuild()
