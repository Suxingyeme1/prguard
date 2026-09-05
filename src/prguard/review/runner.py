"""Read-only Independent Reviewer orchestration."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from uuid import uuid4

from prguard.harness import VerificationHarness
from prguard.harness.errors import HarnessError
from prguard.harness.git import GitRepository, apply_patch
from prguard.harness.readiness import readiness_commands, readiness_failure_boundary
from prguard.implementer.errors import ImplementerError, ProviderError
from prguard.implementer.tools import RepositoryTools
from prguard.review.artifacts import finalize_review_artifacts
from prguard.reviewer.compatibility import analyze_python_compatibility
from prguard.reviewer.providers import ReviewerProvider, ReviewProviderRequest
from prguard.schemas import (
    ProviderFailureEvidence,
    ReviewOutcome,
    ReviewReport,
    ReviewTask,
    RunOutcome,
    Severity,
    Task,
    TaskMode,
    TokenUsage,
    Verdict,
)

_BLOCKING_SEVERITIES = {Severity.P0, Severity.P1, Severity.P2}


class ReviewRunner:
    def __init__(self, artifact_root: Path, provider: ReviewerProvider) -> None:
        self.artifact_root = artifact_root.expanduser().resolve()
        self.provider = provider

    def run(self, task: ReviewTask) -> ReviewReport:
        run_id = str(uuid4())
        run_directory = self.artifact_root / run_id
        run_directory.mkdir(parents=True, exist_ok=False)
        review_worktree = run_directory / "_review_worktree"
        base_review_worktree = run_directory / "_review_base_worktree"
        started = time.monotonic()
        deadline = started + task.task_timeout_seconds
        patch_bytes = b""
        readiness = None
        verification = None
        envelope = None
        provider_failure = None
        compatibility_signals: list[str] = []
        resolved_commit = None
        error = None
        outcome = ReviewOutcome.PREFLIGHT_FAILED
        verdict = Verdict.FAILED
        repository = GitRepository(task.repository)
        registered = False
        base_registered = False
        try:
            patch_bytes = task.candidate_patch.expanduser().resolve().read_bytes()
            base_commands = readiness_commands(task.commands)
            if base_commands:
                readiness_task = Task(
                    case_id=f"{task.case_id}-readiness",
                    mode=TaskMode.REVIEW,
                    repository=task.repository,
                    base_commit=task.base_commit,
                    issue=task.issue,
                    commands=base_commands,
                    allowed_commands=[command.argv for command in base_commands],
                    protected_paths=task.protected_paths,
                    command_timeout_seconds=task.command_timeout_seconds,
                    task_timeout_seconds=max(0.1, deadline - time.monotonic()),
                    max_output_bytes=task.max_output_bytes,
                    container=task.container,
                    runtime_files=task.runtime_files,
                )
                readiness = VerificationHarness(run_directory / "readiness").run(readiness_task)
                resolved_commit = readiness.resolved_base_commit
                if readiness.outcome is not RunOutcome.PASSED:
                    boundary = readiness_failure_boundary(readiness)
                    error = (
                        f"{boundary} is not ready; inspect readiness artifacts "
                        f"({readiness.outcome.value})"
                    )
            if readiness is None or readiness.outcome is RunOutcome.PASSED:
                verification_task = Task(
                    case_id=f"{task.case_id}-verification",
                    mode=TaskMode.REVIEW,
                    repository=task.repository,
                    base_commit=task.base_commit,
                    issue=task.issue,
                    candidate_patch=task.candidate_patch,
                    commands=task.commands,
                    allowed_commands=task.allowed_commands,
                    protected_paths=task.protected_paths,
                    command_timeout_seconds=task.command_timeout_seconds,
                    task_timeout_seconds=max(0.1, deadline - time.monotonic()),
                    max_output_bytes=task.max_output_bytes,
                    require_changed_tests_fail_on_base=True,
                    container=task.container,
                    runtime_files=task.runtime_files,
                )
                verification = VerificationHarness(run_directory / "verification").run(
                    verification_task
                )
                resolved_commit = verification.resolved_base_commit
            if verification is None:
                outcome = ReviewOutcome.PREFLIGHT_FAILED
            elif verification.outcome == RunOutcome.PATCH_FAILED:
                outcome = ReviewOutcome.PATCH_FAILED
            elif verification.outcome == RunOutcome.POLICY_BLOCKED:
                outcome = ReviewOutcome.POLICY_BLOCKED
            elif verification.outcome in {RunOutcome.PREFLIGHT_FAILED, RunOutcome.TIMED_OUT}:
                outcome = ReviewOutcome.PREFLIGHT_FAILED
            else:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ImplementerError("task deadline expired before Reviewer call")
                resolved_commit = repository.preflight(task.base_commit, deadline=deadline)
                repository.add_worktree(base_review_worktree, resolved_commit, deadline=deadline)
                base_registered = True
                repository.add_worktree(review_worktree, resolved_commit, deadline=deadline)
                registered = True
                applied, patch_error = apply_patch(
                    review_worktree, task.candidate_patch.expanduser().resolve(), deadline=deadline
                )
                if not applied:
                    raise ImplementerError(f"unable to prepare review worktree: {patch_error}")
                compatibility_signals = analyze_python_compatibility(
                    base_review_worktree,
                    review_worktree,
                    verification.changed_files,
                    max_file_bytes=task.max_file_bytes,
                )
                envelope = self.provider.review(
                    ReviewProviderRequest(
                        task=task,
                        candidate_patch=patch_bytes.decode("utf-8", errors="replace"),
                        verification=verification,
                        compatibility_signals=tuple(compatibility_signals),
                        deadline_monotonic=deadline,
                    ),
                    RepositoryTools(review_worktree, task),
                )
                if time.monotonic() >= deadline:
                    raise ImplementerError("task deadline expired during Reviewer call")
                blocking = any(
                    finding.severity in _BLOCKING_SEVERITIES
                    for finding in envelope.submission.findings
                )
                verdict = (
                    Verdict.ACCEPT
                    if verification.outcome == RunOutcome.PASSED and not blocking
                    else Verdict.REQUEST_CHANGES
                )
                outcome = ReviewOutcome.REVIEWED
        except (OSError, ValueError, ImplementerError, HarnessError) as exc:
            error = str(exc)
            if isinstance(exc, ProviderError) and isinstance(exc.evidence, ProviderFailureEvidence):
                provider_failure = exc.evidence
            if verification and verification.outcome not in {
                RunOutcome.PATCH_FAILED,
                RunOutcome.POLICY_BLOCKED,
                RunOutcome.PREFLIGHT_FAILED,
            }:
                outcome = ReviewOutcome.REVIEWER_FAILED
            verdict = Verdict.FAILED
        finally:
            if registered:
                try:
                    repository.remove_worktree(review_worktree)
                except Exception as exc:
                    error = f"cleanup failed: {exc}"
                    outcome = ReviewOutcome.POLICY_BLOCKED
                    verdict = Verdict.FAILED
            if base_registered:
                try:
                    repository.remove_worktree(base_review_worktree)
                except Exception as exc:
                    error = f"cleanup failed: {exc}"
                    outcome = ReviewOutcome.POLICY_BLOCKED
                    verdict = Verdict.FAILED
            shutil.rmtree(review_worktree, ignore_errors=True)
            shutil.rmtree(base_review_worktree, ignore_errors=True)
        report = ReviewReport(
            run_id=run_id,
            case_id=task.case_id,
            resolved_base_commit=resolved_commit,
            outcome=outcome,
            verdict=verdict,
            readiness=readiness,
            verification=verification,
            review=envelope,
            provider_failure=provider_failure,
            compatibility_signals=compatibility_signals,
            error=error,
            token_usage=(
                envelope.token_usage
                if envelope
                else provider_failure.token_usage
                if provider_failure
                else TokenUsage()
            ),
            duration_seconds=time.monotonic() - started,
            artifact_directory=run_directory,
        )
        finalize_review_artifacts(run_directory, task, report, patch_bytes)
        return report
