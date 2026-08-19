"""Top-level deterministic verification harness."""

from __future__ import annotations

import hashlib
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from prguard.harness.artifacts import ArtifactStore
from prguard.harness.commands import CommandExecutor
from prguard.harness.errors import CommandPolicyError, HarnessError
from prguard.harness.git import (
    GitRepository,
    apply_patch,
    changed_files,
    final_diff,
)
from prguard.harness.policy import (
    CommandPolicy,
    protected_path_violations,
    remove_owned_audit_paths,
    snapshot_changes,
    snapshot_tree,
)
from prguard.schemas import (
    HarnessReport,
    PatchApplicationResult,
    PolicyViolation,
    RunOutcome,
    Task,
    TraceEvent,
)


class VerificationHarness:
    def __init__(self, artifact_root: Path) -> None:
        self.store = ArtifactStore(artifact_root)

    def run(self, task: Task) -> HarnessReport:
        run_id = str(uuid4())
        run_directory = self.store.create_run_directory(run_id)
        worktree = run_directory / "worktree"
        runtime = run_directory / "runtime"
        (runtime / "home").mkdir(parents=True)
        (runtime / "tmp").mkdir(parents=True)
        started_at = datetime.now(UTC)
        started = time.monotonic()
        deadline = started + task.task_timeout_seconds
        traces: list[TraceEvent] = []
        results = []
        violations: list[PolicyViolation] = []
        patch_result = PatchApplicationResult(attempted=False, applied=False)
        resolved_commit: str | None = None
        final_patch = ""
        changed: list[str] = []
        outcome = RunOutcome.PREFLIGHT_FAILED
        patch_bytes: bytes | None = None
        repository = GitRepository(task.repository)
        source_before: dict = {}
        audit_before: dict = {}
        worktree_registered = False

        def trace(kind: str, message: str, **data: object) -> None:
            traces.append(
                TraceEvent(sequence=len(traces), kind=kind, message=message, data=dict(data))
            )

        try:
            trace("preflight.started", "validating repository, commit, and command policy")
            policy = CommandPolicy(task.allowed_commands)
            for command in task.commands:
                policy.authorize(command.argv)
            resolved_commit = repository.preflight(task.base_commit, deadline=deadline)
            source_before = snapshot_tree(repository.path, excluded_names={".git"})
            trace("preflight.completed", "preflight succeeded", commit=resolved_commit)
            repository.add_worktree(worktree, resolved_commit, deadline=deadline)
            worktree_registered = True
            trace("worktree.created", "detached worktree created")

            if task.candidate_patch is not None:
                patch_path = task.candidate_patch.expanduser().resolve()
                patch_bytes = patch_path.read_bytes()
                patch_hash = hashlib.sha256(patch_bytes).hexdigest()
                applied, stderr = apply_patch(worktree, patch_path, deadline=deadline)
                patch_result = PatchApplicationResult(
                    attempted=True,
                    applied=applied,
                    patch_sha256=patch_hash,
                    stderr=stderr,
                )
                trace("patch.applied" if applied else "patch.failed", "candidate patch processed")
                outcome = RunOutcome.FAILED_VERIFICATION if applied else RunOutcome.PATCH_FAILED
            else:
                patch_result = PatchApplicationResult(attempted=False, applied=True)
                outcome = RunOutcome.FAILED_VERIFICATION
                trace("patch.skipped", "task has no candidate patch")

            if patch_result.applied:
                changed = changed_files(worktree)
                violations.extend(
                    protected_path_violations(worktree, changed, task.protected_paths)
                )
                if violations:
                    outcome = RunOutcome.POLICY_BLOCKED
                    trace("policy.blocked", "pre-command policy check failed")
                else:
                    audit_before = snapshot_tree(
                        run_directory, excluded_names={"worktree", "runtime"}
                    )
                    executor = CommandExecutor(
                        worktree=worktree,
                        runtime_directory=runtime,
                        policy=policy,
                        default_timeout=task.command_timeout_seconds,
                        max_output_bytes=task.max_output_bytes,
                        task_deadline=deadline,
                    )
                    if time.monotonic() >= deadline:
                        outcome = RunOutcome.TIMED_OUT
                        trace("task.timed_out", "task deadline expired before verification")
                    else:
                        for index, command in enumerate(task.commands):
                            trace("command.started", "verification command started", index=index)
                            result = executor.execute(index, command)
                            results.append(result)
                            trace(
                                "command.completed",
                                "verification command completed",
                                index=index,
                                passed=result.passed,
                                timed_out=result.timed_out,
                            )
                            if result.timed_out:
                                outcome = RunOutcome.TIMED_OUT
                                break
                    changed = changed_files(worktree)
                    violations.extend(
                        protected_path_violations(worktree, changed, task.protected_paths)
                    )
                    audit_after = snapshot_tree(
                        run_directory, excluded_names={"worktree", "runtime"}
                    )
                    outside_changes = snapshot_changes(audit_before, audit_after)
                    if outside_changes:
                        violations.append(
                            PolicyViolation(
                                code="outside_worktree_write",
                                message="verification wrote outside managed worktree/runtime paths",
                                paths=outside_changes,
                            )
                        )
                        remove_owned_audit_paths(run_directory, outside_changes)
                    source_after = snapshot_tree(repository.path, excluded_names={".git"})
                    source_changes = snapshot_changes(source_before, source_after)
                    if source_changes:
                        violations.append(
                            PolicyViolation(
                                code="source_checkout_modified",
                                message="verification modified the source checkout",
                                paths=source_changes,
                            )
                        )
                    if violations:
                        outcome = RunOutcome.POLICY_BLOCKED
                    elif outcome != RunOutcome.TIMED_OUT:
                        outcome = (
                            RunOutcome.PASSED
                            if all(result.passed for result in results)
                            else RunOutcome.FAILED_VERIFICATION
                        )
                final_patch = final_diff(worktree, resolved_commit)
        except (HarnessError, OSError, ValueError) as exc:
            trace("harness.error", str(exc), error_type=type(exc).__name__)
            if time.monotonic() >= deadline:
                outcome = RunOutcome.TIMED_OUT
            elif isinstance(exc, CommandPolicyError):
                violations.append(
                    PolicyViolation(code="command_not_allowed", message=str(exc), paths=[])
                )
                outcome = RunOutcome.POLICY_BLOCKED
            else:
                outcome = RunOutcome.PREFLIGHT_FAILED
        finally:
            if worktree_registered:
                try:
                    repository.remove_worktree(worktree)
                    trace("worktree.removed", "detached worktree removed")
                except HarnessError as exc:
                    trace("worktree.cleanup_failed", str(exc))
                    violations.append(
                        PolicyViolation(
                            code="workspace_cleanup_failed",
                            message=str(exc),
                            paths=[worktree.name],
                        )
                    )
                    outcome = RunOutcome.POLICY_BLOCKED
            shutil.rmtree(runtime, ignore_errors=True)

        finished_at = datetime.now(UTC)
        report = HarnessReport(
            run_id=run_id,
            case_id=task.case_id,
            resolved_base_commit=resolved_commit,
            outcome=outcome,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=time.monotonic() - started,
            patch=patch_result,
            commands=results,
            changed_files=changed,
            policy_violations=violations,
            trace_events=traces,
            artifact_directory=run_directory,
        )
        self.store.finalize(
            run_directory=run_directory,
            task=task,
            report=report,
            final_diff=final_patch,
            patch_bytes=patch_bytes,
        )
        return report
