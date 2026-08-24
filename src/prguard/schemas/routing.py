"""Deterministic Independent Reviewer routing contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from prguard.schemas.common import (
    REVIEW_ROUTING_POLICY_VERSION,
    SCHEMA_VERSION,
    StrictModel,
)


class ReviewRoutingMode(StrEnum):
    ALWAYS = "always"
    SHADOW = "shadow"
    SELECTIVE = "selective"


class ReviewRoute(StrEnum):
    REVIEW = "review"
    SKIP = "skip"


class ReviewRiskFactor(StrictModel):
    code: str = Field(min_length=1, max_length=80)
    weight: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1, max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=100)


class ReviewSymbolImpact(StrictModel):
    symbol: str = Field(min_length=1, max_length=1000)
    path: str = Field(min_length=1, max_length=1000)
    change_kind: Literal["added", "modified", "deleted"]
    graph_source: Literal["base", "candidate"]
    root_resolution: Literal["exact", "unique_suffix", "ambiguous", "not_found"]
    direct_repository_callers: int = Field(ge=0)
    transitive_repository_callers: int = Field(ge=0)
    reachable_tests: list[str] = Field(default_factory=list, max_length=200)
    related_tests: list[str] = Field(default_factory=list, max_length=200)
    graph_truncated: bool = False


class ReviewRoutingResult(StrictModel):
    schema_version: str = SCHEMA_VERSION
    policy_version: str = REVIEW_ROUTING_POLICY_VERSION
    mode: ReviewRoutingMode
    recommended_route: ReviewRoute
    effective_route: ReviewRoute
    score: int = Field(ge=0)
    threshold: int = Field(ge=1)
    resolved_base_commit: str = Field(min_length=7, max_length=64)
    patch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fix_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    changed_files: list[str] = Field(default_factory=list, max_length=100)
    changed_python_files: list[str] = Field(default_factory=list, max_length=100)
    changed_test_files: list[str] = Field(default_factory=list, max_length=100)
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    pytest_scope: Literal["full", "targeted", "filtered", "none"]
    pytest_targets: list[str] = Field(default_factory=list, max_length=200)
    changed_symbols: list[str] = Field(default_factory=list, max_length=100)
    symbol_impacts: list[ReviewSymbolImpact] = Field(default_factory=list, max_length=100)
    covered_unchanged_tests: list[str] = Field(default_factory=list, max_length=200)
    uncovered_reachable_tests: list[str] = Field(default_factory=list, max_length=200)
    uncovered_related_tests: list[str] = Field(default_factory=list, max_length=200)
    analysis_incomplete: bool = False
    analysis_notes: list[str] = Field(default_factory=list, max_length=100)
    factors: list[ReviewRiskFactor] = Field(default_factory=list, max_length=100)
    duration_seconds: float = Field(ge=0)

    @model_validator(mode="after")
    def decision_matches_versioned_evidence(self) -> ReviewRoutingResult:
        if self.score != sum(factor.weight for factor in self.factors):
            raise ValueError("routing score must equal the sum of factor weights")
        expected = (
            ReviewRoute.REVIEW
            if self.score >= self.threshold
            else ReviewRoute.SKIP
        )
        if self.recommended_route is not expected:
            raise ValueError("recommended route must match score and threshold")
        if self.mode is ReviewRoutingMode.ALWAYS:
            if (
                self.recommended_route is not ReviewRoute.REVIEW
                or self.effective_route is not ReviewRoute.REVIEW
            ):
                raise ValueError("always mode must require Independent Review")
        elif self.mode is ReviewRoutingMode.SHADOW:
            if self.effective_route is not ReviewRoute.REVIEW:
                raise ValueError("shadow mode must still execute Independent Review")
        elif self.effective_route is not self.recommended_route:
            raise ValueError("selective mode must apply its recommended route")
        if self.analysis_incomplete and self.recommended_route is not ReviewRoute.REVIEW:
            raise ValueError("incomplete analysis must fail closed to Independent Review")
        if not set(self.changed_python_files).issubset(self.changed_files):
            raise ValueError("changed Python files must be part of the changed-file set")
        if not set(self.changed_test_files).issubset(self.changed_files):
            raise ValueError("changed test files must be part of the changed-file set")
        return self
