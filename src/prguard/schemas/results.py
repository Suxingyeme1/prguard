"""Verification and run artifact contracts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field

from prguard.schemas.common import (
    HARNESS_VERSION,
    POLICY_VERSION,
    SCHEMA_VERSION,
    ArtifactEntry,
    ExecutionBackend,
    PolicyViolation,
    RunOutcome,
    RuntimeIdentity,
    StrictModel,
    TraceEvent,
)


class PatchApplicationResult(StrictModel):
    attempted: bool
    applied: bool
    patch_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    stderr: str = ""


class VerificationResult(StrictModel):
    command_index: int = Field(ge=0)
    kind: str
    argv: list[str]
    exit_code: int | None = None
    timed_out: bool = False
    duration_seconds: float = Field(ge=0)
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    execution_backend: ExecutionBackend = ExecutionBackend.HOST
    container_image: str | None = None
    runtime: RuntimeIdentity | None = None
    infrastructure_error: bool = False
    passed: bool


class HarnessReport(StrictModel):
    schema_version: str = Field(default=SCHEMA_VERSION)
    run_id: str
    case_id: str
    resolved_base_commit: str | None = None
    outcome: RunOutcome
    started_at: datetime
    finished_at: datetime
    duration_seconds: float = Field(ge=0)
    patch: PatchApplicationResult
    changed_test_base_results: list[VerificationResult] = Field(default_factory=list)
    commands: list[VerificationResult] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    policy_violations: list[PolicyViolation] = Field(default_factory=list)
    trace_events: list[TraceEvent] = Field(default_factory=list)
    artifact_directory: Path | None = None


class RunManifest(StrictModel):
    schema_version: str = Field(default=SCHEMA_VERSION)
    harness_version: str = Field(default=HARNESS_VERSION)
    policy_version: str = Field(default=POLICY_VERSION)
    run_id: str
    case_id: str
    resolved_base_commit: str
    created_at: datetime
    artifacts: list[ArtifactEntry]
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
