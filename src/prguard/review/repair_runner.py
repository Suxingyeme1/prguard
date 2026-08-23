"""Independent review followed by at most one controlled replacement-patch attempt."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from uuid import uuid4

from prguard.harness import VerificationHarness
from prguard.harness.errors import HarnessError
from prguard.harness.git import GitRepository, apply_patch, final_diff
from prguard.implementer.edits import apply_structured_edits
from prguard.implementer.errors import ImplementerError, PatchPolicyError
from prguard.implementer.providers import ImplementerProvider, ProviderRequest
from prguard.implementer.tools import RepositoryTools, validate_proposed_patch
from prguard.review.repair_artifacts import finalize_review_repair_artifacts
from prguard.review.runner import ReviewRunner
from prguard.reviewer.providers import ReviewerProvider
from prguard.schemas import (
    FixTask,
    ReviewOutcome,
    ReviewRepairOutcome,
    ReviewRepairReport,
    ReviewRepairTask,
    ReviewReport,
    ReviewTask,
    RunOutcome,
    Task,
    TaskMode,
    TokenUsage,
    Verdict,
)


def _add_usage(total: TokenUsage, extra: TokenUsage) -> None:
    total.input_tokens += extra.input_tokens
    total.output_tokens += extra.output_tokens
    total.cached_tokens += extra.cached_tokens
    total.estimated_cost_usd += extra.estimated_cost_usd


def _repair_feedback(task: ReviewRepairTask, report_patch: str, report: ReviewReport) -> str:
    """Serialize only public, structured evidence into the Implementer context."""
    initial = report
    review = initial.review
    verification = initial.verification
    payload = {
        "instruction": (
            "Correct all evidence-backed defects while preserving the intended candidate "
            "behavior. Prefer structured edits against the patched files you inspect; PRGuard "
            "will combine them into one replacement Patch against the same Base Commit. A raw "
            "Patch fallback must itself be a complete replacement against that Base Commit."
        ),
        "original_candidate_patch": report_patch,
        "review_summary": review.submission.summary if review else None,
        "review_findings": [
            finding.model_dump(mode="json")
            for finding in (review.submission.findings if review else [])
        ],
        "verification": {
            "outcome": verification.outcome.value if verification else "not_run",
            "changed_files": verification.changed_files if verification else [],
            "policy_violations": [
                item.model_dump(mode="json")
                for item in (verification.policy_violations if verification else [])
            ],
            "failed_commands": [
                {
                    "kind": command.kind,
                    "argv": command.argv,
                    "exit_code": command.exit_code,
                    "timed_out": command.timed_out,
                    "stdout": command.stdout,
                    "stderr": command.stderr,
                }
                for command in (verification.commands if verification else [])
                if not command.passed
            ],
        },
        "base_commit": task.base_commit,
        "issue": task.issue,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _as_review_task(task: ReviewRepairTask, timeout_seconds: float) -> ReviewTask:
    payload = task.model_dump(
        exclude={
            "writable_paths",
            "max_patch_bytes",
            "max_changed_files",
            "review_timeout_seconds",
        }
    )
    payload["task_timeout_seconds"] = timeout_seconds
    return ReviewTask.model_validate(payload)


def _as_fix_task(task: ReviewRepairTask, resolved_commit: str) -> FixTask:
    return FixTask(
        case_id=f"{task.case_id}-controlled-repair",
        repository=task.repository,
        base_commit=resolved_commit,
        issue=task.issue,
        commands=task.commands,
        allowed_commands=task.allowed_commands,
        writable_paths=task.writable_paths,
        protected_paths=task.protected_paths,
        command_timeout_seconds=task.command_timeout_seconds,
        task_timeout_seconds=task.task_timeout_seconds,
        max_output_bytes=task.max_output_bytes,
        max_tool_calls=task.max_tool_calls,
        max_file_bytes=task.max_file_bytes,
        max_context_bytes=task.max_context_bytes,
        max_patch_bytes=task.max_patch_bytes,
        max_changed_files=task.max_changed_files,
        max_repair_attempts=0,
        container=task.container,
        runtime_files=task.runtime_files,
    )


class ReviewRepairRunner:
    """Run a read-only review and, when blocked, one Implementer repair proposal."""

    def __init__(
        self,
        artifact_root: Path,
        reviewer: ReviewerProvider,
        implementer: ImplementerProvider,
    ) -> None:
        self.artifact_root = artifact_root.expanduser().resolve()
        self.reviewer = reviewer
        self.implementer = implementer

    def run(self, task: ReviewRepairTask) -> ReviewRepairReport:
        run_id = str(uuid4())
        run_directory = self.artifact_root / run_id
        run_directory.mkdir(parents=True, exist_ok=False)
        repair_worktree = run_directory / "_repair_worktree"
        started = time.monotonic()
        deadline = started + task.task_timeout_seconds
        repository = GitRepository(task.repository)
        candidate_bytes = b""
        initial_review = None
        repair_proposal = None
        final_verification = None
        final_patch = None
        resolved_commit = None
        token_usage = TokenUsage()
        outcome = ReviewRepairOutcome.PREFLIGHT_FAILED
        verdict = Verdict.FAILED
        error = None
        registered = False
        try:
            candidate_path = task.candidate_patch.expanduser().resolve()
            candidate_bytes = candidate_path.read_bytes()
            candidate_text = candidate_bytes.decode("utf-8", errors="replace")
            review_budget = min(
                task.review_timeout_seconds,
                max(0.1, deadline - time.monotonic()),
            )
            initial_review = ReviewRunner(run_directory / "initial-review", self.reviewer).run(
                _as_review_task(task, review_budget)
            )
            resolved_commit = initial_review.resolved_base_commit
            _add_usage(token_usage, initial_review.token_usage)
            if initial_review.outcome is ReviewOutcome.POLICY_BLOCKED:
                outcome = ReviewRepairOutcome.POLICY_BLOCKED
            elif initial_review.outcome in {
                ReviewOutcome.PATCH_FAILED,
                ReviewOutcome.PREFLIGHT_FAILED,
            }:
                outcome = ReviewRepairOutcome.PREFLIGHT_FAILED
            elif initial_review.outcome is not ReviewOutcome.REVIEWED:
                outcome = ReviewRepairOutcome.REVIEW_FAILED
            elif initial_review.verdict is Verdict.ACCEPT:
                final_patch = run_directory / "final.patch"
                final_patch.write_bytes(candidate_bytes)
                outcome = ReviewRepairOutcome.ACCEPTED_WITHOUT_REPAIR
                verdict = Verdict.ACCEPT
            elif initial_review.verdict is Verdict.REQUEST_CHANGES:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ImplementerError("task deadline expired before controlled repair")
                resolved_commit = repository.preflight(task.base_commit, deadline=deadline)
                repository.add_worktree(repair_worktree, resolved_commit, deadline=deadline)
                registered = True
                applied, patch_error = apply_patch(
                    repair_worktree, candidate_path, deadline=deadline
                )
                if not applied:
                    raise ImplementerError(
                        f"unable to prepare controlled-repair worktree: {patch_error}"
                    )
                fix_task = _as_fix_task(task, resolved_commit)
                repair_proposal = self.implementer.propose(
                    ProviderRequest(
                        task=fix_task,
                        attempt=0,
                        feedback=_repair_feedback(task, candidate_text, initial_review),
                        deadline_monotonic=deadline,
                    ),
                    RepositoryTools(repair_worktree, task),
                )
                _add_usage(token_usage, repair_proposal.token_usage)
                if repair_proposal.proposal.patch is None:
                    apply_structured_edits(
                        repair_worktree, fix_task, repair_proposal.proposal.edits
                    )
                    generated_patch = final_diff(
                        repair_worktree, resolved_commit, deadline=deadline
                    )
                    if not generated_patch.strip():
                        raise PatchPolicyError("structured repair generated an empty Patch")
                else:
                    generated_patch = repair_proposal.proposal.patch
                repair_path = run_directory / "repair.patch"
                repair_path.write_text(generated_patch, encoding="utf-8")
                (run_directory / "repair-proposal.json").write_bytes(
                    json.dumps(
                        repair_proposal.model_dump(mode="json"),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    + b"\n"
                )
                if time.monotonic() >= deadline:
                    raise ImplementerError("task deadline expired during controlled repair")
                validate_proposed_patch(fix_task, generated_patch)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ImplementerError("task deadline expired before final verification")
                verification_task = Task(
                    case_id=f"{task.case_id}-final-verification",
                    mode=TaskMode.REVIEW_REPAIR,
                    repository=task.repository,
                    base_commit=resolved_commit,
                    issue=task.issue,
                    candidate_patch=repair_path,
                    commands=task.commands,
                    allowed_commands=task.allowed_commands,
                    protected_paths=task.protected_paths,
                    command_timeout_seconds=task.command_timeout_seconds,
                    task_timeout_seconds=remaining,
                    max_output_bytes=task.max_output_bytes,
                    container=task.container,
                    runtime_files=task.runtime_files,
                )
                final_verification = VerificationHarness(run_directory / "final-verification").run(
                    verification_task
                )
                if final_verification.outcome is RunOutcome.PASSED:
                    final_patch = run_directory / "final.patch"
                    final_patch.write_text(generated_patch, encoding="utf-8")
                    outcome = ReviewRepairOutcome.ACCEPTED_AFTER_REPAIR
                    verdict = Verdict.ACCEPT
                elif final_verification.outcome is RunOutcome.POLICY_BLOCKED:
                    outcome = ReviewRepairOutcome.POLICY_BLOCKED
                else:
                    outcome = ReviewRepairOutcome.REPAIR_FAILED
                    verdict = Verdict.REQUEST_CHANGES
            else:
                outcome = ReviewRepairOutcome.REVIEW_FAILED
        except (OSError, ValueError, ImplementerError, HarnessError) as exc:
            error = str(exc)
            if isinstance(exc, PatchPolicyError):
                outcome = ReviewRepairOutcome.POLICY_BLOCKED
            elif initial_review is not None:
                outcome = ReviewRepairOutcome.REPAIR_FAILED
                verdict = Verdict.REQUEST_CHANGES
            else:
                outcome = ReviewRepairOutcome.PREFLIGHT_FAILED
        finally:
            if registered:
                try:
                    repository.remove_worktree(repair_worktree)
                except Exception as exc:
                    error = f"cleanup failed: {exc}"
                    outcome = ReviewRepairOutcome.POLICY_BLOCKED
                    verdict = Verdict.FAILED
            shutil.rmtree(repair_worktree, ignore_errors=True)
        report = ReviewRepairReport(
            run_id=run_id,
            case_id=task.case_id,
            resolved_base_commit=resolved_commit,
            outcome=outcome,
            verdict=verdict,
            initial_review=initial_review,
            repair_proposal=repair_proposal,
            final_verification=final_verification,
            final_patch=final_patch,
            error=error,
            token_usage=token_usage,
            duration_seconds=time.monotonic() - started,
            artifact_directory=run_directory,
        )
        finalize_review_repair_artifacts(run_directory, task, report, candidate_bytes)
        return report
