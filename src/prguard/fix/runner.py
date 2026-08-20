"""Single-Implementer Issue-to-Patch workflow."""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from prguard.fix.artifacts import finalize_fix_artifacts
from prguard.harness import VerificationHarness
from prguard.harness.errors import HarnessError
from prguard.harness.git import GitRepository
from prguard.implementer.errors import ImplementerError, PatchPolicyError
from prguard.implementer.providers import ImplementerProvider, ProviderRequest
from prguard.implementer.tools import RepositoryTools, validate_proposed_patch
from prguard.schemas import (
    FixAttempt,
    FixOutcome,
    FixReport,
    FixTask,
    RunOutcome,
    Task,
    TaskMode,
    TokenUsage,
)

FixProgressCallback = Callable[[str, dict[str, object]], None]


def _verification_feedback(attempt: FixAttempt) -> str:
    assert attempt.proposal is not None
    assert attempt.verification is not None
    report = attempt.verification
    payload = {
        "previous_patch": attempt.proposal.proposal.patch,
        "outcome": report.outcome.value,
        "changed_files": report.changed_files,
        "policy_violations": [item.model_dump(mode="json") for item in report.policy_violations],
        "commands": [
            {
                "kind": result.kind,
                "argv": result.argv,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            for result in report.commands
            if not result.passed
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


class FixRunner:
    def __init__(
        self,
        artifact_root: Path,
        provider: ImplementerProvider,
        *,
        progress: FixProgressCallback | None = None,
    ) -> None:
        self.artifact_root = artifact_root.expanduser().resolve()
        self.provider = provider
        self.progress = progress

    def _emit(self, event: str, **data: object) -> None:
        """Notify an optional observer without letting presentation break the run."""

        if self.progress is None:
            return
        with suppress(Exception):
            self.progress(event, data)

    def run(self, task: FixTask) -> FixReport:
        run_id = str(uuid4())
        run_directory = self.artifact_root / run_id
        run_directory.mkdir(parents=True, exist_ok=False)
        agent_worktree = run_directory / "_agent_worktree"
        started = time.monotonic()
        repository = GitRepository(task.repository)
        attempts: list[FixAttempt] = []
        resolved_commit: str | None = None
        final_patch: Path | None = None
        outcome = FixOutcome.PREFLIGHT_FAILED
        token_usage = TokenUsage()
        registered = False
        self._emit("run.started", case_id=task.case_id, run_id=run_id)
        try:
            deadline = started + task.task_timeout_seconds
            self._emit("preflight.started", base_commit=task.base_commit)
            resolved_commit = repository.preflight(task.base_commit, deadline=deadline)
            repository.add_worktree(agent_worktree, resolved_commit, deadline=deadline)
            registered = True
            self._emit("preflight.completed", resolved_base_commit=resolved_commit)
            feedback: str | None = None
            for attempt_index in range(task.max_repair_attempts + 1):
                attempt = FixAttempt(attempt=attempt_index)
                attempts.append(attempt)
                self._emit(
                    "attempt.started",
                    attempt=attempt_index,
                    repair=attempt_index > 0,
                )
                try:
                    tools = RepositoryTools(agent_worktree, task)
                    envelope = self.provider.propose(
                        ProviderRequest(
                            task=task,
                            attempt=attempt_index,
                            feedback=feedback,
                            deadline_monotonic=deadline,
                        ),
                        tools,
                    )
                    self._emit(
                        "proposal.completed",
                        attempt=attempt_index,
                        provider=envelope.provider,
                        model=envelope.model,
                        tool_calls=len(envelope.tool_calls),
                        patch_bytes=len(envelope.proposal.patch.encode()),
                    )
                    attempt.proposal = envelope
                    token_usage.input_tokens += envelope.token_usage.input_tokens
                    token_usage.output_tokens += envelope.token_usage.output_tokens
                    token_usage.cached_tokens += envelope.token_usage.cached_tokens
                    token_usage.estimated_cost_usd += envelope.token_usage.estimated_cost_usd
                    patch_path = run_directory / f"attempt-{attempt_index}.patch"
                    patch_path.write_text(envelope.proposal.patch, encoding="utf-8")
                    (run_directory / f"attempt-{attempt_index}-proposal.json").write_bytes(
                        json.dumps(
                            envelope.model_dump(mode="json"),
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                        + b"\n"
                    )
                    if time.monotonic() >= deadline:
                        raise ImplementerError("task deadline expired during Implementer call")
                    validate_proposed_patch(task, envelope.proposal.patch)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ImplementerError("task deadline expired before verification")
                    verification_task = Task(
                        case_id=f"{task.case_id}-attempt-{attempt_index}",
                        mode=TaskMode.ISSUE_TO_PR,
                        repository=task.repository,
                        base_commit=resolved_commit,
                        issue=task.issue,
                        candidate_patch=patch_path,
                        commands=task.commands,
                        allowed_commands=task.allowed_commands,
                        protected_paths=task.protected_paths,
                        command_timeout_seconds=task.command_timeout_seconds,
                        task_timeout_seconds=remaining,
                        max_output_bytes=task.max_output_bytes,
                        container=task.container,
                    )
                    self._emit("verification.started", attempt=attempt_index)
                    verification = VerificationHarness(run_directory / "verification").run(
                        verification_task
                    )
                    attempt.verification = verification
                    self._emit(
                        "verification.completed",
                        attempt=attempt_index,
                        outcome=verification.outcome.value,
                        command_count=len(verification.commands),
                        changed_files=len(verification.changed_files),
                    )
                    if verification.outcome == RunOutcome.PASSED:
                        final_patch = run_directory / "final.patch"
                        final_patch.write_text(envelope.proposal.patch, encoding="utf-8")
                        outcome = FixOutcome.ACCEPTED
                        break
                    if verification.outcome == RunOutcome.POLICY_BLOCKED:
                        outcome = FixOutcome.POLICY_BLOCKED
                        break
                    if verification.outcome is RunOutcome.PREFLIGHT_FAILED:
                        outcome = FixOutcome.PREFLIGHT_FAILED
                        break
                    if verification.outcome is RunOutcome.TIMED_OUT:
                        outcome = FixOutcome.FAILED_VERIFICATION
                        break
                    outcome = FixOutcome.FAILED_VERIFICATION
                    feedback = _verification_feedback(attempt)
                    if attempt_index < task.max_repair_attempts:
                        self._emit(
                            "repair.requested",
                            attempt=attempt_index + 1,
                            failure=verification.outcome.value,
                        )
                except ImplementerError as exc:
                    attempt.error = str(exc)
                    self._emit(
                        "attempt.failed",
                        attempt=attempt_index,
                        error_type=type(exc).__name__,
                    )
                    outcome = (
                        FixOutcome.POLICY_BLOCKED
                        if isinstance(exc, PatchPolicyError)
                        else FixOutcome.AGENT_FAILED
                    )
                    break
        except (OSError, ValueError, ImplementerError, HarnessError) as exc:
            if not attempts:
                attempts.append(FixAttempt(attempt=0, error=str(exc)))
            outcome = FixOutcome.PREFLIGHT_FAILED
        finally:
            if registered:
                try:
                    repository.remove_worktree(agent_worktree)
                except Exception as exc:  # cleanup failure must remain visible and fail closed
                    if attempts:
                        attempts[-1].error = f"cleanup failed: {exc}"
                    else:
                        attempts.append(FixAttempt(attempt=0, error=f"cleanup failed: {exc}"))
                    outcome = FixOutcome.POLICY_BLOCKED
            shutil.rmtree(agent_worktree, ignore_errors=True)
        report = FixReport(
            run_id=run_id,
            case_id=task.case_id,
            resolved_base_commit=resolved_commit,
            outcome=outcome,
            attempts=attempts,
            final_patch=final_patch,
            token_usage=token_usage,
            duration_seconds=time.monotonic() - started,
            artifact_directory=run_directory,
        )
        finalize_fix_artifacts(run_directory, task, report)
        self._emit(
            "run.completed",
            outcome=report.outcome.value,
            attempts=len(report.attempts),
            duration_seconds=round(report.duration_seconds, 3),
        )
        return report
