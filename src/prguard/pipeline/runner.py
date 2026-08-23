"""Top-level Issue-to-PR composition."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from uuid import uuid4

from prguard.fix import FixRunner
from prguard.implementer.errors import ImplementerError
from prguard.implementer.providers import ImplementerProvider
from prguard.pipeline.artifacts import finalize_issue_to_pr_artifacts
from prguard.review import ReviewRepairRunner
from prguard.reviewer.providers import ReviewerProvider
from prguard.schemas import (
    FixOutcome,
    FixTask,
    IssueToPROutcome,
    IssueToPRReport,
    IssueToPRTask,
    ReviewRepairOutcome,
    ReviewRepairTask,
    TokenUsage,
    Verdict,
)


def _add_usage(total: TokenUsage, extra: TokenUsage) -> None:
    total.input_tokens += extra.input_tokens
    total.output_tokens += extra.output_tokens
    total.cached_tokens += extra.cached_tokens
    total.estimated_cost_usd += extra.estimated_cost_usd


def _as_fix_task(task: IssueToPRTask, timeout_seconds: float) -> FixTask:
    payload = task.model_dump(exclude={"fix_timeout_seconds", "review_timeout_seconds"})
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
        max_tool_calls=task.max_tool_calls,
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
        reviewer: ReviewerProvider,
        repair_implementer: ImplementerProvider,
    ) -> None:
        self.artifact_root = artifact_root.expanduser().resolve()
        self.implementer = implementer
        self.reviewer = reviewer
        self.repair_implementer = repair_implementer

    def run(self, task: IssueToPRTask) -> IssueToPRReport:
        run_id = str(uuid4())
        run_directory = self.artifact_root / run_id
        run_directory.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        deadline = started + task.task_timeout_seconds
        fix_report = None
        review_report = None
        final_patch = None
        resolved_commit = None
        token_usage = TokenUsage()
        outcome = IssueToPROutcome.PREFLIGHT_FAILED
        verdict = Verdict.FAILED
        error = None
        try:
            fix_budget = min(task.fix_timeout_seconds, deadline - time.monotonic())
            if fix_budget <= 0:
                raise ImplementerError("task deadline expired before Fix stage")
            fix_report = FixRunner(run_directory / "fix", self.implementer).run(
                _as_fix_task(task, fix_budget)
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
                remaining = deadline - time.monotonic()
                if remaining <= 0.2:
                    raise ImplementerError("task deadline expired before Review stage")
                review_budget = min(task.review_timeout_seconds, remaining - 0.1)
                review_report = ReviewRepairRunner(
                    run_directory / "review", self.reviewer, self.repair_implementer
                ).run(
                    _as_review_repair_task(
                        task,
                        Path(fix_report.final_patch),
                        remaining,
                        review_budget,
                    )
                )
                _add_usage(token_usage, review_report.token_usage)
                accepted = {
                    ReviewRepairOutcome.ACCEPTED_WITHOUT_REPAIR,
                    ReviewRepairOutcome.ACCEPTED_AFTER_REPAIR,
                }
                if review_report.outcome in accepted and review_report.final_patch:
                    final_patch = run_directory / "final.patch"
                    shutil.copyfile(review_report.final_patch, final_patch)
                    outcome = IssueToPROutcome.ACCEPTED
                    verdict = Verdict.ACCEPT
                elif review_report.outcome is ReviewRepairOutcome.POLICY_BLOCKED:
                    outcome = IssueToPROutcome.POLICY_BLOCKED
                elif review_report.outcome is ReviewRepairOutcome.PREFLIGHT_FAILED:
                    outcome = IssueToPROutcome.PREFLIGHT_FAILED
                else:
                    outcome = IssueToPROutcome.REVIEW_FAILED
                    verdict = review_report.verdict
        except (OSError, ValueError, ImplementerError) as exc:
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
            review_repair=review_report,
            final_patch=final_patch,
            error=error,
            token_usage=token_usage,
            duration_seconds=time.monotonic() - started,
            artifact_directory=run_directory,
        )
        finalize_issue_to_pr_artifacts(run_directory, task, report)
        return report
