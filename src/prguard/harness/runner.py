"""Top-level deterministic verification harness."""

from __future__ import annotations

import ast
import hashlib
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
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
    CommandSpec,
    HarnessReport,
    PatchApplicationResult,
    PolicyViolation,
    RunOutcome,
    Task,
    TraceEvent,
    VerificationResult,
)


def _is_pytest_command(command: CommandSpec) -> bool:
    argv = command.argv
    return argv[0] == "pytest" or (
        len(argv) >= 3
        and argv[0] in {"python", "python3", "python3.12"}
        and argv[1:3] == ["-m", "pytest"]
    )


def _changed_python_tests(paths: list[str]) -> list[str]:
    tests: list[str] = []
    for value in paths:
        path = PurePosixPath(value)
        if path.suffix != ".py" or path.name == "conftest.py":
            continue
        in_test_root = bool({"test", "tests"} & set(path.parts[:-1]))
        conventional_name = path.name.startswith("test_") or path.name.endswith("_test.py")
        if (in_test_root or len(path.parts) == 1) and conventional_name:
            tests.append(path.as_posix())
    return sorted(tests)


def _changed_python_test_support(paths: list[str]) -> list[str]:
    """Return changed Python files under test roots, including conftest helpers."""

    return sorted(
        value
        for value in paths
        if PurePosixPath(value).suffix == ".py"
        and bool({"test", "tests"} & set(PurePosixPath(value).parts[:-1]))
    )


