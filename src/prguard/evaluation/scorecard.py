"""Hash-bound, evaluator-only Shadow Reviewer scorecards.

This module consumes frozen public artifacts after Agent execution. It is deliberately not
imported by :mod:`prguard.schemas`, so evaluator labels cannot enter a Fix or Review task through
the product's public schema surface.
"""

from __future__ import annotations

import json
from datetime import date
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import Field, model_validator

from prguard.harness.artifacts import sha256_file
from prguard.schemas import (
    REVIEW_ROUTING_POLICY_VERSION,
    ReviewRoute,
    ReviewRoutingMode,
    ReviewRoutingResult,
    TokenUsage,
    Verdict,
)
from prguard.schemas.common import StrictModel

SHADOW_EVALUATION_SCHEMA_VERSION = "prguard-shadow-evaluation-1"
SHADOW_SCORECARD_SCHEMA_VERSION = "prguard-shadow-scorecard-1"


class EvidenceSource(StrEnum):
    REAL_REPOSITORY = "real_repository"
    DETERMINISTIC_FIXTURE = "deterministic_fixture"


class EvaluatorLabel(StrEnum):
    CLEAN = "clean"
    DEFECTIVE = "defective"


class ReviewerEvidenceReference(StrictModel):
    artifact: str = Field(min_length=1, max_length=1000)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_id: str = Field(min_length=1, max_length=120)


class ShadowEvaluationCase(StrictModel):
    case_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    source: EvidenceSource
    repository: str = Field(min_length=1, max_length=500)
    issue_url: str | None = Field(default=None, max_length=2000)
    candidate_patch_artifact: str = Field(min_length=1, max_length=1000)
    candidate_patch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    routing_artifact: str = Field(min_length=1, max_length=1000)
    routing_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_label: EvaluatorLabel
    label_visibility: Literal["evaluator_only_not_in_agent_context"]
    candidate_wider_gate: Literal["passed", "failed"]
    evaluator_checks: list[str] = Field(min_length=1, max_length=20)
    reviewer_evidence: ReviewerEvidenceReference | None = None

    @model_validator(mode="after")
    def label_matches_wider_gate(self) -> ShadowEvaluationCase:
        expected = "passed" if self.evaluator_label is EvaluatorLabel.CLEAN else "failed"
        if self.candidate_wider_gate != expected:
            raise ValueError("evaluator label must agree with the frozen candidate wider gate")
        return self


class ShadowEvaluationDataset(StrictModel):
    schema_version: Literal["prguard-shadow-evaluation-1"] = (
        SHADOW_EVALUATION_SCHEMA_VERSION
    )
    frozen_at: date
    policy_version: str = REVIEW_ROUTING_POLICY_VERSION
    cases: list[ShadowEvaluationCase] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_cases(self) -> ShadowEvaluationDataset:
        identifiers = [case.case_id for case in self.cases]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("shadow evaluation case_id values must be unique")
        return self


class ReviewerObservation(StrictModel):
    verdict: Verdict
    finding_count: int = Field(ge=0)
    confirmed_incremental_findings: int = Field(ge=0)
    rejected_findings: int = Field(ge=0)
    unresolved_findings: int = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    token_usage: TokenUsage
    repair_rounds: int = Field(ge=0, le=1)

    @model_validator(mode="after")
    def every_finding_has_one_disposition(self) -> ReviewerObservation:
        dispositions = (
            self.confirmed_incremental_findings
            + self.rejected_findings
            + self.unresolved_findings
        )
        if dispositions != self.finding_count:
            raise ValueError("Reviewer finding dispositions must sum to finding_count")
        return self


class Ratio(StrictModel):
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    rate: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def rate_matches_counts(self) -> Ratio:
        expected = self.numerator / self.denominator if self.denominator else None
        if self.rate != expected:
            raise ValueError("ratio rate must be derived exactly from numerator and denominator")
        return self


class ShadowCaseScore(StrictModel):
    case_id: str
    source: EvidenceSource
    repository: str
    evaluator_label: EvaluatorLabel
    resolved_base_commit: str
    candidate_patch_sha256: str
    recommended_route: ReviewRoute
    routing_score: int = Field(ge=0)
    routing_threshold: int = Field(ge=1)
    reviewer_observed: bool
    reviewer_verdict: Verdict | None = None
    confirmed_incremental_findings: int = Field(ge=0)
    reviewer_duration_seconds: float = Field(ge=0)
    reviewer_input_tokens: int = Field(ge=0)
    reviewer_output_tokens: int = Field(ge=0)
    repair_rounds: int = Field(ge=0, le=1)


