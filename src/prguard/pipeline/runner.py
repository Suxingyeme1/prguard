"""Top-level Issue-to-PR composition."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from prguard.fix import FixRunner
from prguard.harness.artifacts import (
    canonical_json,
    sha256_bytes,
    sha256_file,
    verify_manifest,
)
from prguard.harness.errors import ArtifactIntegrityError, HarnessError
from prguard.implementer.errors import ImplementerError
from prguard.implementer.providers import ImplementerProvider
from prguard.pipeline.artifacts import finalize_issue_to_pr_artifacts
from prguard.pipeline.routing import route_accepted_fix
from prguard.review import ReviewRepairRunner
from prguard.reviewer.providers import ReviewerProvider
from prguard.schemas import (
    FixOutcome,
    FixTask,
    IssueToPROutcome,
    IssueToPRReport,
    IssueToPRTask,
    ReviewRepairOutcome,
    ReviewRepairReport,
    ReviewRepairTask,
    ReviewRoute,
    TokenUsage,
    Verdict,
)

ReviewerSource = ReviewerProvider | Callable[[], ReviewerProvider]
ImplementerSource = ImplementerProvider | Callable[[], ImplementerProvider]
PipelineProgressCallback = Callable[[str, dict[str, object]], None]


# Progress is an observability boundary, not a second artifact channel. Keep the
# relay deliberately small so callers never receive Issue text, file paths,
# command arguments/output, Patch content, or exception messages.
_FIX_PROGRESS_FIELDS: dict[str, frozenset[str]] = {
    "run.started": frozenset({"run_id"}),
    "preflight.started": frozenset(),
    "preflight.completed": frozenset({"resolved_base_commit"}),
    "readiness.started": frozenset({"command_count"}),
    "readiness.completed": frozenset({"outcome"}),
    "attempt.started": frozenset({"attempt", "repair"}),
    "proposal.completed": frozenset({"provider", "model", "tool_calls", "patch_bytes"}),
    "verification.started": frozenset({"attempt"}),
    "verification.completed": frozenset(
        {"attempt", "outcome", "command_count", "changed_files"}
    ),
    "repair.requested": frozenset({"attempt", "failure"}),
    "attempt.failed": frozenset({"attempt", "error_type"}),
    "run.completed": frozenset({"outcome", "attempts", "duration_seconds"}),
}
_REVIEW_REPAIR_PROGRESS_FIELDS: dict[str, frozenset[str]] = {
    "review_repair.started": frozenset({"run_id"}),
    "review.started": frozenset({"run_id"}),
    "review.readiness.started": frozenset({"command_count"}),
    "review.readiness.completed": frozenset({"outcome"}),
    "review.verification.started": frozenset({"command_count"}),
    "review.verification.completed": frozenset(
        {"outcome", "command_count", "changed_files"}
    ),
    "review.analysis.started": frozenset({"changed_files"}),
    "review.analysis.completed": frozenset({"compatibility_signals"}),
    "review.provider.started": frozenset(),
    "review.provider.completed": frozenset({"provider", "model", "tool_calls", "findings"}),
    "review.completed": frozenset({"outcome", "verdict", "findings", "duration_seconds"}),
    "review.decision": frozenset({"outcome", "verdict", "findings"}),
    "repair.started": frozenset(),
    "repair.provider.started": frozenset(),
    "repair.provider.completed": frozenset({"provider", "model", "tool_calls", "patch_bytes"}),
    "repair.verification.started": frozenset({"command_count"}),
    "repair.verification.completed": frozenset(
        {"outcome", "command_count", "changed_files"}
    ),
    "repair.completed": frozenset({"outcome", "verdict", "duration_seconds"}),
    "review_repair.completed": frozenset({"outcome", "verdict", "duration_seconds"}),
}


def _public_progress_data(
    event: str,
    data: dict[str, object],
    allowed_fields: dict[str, frozenset[str]],
) -> dict[str, object]:
    """Copy only the explicit, non-sensitive fields for a progress observer."""

    return {
        field: data[field]
        for field in allowed_fields.get(event, frozenset())
        if field in data
    }


def _add_usage(total: TokenUsage, extra: TokenUsage) -> None:
    total.input_tokens += extra.input_tokens
    total.output_tokens += extra.output_tokens
    total.cached_tokens += extra.cached_tokens
    total.estimated_cost_usd += extra.estimated_cost_usd


def _bind_review_artifacts(report: ReviewRepairReport, routed_patch_sha256: str) -> None:
    root = Path(report.artifact_directory).resolve()
    manifest = verify_manifest(root / "review-repair-manifest.json")
    if (
        manifest.run_id != report.run_id
        or manifest.case_id != report.case_id
        or (
            report.resolved_base_commit is not None
            and manifest.resolved_base_commit != report.resolved_base_commit
        )
    ):
        raise ArtifactIntegrityError(
            "Review/repair manifest identity does not match its report"
        )
    archived = ReviewRepairReport.model_validate_json(
        (root / "review-repair-report.json").read_bytes()
    )
    if canonical_json(archived.model_dump(mode="json")) != canonical_json(
        report.model_dump(mode="json")
    ):
        raise ArtifactIntegrityError(
            "in-memory Review/repair report differs from verified artifact"
        )
    if sha256_file(root / "original-candidate.patch") != routed_patch_sha256:
        raise ArtifactIntegrityError(
            "Review/repair candidate does not match routed Patch hash"
        )


def _verified_review_delivery(report: ReviewRepairReport) -> bytes:
    if report.final_patch is None:
        raise ArtifactIntegrityError("accepted Review/repair report has no final Patch")
    root = Path(report.artifact_directory).resolve()
    final_patch = Path(report.final_patch).resolve()
    try:
        final_patch.relative_to(root)
    except ValueError as exc:
        raise ArtifactIntegrityError(
            "Review/repair final Patch escapes its artifact directory"
        ) from exc
    if report.final_verification is not None:
        expected_sha256 = report.final_verification.patch.patch_sha256
    elif report.initial_review is not None and report.initial_review.verification is not None:
        expected_sha256 = report.initial_review.verification.patch.patch_sha256
    else:
        raise ArtifactIntegrityError(
            "accepted Review/repair report has no verification binding"
        )
    payload = final_patch.read_bytes()
    if sha256_bytes(payload) != expected_sha256:
        raise ArtifactIntegrityError(
            "Review/repair final Patch does not match verified Patch hash"
        )
    return payload


def _as_fix_task(task: IssueToPRTask, timeout_seconds: float) -> FixTask:
    payload = task.model_dump(
        exclude={
            "fix_timeout_seconds",
            "review_timeout_seconds",
            "review_max_tool_calls",
            "review_routing_mode",
        }
    )
    payload["task_timeout_seconds"] = timeout_seconds
    return FixTask.model_validate(payload)


def _as_review_repair_task(
    task: IssueToPRTask,
    candidate_patch: Path,
    timeout_seconds: float,
    review_timeout_seconds: float,
) -> ReviewRepairTask:
    return ReviewRepairTask(
        case_id=f"{task.case_id}-independent-review",
        repository=task.repository,
        base_commit=task.base_commit,
        issue=task.issue,
        candidate_patch=candidate_patch,
        commands=task.commands,
        allowed_commands=task.allowed_commands,
        writable_paths=task.writable_paths,
        protected_paths=task.protected_paths,
        command_timeout_seconds=task.command_timeout_seconds,
        task_timeout_seconds=timeout_seconds,
        max_output_bytes=task.max_output_bytes,
        max_tool_calls=task.review_max_tool_calls,
        max_file_bytes=task.max_file_bytes,
        max_context_bytes=task.max_context_bytes,
        max_patch_bytes=task.max_patch_bytes,
        max_changed_files=task.max_changed_files,
        review_timeout_seconds=review_timeout_seconds,
        container=task.container,
        runtime_files=task.runtime_files,
    )


class IssueToPRRunner:
    """Compose implementation, independent review, and optional controlled repair."""

    def __init__(
        self,
        artifact_root: Path,
        implementer: ImplementerProvider,
        reviewer: ReviewerSource,
        repair_implementer: ImplementerSource,
        *,
        progress: PipelineProgressCallback | None = None,
    ) -> None:
        self.artifact_root = artifact_root.expanduser().resolve()
        self.implementer = implementer
        self.reviewer = reviewer
        self.repair_implementer = repair_implementer
        self.progress = progress

    def _emit(self, event: str, **data: object) -> None:
        """Notify an optional observer without letting presentation break the run."""

        if self.progress is None:
            return
        with suppress(Exception):
            self.progress(event, data)

    def _forward_fix_progress(self, event: str, data: dict[str, object]) -> None:
        if event not in _FIX_PROGRESS_FIELDS:
            return
        self._emit(
            f"fix.{event}",
            **_public_progress_data(event, data, _FIX_PROGRESS_FIELDS),
        )

    def _forward_review_repair_progress(
        self, event: str, data: dict[str, object]
    ) -> None:
        if event not in _REVIEW_REPAIR_PROGRESS_FIELDS:
            return
        public = _public_progress_data(event, data, _REVIEW_REPAIR_PROGRESS_FIELDS)
        if event in {
            "review.started",
            "review.completed",
            "repair.started",
            "repair.completed",
        }:
            self._emit(event, **public)
            return
        self._emit(f"review.detail.{event}", **public)

    @staticmethod
    def _resolve_reviewer(source: ReviewerSource) -> ReviewerProvider:
        return source() if callable(source) else source

    def run(self, task: IssueToPRTask) -> IssueToPRReport:
        run_id = str(uuid4())
        run_directory = self.artifact_root / run_id
        run_directory.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        deadline = started + task.task_timeout_seconds
        fix_report = None
        review_report = None
        routing = None
        final_patch = None
        resolved_commit = None
        token_usage = TokenUsage()
        outcome = IssueToPROutcome.PREFLIGHT_FAILED
        verdict = Verdict.FAILED
        error = None
        self._emit("pipeline.started", run_id=run_id)
        try:
            fix_budget = min(task.fix_timeout_seconds, deadline - time.monotonic())
            if fix_budget <= 0:
                raise ImplementerError("task deadline expired before Fix stage")
            self._emit("fix.started", budget_seconds=round(fix_budget, 3))
            fix_report = FixRunner(
                run_directory / "fix",
                self.implementer,
                progress=self._forward_fix_progress,
            ).run(
                _as_fix_task(task, fix_budget)
            )
            self._emit(
                "fix.completed",
                outcome=fix_report.outcome.value,
                attempts=len(fix_report.attempts),
            )
            resolved_commit = fix_report.resolved_base_commit
            _add_usage(token_usage, fix_report.token_usage)
            if fix_report.outcome is FixOutcome.POLICY_BLOCKED:
                outcome = IssueToPROutcome.POLICY_BLOCKED
            elif fix_report.outcome is FixOutcome.PREFLIGHT_FAILED:
                outcome = IssueToPROutcome.PREFLIGHT_FAILED
            elif fix_report.outcome is not FixOutcome.ACCEPTED or fix_report.final_patch is None:
                outcome = IssueToPROutcome.FIX_FAILED
            else:
                self._emit("routing.started")
                routing = route_accepted_fix(
                    task,
                    fix_report,
                    run_directory,
                    deadline_monotonic=deadline,
                )
                self._emit(
                    "routing.completed",
                    mode=routing.mode.value,
                    recommended_route=routing.recommended_route.value,
                    effective_route=routing.effective_route.value,
                    score=routing.score,
                    factors=len(routing.factors),
                    uncovered_reachable_tests=len(routing.uncovered_reachable_tests),
                )
                if time.monotonic() >= deadline:
                    raise ImplementerError("task deadline expired during Reviewer routing")
                if sha256_file(Path(fix_report.final_patch)) != routing.patch_sha256:
                    raise ArtifactIntegrityError(
                        "Fix final Patch changed after Reviewer routing"
                    )
                if routing.effective_route is ReviewRoute.SKIP:
                    self._emit("delivery.started", source="fix")
                    final_patch = run_directory / "final.patch"
                    patch_bytes = Path(fix_report.final_patch).read_bytes()
                    if sha256_bytes(patch_bytes) != routing.patch_sha256:
                        raise ArtifactIntegrityError(
                            "selective delivery Patch does not match routed Patch hash"
                        )
                    final_patch.write_bytes(patch_bytes)
                    outcome = IssueToPROutcome.ACCEPTED
                    verdict = Verdict.ACCEPT
                    self._emit("delivery.completed", source="fix", outcome=outcome.value)
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0.2:
                        raise ImplementerError("task deadline expired before Review stage")
                    review_budget = min(task.review_timeout_seconds, remaining - 0.1)
                    review_report = ReviewRepairRunner(
                        run_directory / "review",
                        self._resolve_reviewer(self.reviewer),
                        self.repair_implementer,
                        progress=self._forward_review_repair_progress,
                    ).run(
                        _as_review_repair_task(
                            task,
                            Path(fix_report.final_patch),
                            remaining,
                            review_budget,
                        )
                    )
                    if time.monotonic() >= deadline:
                        raise ImplementerError("task deadline expired during Review stage")
                    _bind_review_artifacts(review_report, routing.patch_sha256)
                    if time.monotonic() >= deadline:
                        raise ImplementerError(
                            "task deadline expired while binding Review artifacts"
                        )
                    _add_usage(token_usage, review_report.token_usage)
                    accepted = {
                        ReviewRepairOutcome.ACCEPTED_WITHOUT_REPAIR,
                        ReviewRepairOutcome.ACCEPTED_AFTER_REPAIR,
                    }
                    if review_report.outcome in accepted and review_report.final_patch:
                        self._emit("delivery.started", source="review_repair")
                        final_patch = run_directory / "final.patch"
                        final_patch.write_bytes(_verified_review_delivery(review_report))
                        outcome = IssueToPROutcome.ACCEPTED
                        verdict = Verdict.ACCEPT
                        self._emit(
                            "delivery.completed",
                            source="review_repair",
                            outcome=outcome.value,
                        )
                    elif review_report.outcome is ReviewRepairOutcome.POLICY_BLOCKED:
                        outcome = IssueToPROutcome.POLICY_BLOCKED
                    elif review_report.outcome is ReviewRepairOutcome.PREFLIGHT_FAILED:
                        outcome = IssueToPROutcome.PREFLIGHT_FAILED
                    else:
                        outcome = IssueToPROutcome.REVIEW_FAILED
                        verdict = review_report.verdict
        except (OSError, ValueError, ImplementerError, HarnessError) as exc:
            error = str(exc)
            if fix_report is not None:
                outcome = IssueToPROutcome.REVIEW_FAILED
            else:
                outcome = IssueToPROutcome.PREFLIGHT_FAILED
        report = IssueToPRReport(
            run_id=run_id,
            case_id=task.case_id,
            resolved_base_commit=resolved_commit,
            outcome=outcome,
            verdict=verdict,
            fix=fix_report,
            review_routing=routing,
            review_repair=review_report,
            final_patch=final_patch,
            error=error,
            token_usage=token_usage,
            duration_seconds=time.monotonic() - started,
            artifact_directory=run_directory,
        )
        try:
            finalize_issue_to_pr_artifacts(run_directory, task, report)
        except ArtifactIntegrityError as exc:
            if final_patch is not None:
                try:
                    Path(final_patch).resolve().relative_to(run_directory.resolve())
                except ValueError:
                    pass
                else:
                    Path(final_patch).unlink(missing_ok=True)
            report = report.model_copy(
                update={
                    "outcome": IssueToPROutcome.REVIEW_FAILED,
                    "verdict": Verdict.FAILED,
                    "final_patch": None,
                    "error": str(exc),
                }
            )
            finalize_issue_to_pr_artifacts(run_directory, task, report)
        self._emit(
            "pipeline.completed",
            outcome=report.outcome.value,
            verdict=report.verdict.value,
            duration_seconds=round(report.duration_seconds, 3),
        )
        return report