def _has_executable_python_change(base: Path, candidate: Path) -> bool:
    """Distinguish Python behavior changes from comments and formatting only."""

    if not base.is_file():
        return True
    try:
        base_tree = ast.parse(base.read_text(encoding="utf-8"))
        candidate_tree = ast.parse(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        # Fail closed: an unreadable or invalid changed test still needs a Base probe.
        return True
    return ast.dump(base_tree, include_attributes=False) != ast.dump(
        candidate_tree, include_attributes=False
    )


def _generated_test_command(
    commands: list[CommandSpec], changed_paths: list[str]
) -> tuple[CommandSpec | None, PolicyViolation | None]:
    changed_tests = _changed_python_tests(changed_paths)
    if not changed_tests:
        return None, None
    pytest_commands = [command for command in commands if _is_pytest_command(command)]
    if not pytest_commands:
        return None, PolicyViolation(
            code="changed_tests_without_pytest",
            message="candidate changes Python tests but the Task declares no pytest capability",
            paths=changed_tests,
        )
    explicitly_covered = {
        path
        for command in pytest_commands
        for token in command.argv
        for path in changed_tests
        if token.split("::", 1)[0].rstrip("/") == path
    }
    uncovered = [path for path in changed_tests if path not in explicitly_covered]
    if not uncovered:
        return None, None
    return (
        CommandSpec(
            argv=["pytest", "-q", *uncovered],
            kind="pytest_changed_tests",
        ),
        None,
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


def _runtime_file_violations(worktree: Path, fingerprints: dict[str, str]) -> list[PolicyViolation]:
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


def _run_changed_test_base_probe(
    *,
    repository: GitRepository,
    run_directory: Path,
    candidate_worktree: Path,
    resolved_commit: str,
    task: Task,
    changed_paths: list[str],
    changed_tests: list[str],
    deadline: float,
) -> tuple[VerificationResult | None, list[PolicyViolation], list[str]]:
    """Run Agent-authored tests on Base while withholding candidate source changes."""

    probe_worktree = run_directory / "changed-test-base-worktree"
    probe_runtime = run_directory / "changed-test-base-runtime"
    (probe_runtime / "home").mkdir(parents=True)
    (probe_runtime / "tmp").mkdir(parents=True)
    registered = False
    violations: list[PolicyViolation] = []
    result: VerificationResult | None = None
    excluded = {
        "worktree",
        "runtime",
        probe_worktree.name,
        probe_runtime.name,
    }
    audit_before = snapshot_tree(run_directory, excluded_names=excluded)
    source_before = snapshot_tree(repository.path, excluded_names={".git"})
    try:
        repository.add_worktree(probe_worktree, resolved_commit, deadline=deadline)
        registered = True
        probed_tests = [
            relative
            for relative in changed_tests
            if _has_executable_python_change(
                probe_worktree / relative, candidate_worktree / relative
            )
        ]
        if not probed_tests:
            return None, violations, []
        invalid: list[str] = []
        for relative in _changed_python_test_support(changed_paths):
            source = candidate_worktree / relative
            destination = probe_worktree / relative
            if source.is_symlink() or not source.is_file():
                invalid.append(relative)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        if invalid:
            violations.append(
                PolicyViolation(
                    code="changed_test_not_regular",
                    message="changed Python tests must be regular files for the Base probe",
                    paths=invalid,
                )
            )
            return None, violations, probed_tests

        runtime_fingerprints = _materialize_runtime_files(probe_worktree, task)
        expected_diff = final_diff(
            probe_worktree,
            resolved_commit,
            deadline=deadline,
            excluded_paths=sorted(runtime_fingerprints),
        )
        command = CommandSpec(
            argv=["pytest", "-q", *probed_tests],
            kind="pytest_changed_tests_base",
        )
        executor = CommandExecutor(
            worktree=probe_worktree,
            runtime_directory=probe_runtime,
            policy=CommandPolicy([command.argv]),
            default_timeout=task.command_timeout_seconds,
            max_output_bytes=task.max_output_bytes,
            task_deadline=deadline,
            container=task.container,
        )
        result = executor.execute(0, command)
        actual_diff = final_diff(
            probe_worktree,
            resolved_commit,
            deadline=deadline,
            excluded_paths=sorted(runtime_fingerprints),
        )
        if actual_diff != expected_diff:
            violations.append(
                PolicyViolation(
                    code="changed_test_base_probe_modified_worktree",
                    message="the changed-test Base probe modified its worktree",
                    paths=changed_files(probe_worktree),
                )
            )
        violations.extend(_runtime_file_violations(probe_worktree, runtime_fingerprints))
    finally:
        audit_after = snapshot_tree(run_directory, excluded_names=excluded)
        outside_changes = snapshot_changes(audit_before, audit_after)
        if outside_changes:
            violations.append(
                PolicyViolation(
                    code="changed_test_base_probe_outside_write",
                    message="the changed-test Base probe wrote outside managed paths",
                    paths=outside_changes,
                )
            )
            remove_owned_audit_paths(run_directory, outside_changes)
        source_after = snapshot_tree(repository.path, excluded_names={".git"})
        source_changes = snapshot_changes(source_before, source_after)
        if source_changes:
            violations.append(
                PolicyViolation(
                    code="changed_test_base_probe_modified_source",
                    message="the changed-test Base probe modified the source checkout",
                    paths=source_changes,
                )
            )
        if registered:
            try:
                repository.remove_worktree(probe_worktree)
            except HarnessError as exc:
                violations.append(
                    PolicyViolation(
                        code="changed_test_base_probe_cleanup_failed",
                        message=str(exc),
                        paths=[probe_worktree.name],
                    )
                )
        shutil.rmtree(probe_worktree, ignore_errors=True)
        shutil.rmtree(probe_runtime, ignore_errors=True)
    return result, violations, probed_tests


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
        changed_test_base_results = []
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
                violations.extend(protected_path_violations(worktree, changed, effective_protected))
                changed_test_command, changed_test_violation = _generated_test_command(
                    task.commands, changed
                )
                if changed_test_violation is not None:
                    violations.append(changed_test_violation)
                base_probe_outcome: RunOutcome | None = None
                changed_tests = _changed_python_tests(changed)
                if not violations and task.require_changed_tests_fail_on_base and changed_tests:
                    trace(
                        "changed_tests.base_probe_started",
                        "running changed tests against the unchanged Base",
                        paths=changed_tests,
                    )
                    base_result, base_violations, probed_tests = _run_changed_test_base_probe(
                        repository=repository,
                        run_directory=run_directory,
                        candidate_worktree=worktree,
                        resolved_commit=resolved_commit,
                        task=task,
                        changed_paths=changed,
                        changed_tests=changed_tests,
                        deadline=deadline,
                    )
                    violations.extend(base_violations)
                    if not probed_tests:
                        trace(
                            "changed_tests.base_probe_skipped",
                            "changed test files contain no executable Python changes",
                            paths=changed_tests,
                        )
                    if base_result is not None:
                        changed_test_base_results.append(base_result)
                        if base_result.timed_out:
                            base_probe_outcome = RunOutcome.TIMED_OUT
                        elif base_result.infrastructure_error:
                            base_probe_outcome = RunOutcome.PREFLIGHT_FAILED
                        elif base_result.passed:
                            violations.append(
                                PolicyViolation(
                                    code="changed_tests_pass_on_base",
                                    message=(
                                        "Agent-authored tests do not demonstrate "
                                        "FAIL_TO_PASS behavior"
                                    ),
                                    paths=probed_tests,
                                )
                            )
                        elif base_result.exit_code != 1:
                            violations.append(
                                PolicyViolation(
                                    code="changed_tests_base_probe_invalid",
                                    message=(
                                        "Agent-authored tests must collect on Base and fail as "
                                        "tests; collection/import errors are not FAIL_TO_PASS "
                                        "evidence"
                                    ),
                                    paths=probed_tests,
                                )
                            )
                        else:
                            trace(
                                "changed_tests.base_probe_failed_as_expected",
                                "changed tests fail against Base and may join the gate",
                                exit_code=base_result.exit_code,
                            )
                if violations:
                    outcome = RunOutcome.POLICY_BLOCKED
                    trace("policy.blocked", "pre-command policy check failed")
                elif base_probe_outcome is not None:
                    outcome = base_probe_outcome
                    trace(
                        "changed_tests.base_probe_stopped",
                        "changed-test Base probe could not establish FAIL_TO_PASS",
                        outcome=outcome.value,
                    )
                else:
                    runtime_fingerprints = _materialize_runtime_files(worktree, task)
                    if runtime_fingerprints:
                        trace(
                            "runtime.prepared",
                            "deterministic runtime scaffolds created",
                            paths=sorted(runtime_fingerprints),
                        )
                    candidate_diff_before_commands = final_diff(
                        worktree,
                        resolved_commit,
                        deadline=deadline,
                        excluded_paths=sorted(runtime_paths),
                    )
                    audit_before = snapshot_tree(
                        run_directory, excluded_names={"worktree", "runtime"}
                    )
                    verification_commands = list(task.commands)
                    execution_policy = policy
                    if changed_test_command is not None:
                        verification_commands.append(changed_test_command)
                        execution_policy = CommandPolicy(
                            [*task.allowed_commands, changed_test_command.argv]
                        )
                        trace(
                            "verification.derived",
                            "changed Python tests added to the deterministic gate",
                            argv=changed_test_command.argv,
                        )
                    executor = CommandExecutor(
                        worktree=worktree,
                        runtime_directory=runtime,
                        policy=execution_policy,
                        default_timeout=task.command_timeout_seconds,
                        max_output_bytes=task.max_output_bytes,
                        task_deadline=deadline,
                        container=task.container,
                    )
                    if time.monotonic() >= deadline:
                        outcome = RunOutcome.TIMED_OUT
                        trace("task.timed_out", "task deadline expired before verification")
                    else:
                        for index, command in enumerate(verification_commands):
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
                    candidate_diff_after_commands = final_diff(
                        worktree,
                        resolved_commit,
                        deadline=deadline,
                        excluded_paths=sorted(runtime_paths),
                    )
                    if candidate_diff_after_commands != candidate_diff_before_commands:
                        violations.append(
                            PolicyViolation(
                                code="verification_modified_worktree",
                                message=(
                                    "verification commands modified the candidate worktree; "
                                    "verification must be non-mutating"
                                ),
                                paths=[
                                    path
                                    for path in changed_files(worktree)
                                    if path not in runtime_paths
                                ],
                            )
                        )
                    changed = [
                        path for path in changed_files(worktree) if path not in runtime_paths
                    ]
                    violations.extend(
                        protected_path_violations(worktree, changed, effective_protected)
                    )
                    violations.extend(_runtime_file_violations(worktree, runtime_fingerprints))
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
            changed_test_base_results=changed_test_base_results,
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