class ShadowScorecard(StrictModel):
    schema_version: Literal["prguard-shadow-scorecard-1"] = (
        SHADOW_SCORECARD_SCHEMA_VERSION
    )
    source_schema_version: Literal["prguard-shadow-evaluation-1"]
    frozen_at: date
    policy_version: str
    case_count: int = Field(ge=1)
    clean_cases: int = Field(ge=0)
    defective_cases: int = Field(ge=0)
    real_repository_cases: int = Field(ge=0)
    reviewer_observed_cases: int = Field(ge=0)
    recommended_reviews: int = Field(ge=0)
    recommended_skips: int = Field(ge=0)
    reviewer_coverage: Ratio
    false_routes: Ratio
    false_skips: Ratio
    false_blocks: Ratio
    defective_cases_caught_by_reviewer: Ratio
    confirmed_incremental_findings: int = Field(ge=0)
    total_reviewer_duration_seconds: float = Field(ge=0)
    total_reviewer_input_tokens: int = Field(ge=0)
    total_reviewer_output_tokens: int = Field(ge=0)
    total_repair_rounds: int = Field(ge=0)
    selective_activation_ready: bool
    activation_blockers: list[str] = Field(default_factory=list)
    cases: list[ShadowCaseScore]


def _ratio(numerator: int, denominator: int) -> Ratio:
    return Ratio(
        numerator=numerator,
        denominator=denominator,
        rate=numerator / denominator if denominator else None,
    )


def _safe_artifact(evidence_root: Path, relative_value: str) -> Path:
    relative = PurePosixPath(relative_value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"unsafe evaluator artifact path: {relative_value}")
    root = evidence_root.expanduser().resolve()
    candidate = root.joinpath(*relative.parts)
    if candidate.is_symlink():
        raise ValueError(f"evaluator artifact must not be a symlink: {relative_value}")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"evaluator artifact escapes evidence root: {relative_value}")
    return resolved


def _verified_artifact(evidence_root: Path, relative: str, expected_sha256: str) -> Path:
    path = _safe_artifact(evidence_root, relative)
    if sha256_file(path) != expected_sha256:
        raise ValueError(f"evaluator artifact hash mismatch: {relative}")
    return path


def _reviewer_observation(
    evidence_root: Path,
    reference: ReviewerEvidenceReference,
    *,
    route: ReviewRoutingResult,
) -> ReviewerObservation:
    path = _verified_artifact(
        evidence_root,
        reference.artifact,
        reference.artifact_sha256,
    )
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != "prguard-public-evidence-1":
            raise ValueError("unsupported Reviewer evidence schema")
        matches = [
            value
            for value in manifest["cases"]
            if value.get("case_id") == reference.case_id
        ]
        if len(matches) != 1:
            raise ValueError("Reviewer evidence case must resolve exactly once")
        value = matches[0]
        if value["base_commit"] != route.resolved_base_commit:
            raise ValueError("Reviewer and routing Base Commit do not match")
        if value["candidate_patch_sha256"] != route.patch_sha256:
            raise ValueError("Reviewer and routing candidate Patch do not match")
        return ReviewerObservation(
            verdict=Verdict(value["review_verdict"]),
            finding_count=value["finding_count"],
            confirmed_incremental_findings=value["incremental_finding_count"],
            rejected_findings=value["rejected_finding_count"],
            unresolved_findings=value["unresolved_finding_count"],
            duration_seconds=value["review_duration_seconds"],
            token_usage=TokenUsage.model_validate(value["review_token_usage"]),
            repair_rounds=value["repair_rounds"],
        )
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed Reviewer evidence: {reference.artifact}") from exc


