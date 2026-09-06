"""GitHub Issue onboarding and repository-profile contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from prguard.schemas.common import (
    CommandSpec,
    ContainerExecutionSpec,
    RuntimeFileSpec,
    StrictModel,
)


class GitHubIssueReference(StrictModel):
    owner: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$",
    )
    repository: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    number: int = Field(ge=1)
    url: str


class GitHubIssueSnapshot(StrictModel):
    reference: GitHubIssueReference
    title: str = Field(min_length=1, max_length=1000)
    body: str = Field(default="", max_length=49_000)
    state: Literal["open", "closed"]
    repository_url: str
    clone_url: str
    default_branch: str = Field(min_length=1, max_length=255)
    base_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    private: bool = False
    archived: bool = False

    @property
    def issue_text(self) -> str:
        heading = f"GitHub Issue #{self.reference.number}: {self.title}"
        return f"{heading}\n\n{self.body}" if self.body else heading


class LocalIssueSnapshot(StrictModel):
    source_repository: Path
    requested_base_commit: str = Field(min_length=1, max_length=255)
    base_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    issue_text: str = Field(min_length=1, max_length=50_000)
    issue_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProjectConfig(StrictModel):
    """Optional versioned `.prguard.toml` values owned by a repository."""

    version: Literal[1] = 1
    verification_commands: list[list[str]] = Field(min_length=1, max_length=32)
    writable_paths: list[str] = Field(min_length=1, max_length=128)
    protected_paths: list[str] = Field(default_factory=list, max_length=128)
    command_timeout_seconds: float = Field(default=120, gt=0, le=3600)
    task_timeout_seconds: float = Field(default=900, gt=0, le=7200)
    max_repair_attempts: int = Field(default=1, ge=0, le=1)

    @field_validator("writable_paths", "protected_paths")
    @classmethod
    def relative_patterns(cls, values: list[str]) -> list[str]:
        for value in values:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts or not value.strip():
                raise ValueError("project path patterns must be repository-relative")
        return values


class DiscoveredProjectPolicy(StrictModel):
    commands: list[CommandSpec] = Field(min_length=1, max_length=32)
    writable_paths: list[str] = Field(min_length=1, max_length=128)
    protected_paths: list[str] = Field(min_length=1, max_length=128)
    source: Literal["repository_config", "operator_config", "deterministic_discovery"]
    warnings: list[str] = Field(default_factory=list)
    command_timeout_seconds: float = Field(default=120, gt=0, le=3600)
    task_timeout_seconds: float = Field(default=900, gt=0, le=7200)
    max_repair_attempts: int = Field(default=1, ge=0, le=1)
    runtime_files: list[RuntimeFileSpec] = Field(default_factory=list, max_length=16)


class ProjectPolicyInspection(StrictModel):
    repository: Path
    requested_base_commit: str = Field(min_length=1, max_length=255)
    base_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    status: Literal["ready", "needs_config"]
    config_path: Path | None = None
    policy_source: Literal[
        "repository_config", "operator_config", "deterministic_discovery"
    ] | None = None
    commands: list[CommandSpec] = Field(default_factory=list, max_length=32)
    writable_paths: list[str] = Field(default_factory=list, max_length=128)
    protected_paths: list[str] = Field(default_factory=list, max_length=256)
    runtime_files: list[RuntimeFileSpec] = Field(default_factory=list, max_length=16)
    signals: list[str] = Field(default_factory=list, max_length=32)
    warnings: list[str] = Field(default_factory=list, max_length=32)
    blocking_reasons: list[str] = Field(default_factory=list, max_length=16)
    next_actions: list[str] = Field(default_factory=list, max_length=16)
    suggested_config: str | None = None


class TaskPreparationReport(StrictModel):
    issue: GitHubIssueSnapshot
    checkout: Path
    task_path: Path
    config_path: Path | None = None
    policy_source: Literal["repository_config", "operator_config", "deterministic_discovery"]
    execution_backend: Literal["host", "container"]
    container: ContainerExecutionSpec | None = None
    commands: list[CommandSpec]
    writable_paths: list[str]
    protected_paths: list[str]
    runtime_files: list[RuntimeFileSpec] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LocalTaskPreparationReport(StrictModel):
    issue: LocalIssueSnapshot
    checkout: Path
    task_path: Path
    config_path: Path | None = None
    policy_source: Literal["repository_config", "operator_config", "deterministic_discovery"]
    execution_backend: Literal["host", "container"]
    container: ContainerExecutionSpec | None = None
    commands: list[CommandSpec]
    writable_paths: list[str]
    protected_paths: list[str]
    runtime_files: list[RuntimeFileSpec] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
