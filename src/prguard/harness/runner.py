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
from prguard.harness.errors import CommandPolicyError, HarnessError, PreflightError
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


def _materialize_runtime_files(worktree: Path, task: Task) -> dict[str, str]:
    root = worktree.resolve()
    fingerprints: dict[str, str] = {}
    for spec in task.runtime_files:
        candidate = worktree / spec.path
        try:
            candidate.resolve(strict=False).relative_to(root)
        except ValueError as exc:
            raise PreflightError("runtime file resolves outside the worktree") from exc
        if candidate.exists() or candidate.is_symlink():
            raise PreflightError(f"runtime file path already exists at Base Commit: {spec.path}")
        candidate.parent.mkdir(parents=True, exist_ok=True)
        payload = spec.content.encode("utf-8")
        candidate.write_bytes(payload)
        fingerprints[spec.path] = hashlib.sha256(payload).hexdigest()
    return fingerprints


def _runtime_file_violations(
    worktree: Path, fingerprints: dict[str, str]
) -> list[PolicyViolation]:
    modified: list[str] = []
    for relative, expected in fingerprints.items():
        candidate = worktree / relative
        if (
            candidate.is_symlink()
            or not candidate.is_file()
            or hashlib.sha256(candidate.read_bytes()).hexdigest() != expected
        ):
            modified.append(relative)
    if not modified:
        return []
    return [
        PolicyViolation(
            code="runtime_scaffold_modified",
            message="verification modified a Harness-owned runtime scaffold",
            paths=sorted(modified),
        )
    ]


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
        runtime_fingerprints: dict[str, str] = {}
        runtime_paths = {spec.path for spec in task.runtime_files}
        effective_protected = [*task.protected_paths, *sorted(runtime_paths)]

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
                    protected_path_violations(worktree, changed, effective_protected)
                )
                if violations:
                    outcome = RunOutcome.POLICY_BLOCKED
                    trace("policy.blocked", "pre-command policy check failed")
                else:
                    runtime_fingerprints = _materialize_runtime_files(worktree, task)
                    if runtime_fingerprints:
                        trace(
                            "runtime.prepared",
                            "deterministic runtime scaffolds created",
                            paths=sorted(runtime_fingerprints),
                        )
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
                        container=task.container,
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
                            if result.infrastructure_error:
                                outcome = RunOutcome.PREFLIGHT_FAILED
                                break
                    changed = [
                        path for path in changed_files(worktree) if path not in runtime_paths
                    ]
                    violations.extend(
                        protected_path_violations(worktree, changed, effective_protected)
                    )
                    violations.extend(
                        _runtime_file_violations(worktree, runtime_fingerprints)
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
                    elif outcome not in {RunOutcome.TIMED_OUT, RunOutcome.PREFLIGHT_FAILED}:
                        outcome = (
                            RunOutcome.PASSED
                            if all(result.passed for result in results)
                            else RunOutcome.FAILED_VERIFICATION
                        )
                final_patch = final_diff(
                    worktree,
                    resolved_commit,
                    deadline=deadline,
                    excluded_paths=sorted(runtime_paths),
                )
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