def load_shadow_evaluation(
    evidence_root: Path,
    dataset_artifact: str,
) -> tuple[ShadowEvaluationDataset, list[tuple[ReviewRoutingResult, ReviewerObservation | None]]]:
    """Load and cryptographically bind every Patch, route, and optional Reviewer record."""

    dataset_path = _safe_artifact(evidence_root, dataset_artifact)
    dataset = ShadowEvaluationDataset.model_validate_json(dataset_path.read_bytes())
    observations: list[tuple[ReviewRoutingResult, ReviewerObservation | None]] = []
    for case in dataset.cases:
        _verified_artifact(
            evidence_root,
            case.candidate_patch_artifact,
            case.candidate_patch_sha256,
        )
        route_path = _verified_artifact(
            evidence_root,
            case.routing_artifact,
            case.routing_artifact_sha256,
        )
        route = ReviewRoutingResult.model_validate_json(route_path.read_bytes())
        if route.policy_version != dataset.policy_version:
            raise ValueError("routing policy version does not match frozen evaluation dataset")
        if route.mode is not ReviewRoutingMode.SHADOW:
            raise ValueError("scorecard accepts only Shadow routing observations")
        if route.effective_route is not ReviewRoute.REVIEW:
            raise ValueError("Shadow routing must preserve an effective Review route")
        if route.patch_sha256 != case.candidate_patch_sha256:
            raise ValueError("routing result is not bound to the frozen candidate Patch")
        reviewer = (
            _reviewer_observation(evidence_root, case.reviewer_evidence, route=route)
            if case.reviewer_evidence is not None
            else None
        )
        observations.append((route, reviewer))
    return dataset, observations


def build_shadow_scorecard(
    dataset: ShadowEvaluationDataset,
    observations: list[tuple[ReviewRoutingResult, ReviewerObservation | None]],
) -> ShadowScorecard:
    """Derive routing errors and observed Reviewer value without manual arithmetic."""

    if len(dataset.cases) != len(observations):
        raise ValueError("each evaluation case requires exactly one routing observation")
    clean = sum(case.evaluator_label is EvaluatorLabel.CLEAN for case in dataset.cases)
    defective = len(dataset.cases) - clean
    reviewed = sum(reviewer is not None for _, reviewer in observations)
    recommended_reviews = sum(
        route.recommended_route is ReviewRoute.REVIEW for route, _ in observations
    )
    false_routes = sum(
        case.evaluator_label is EvaluatorLabel.CLEAN
        and route.recommended_route is ReviewRoute.REVIEW
        for case, (route, _) in zip(dataset.cases, observations, strict=True)
    )
    false_skips = sum(
        case.evaluator_label is EvaluatorLabel.DEFECTIVE
        and route.recommended_route is ReviewRoute.SKIP
        for case, (route, _) in zip(dataset.cases, observations, strict=True)
    )
    clean_reviewed = sum(
        case.evaluator_label is EvaluatorLabel.CLEAN and reviewer is not None
        for case, (_, reviewer) in zip(dataset.cases, observations, strict=True)
    )
    false_blocks = sum(
        case.evaluator_label is EvaluatorLabel.CLEAN
        and reviewer is not None
        and reviewer.verdict is Verdict.REQUEST_CHANGES
        for case, (_, reviewer) in zip(dataset.cases, observations, strict=True)
    )
    defective_reviewed = sum(
        case.evaluator_label is EvaluatorLabel.DEFECTIVE and reviewer is not None
        for case, (_, reviewer) in zip(dataset.cases, observations, strict=True)
    )
    defective_caught = sum(
        case.evaluator_label is EvaluatorLabel.DEFECTIVE
        and reviewer is not None
        and reviewer.confirmed_incremental_findings > 0
        for case, (_, reviewer) in zip(dataset.cases, observations, strict=True)
    )
    confirmed = sum(
        reviewer.confirmed_incremental_findings
        for _, reviewer in observations
        if reviewer is not None
    )
    duration = sum(
        reviewer.duration_seconds for _, reviewer in observations if reviewer is not None
    )
    input_tokens = sum(
        reviewer.token_usage.input_tokens
        for _, reviewer in observations
        if reviewer is not None
    )
    output_tokens = sum(
        reviewer.token_usage.output_tokens
        for _, reviewer in observations
        if reviewer is not None
    )
    repairs = sum(
        reviewer.repair_rounds for _, reviewer in observations if reviewer is not None
    )
    real_defective = sum(
        case.source is EvidenceSource.REAL_REPOSITORY
        and case.evaluator_label is EvaluatorLabel.DEFECTIVE
        for case in dataset.cases
    )
    blockers: list[str] = []
    if reviewed != len(dataset.cases):
        blockers.append(f"paired Reviewer outcome coverage is {reviewed}/{len(dataset.cases)}")
    if real_defective == 0:
        blockers.append("no evaluator-confirmed defective real-repository case")
    if defective_reviewed == 0:
        blockers.append("no defective case has a paired Reviewer observation")
    case_scores: list[ShadowCaseScore] = []
    for case, (route, reviewer) in zip(dataset.cases, observations, strict=True):
        case_scores.append(
            ShadowCaseScore(
                case_id=case.case_id,
                source=case.source,
                repository=case.repository,
                evaluator_label=case.evaluator_label,
                resolved_base_commit=route.resolved_base_commit,
                candidate_patch_sha256=case.candidate_patch_sha256,
                recommended_route=route.recommended_route,
                routing_score=route.score,
                routing_threshold=route.threshold,
                reviewer_observed=reviewer is not None,
                reviewer_verdict=reviewer.verdict if reviewer else None,
                confirmed_incremental_findings=(
                    reviewer.confirmed_incremental_findings if reviewer else 0
                ),
                reviewer_duration_seconds=reviewer.duration_seconds if reviewer else 0,
                reviewer_input_tokens=reviewer.token_usage.input_tokens if reviewer else 0,
                reviewer_output_tokens=reviewer.token_usage.output_tokens if reviewer else 0,
                repair_rounds=reviewer.repair_rounds if reviewer else 0,
            )
        )
    return ShadowScorecard(
        source_schema_version=dataset.schema_version,
        frozen_at=dataset.frozen_at,
        policy_version=dataset.policy_version,
        case_count=len(dataset.cases),
        clean_cases=clean,
        defective_cases=defective,
        real_repository_cases=sum(
            case.source is EvidenceSource.REAL_REPOSITORY for case in dataset.cases
        ),
        reviewer_observed_cases=reviewed,
        recommended_reviews=recommended_reviews,
        recommended_skips=len(dataset.cases) - recommended_reviews,
        reviewer_coverage=_ratio(reviewed, len(dataset.cases)),
        false_routes=_ratio(false_routes, clean),
        false_skips=_ratio(false_skips, defective),
        false_blocks=_ratio(false_blocks, clean_reviewed),
        defective_cases_caught_by_reviewer=_ratio(defective_caught, defective_reviewed),
        confirmed_incremental_findings=confirmed,
        total_reviewer_duration_seconds=duration,
        total_reviewer_input_tokens=input_tokens,
        total_reviewer_output_tokens=output_tokens,
        total_repair_rounds=repairs,
        selective_activation_ready=not blockers,
        activation_blockers=blockers,
        cases=case_scores,
    )


def render_shadow_scorecard_markdown(scorecard: ShadowScorecard) -> str:
    """Render a compact report while preserving numerator/denominator semantics."""

    def ratio(value: Ratio) -> str:
        return f"{value.numerator}/{value.denominator}"

    lines = [
        "# Shadow Reviewer scorecard",
        "",
        f"Frozen: {scorecard.frozen_at.isoformat()}  ",
        f"Policy: `{scorecard.policy_version}`",
        "",
        "| Case | Source | Label | Route | Reviewer | Confirmed incremental findings |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    for case in scorecard.cases:
        reviewer = case.reviewer_verdict.value if case.reviewer_verdict else "not observed"
        lines.append(
            f"| `{case.case_id}` | {case.source.value} | {case.evaluator_label.value} | "
            f"{case.recommended_route.value} ({case.routing_score}/{case.routing_threshold}) | "
            f"{reviewer} | {case.confirmed_incremental_findings} |"
        )
    lines.extend(
        [
            "",
            "## Derived counts",
            "",
            f"- False route: {ratio(scorecard.false_routes)}",
            f"- False skip: {ratio(scorecard.false_skips)}",
            f"- False block: {ratio(scorecard.false_blocks)}",
            f"- Paired Reviewer coverage: {ratio(scorecard.reviewer_coverage)}",
            (
                "- Defective cases caught by Reviewer: "
                f"{ratio(scorecard.defective_cases_caught_by_reviewer)}"
            ),
            f"- Confirmed incremental findings: {scorecard.confirmed_incremental_findings}",
            (
                "- Observed Reviewer cost: "
                f"{scorecard.total_reviewer_duration_seconds:.3f}s, "
                f"{scorecard.total_reviewer_input_tokens} input / "
                f"{scorecard.total_reviewer_output_tokens} output tokens, "
                f"{scorecard.total_repair_rounds} repair round(s)"
            ),
            "",
            "## Selective activation decision",
            "",
        ]
    )
    if scorecard.selective_activation_ready:
        lines.append("The frozen activation requirements are satisfied.")
    else:
        lines.append("Selective Review remains opt-in; the frozen evidence is incomplete:")
        lines.append("")
        lines.extend(f"- {blocker}" for blocker in scorecard.activation_blockers)
    lines.extend(
        [
            "",
            "These are observed case counts, not population accuracy estimates. Evaluator labels "
            "were applied after Agent execution and are not part of Fix or Review task schemas.",
            "",
        ]
    )
    return "\n".join(lines)
