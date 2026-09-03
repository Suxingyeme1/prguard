"""Small Phase 1 command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import ClassVar

from prguard.harness import VerificationHarness, load_replay_task, verify_manifest
from prguard.harness.errors import ArtifactIntegrityError
from prguard.schemas import (
    FixOutcome,
    FixTask,
    IssueToPROutcome,
    IssueToPRTask,
    ReviewOutcome,
    ReviewRepairOutcome,
    ReviewRepairTask,
    ReviewRoutingMode,
    ReviewTask,
    RunOutcome,
    Task,
)


class _ProgressReporter:
    """Human-readable stderr progress while stdout remains a JSON contract."""

    _labels: ClassVar[dict[str, str]] = {
        "run.started": "run created",
        "onboarding.started": "freezing GitHub Issue and repository",
        "onboarding.completed": "GitHub task prepared",
        "onboarding.local_started": "freezing local repository and Issue",
        "onboarding.local_completed": "local task prepared",
        "preflight.started": "validating repository and base commit",
        "preflight.completed": "isolated worktree ready",
        "readiness.started": "checking base test collection",
        "readiness.completed": "base test collection checked",
        "attempt.started": "Implementer working",
        "proposal.completed": "candidate Patch received",
        "verification.started": "deterministic verification running",
        "verification.completed": "verification completed",
        "repair.requested": "failure evidence returned for one repair",
        "attempt.failed": "Implementer attempt failed",
        "run.completed": "run completed",
    }

    def __init__(self, enabled: bool, heartbeat_seconds: float = 15.0) -> None:
        self.enabled = enabled
        self.heartbeat_seconds = heartbeat_seconds
        self.started = time.monotonic()
        self.phase = "starting"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.enabled:
            return
        print("[prguard] starting verified Issue-to-Patch run", file=sys.stderr, flush=True)
        self._thread = threading.Thread(target=self._heartbeat, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.enabled:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def __call__(self, event: str, data: dict[str, object]) -> None:
        if not self.enabled:
            return
        self.phase = self._labels.get(event, event)
        details = self._details(event, data)
        suffix = f" — {details}" if details else ""
        print(f"[prguard] {self.phase}{suffix}", file=sys.stderr, flush=True)

    def _heartbeat(self) -> None:
        while not self._stop.wait(self.heartbeat_seconds):
            elapsed = int(time.monotonic() - self.started)
            print(
                f"[prguard] still running ({elapsed}s) — {self.phase}",
                file=sys.stderr,
                flush=True,
            )

    @staticmethod
    def _details(event: str, data: dict[str, object]) -> str:
        if event == "attempt.started":
            attempt = int(data.get("attempt", 0))
            return f"attempt {attempt}{' (repair)' if data.get('repair') else ''}"
        if event == "proposal.completed":
            return (
                f"{data.get('tool_calls', 0)} tool calls, "
                f"{data.get('patch_bytes', 0)} Patch bytes"
            )
        if event == "verification.completed":
            return str(data.get("outcome", "unknown"))
        if event == "repair.requested":
            return str(data.get("failure", "failed"))
        if event == "run.completed":
            return (
                f"{data.get('outcome', 'unknown')}, {data.get('attempts', 0)} attempt(s), "
                f"{data.get('duration_seconds', 0)}s"
            )
        return ""


def load_task(path: Path) -> Task:
    path = path.expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in ("repository", "candidate_patch"):
        value = payload.get(key)
        if value and not Path(value).is_absolute():
            payload[key] = path.parent / value
    return Task.model_validate(payload)


def load_fix_task(path: Path) -> FixTask:
    path = path.expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    repository = payload.get("repository")
    if repository and not Path(repository).is_absolute():
        payload["repository"] = path.parent / repository
    return FixTask.model_validate(payload)


def load_issue_to_pr_task(path: Path) -> IssueToPRTask:
    path = path.expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    repository = payload.get("repository")
    if repository and not Path(repository).is_absolute():
        payload["repository"] = path.parent / repository
    if "fix_timeout_seconds" not in payload and "review_timeout_seconds" not in payload:
        total = float(payload.get("task_timeout_seconds", 1200))
        payload["fix_timeout_seconds"] = min(600.0, total * 0.65)
        payload["review_timeout_seconds"] = min(300.0, total * 0.25)
    return IssueToPRTask.model_validate(payload)


def load_review_task(path: Path) -> ReviewTask:
    path = path.expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("mode", None)
    for key in ("repository", "candidate_patch"):
        value = payload.get(key)
        if value and not Path(value).is_absolute():
            payload[key] = path.parent / value
    return ReviewTask.model_validate(payload)


def load_review_repair_task(path: Path) -> ReviewRepairTask:
    path = path.expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("mode", None)
    for key in ("repository", "candidate_patch"):
        value = payload.get(key)
        if value and not Path(value).is_absolute():
            payload[key] = path.parent / value
    return ReviewRepairTask.model_validate(payload)


def review_task_from_fix_task(
    path: Path, candidate_patch: Path, *, repair: bool
) -> ReviewTask | ReviewRepairTask:
    fix = load_fix_task(path)
    common: dict[str, object] = {
        "case_id": f"{fix.case_id}-review",
        "repository": fix.repository,
        "base_commit": fix.base_commit,
        "issue": fix.issue,
        "candidate_patch": candidate_patch.expanduser().resolve(),
        "commands": fix.commands,
        "allowed_commands": fix.allowed_commands,
        "protected_paths": fix.protected_paths,
        "command_timeout_seconds": fix.command_timeout_seconds,
        "task_timeout_seconds": fix.task_timeout_seconds,
        "max_output_bytes": fix.max_output_bytes,
        "max_tool_calls": fix.max_tool_calls,
        "max_file_bytes": fix.max_file_bytes,
        "max_context_bytes": fix.max_context_bytes,
        "container": fix.container,
        "runtime_files": fix.runtime_files,
    }
    if not repair:
        return ReviewTask.model_validate(common)
    return ReviewRepairTask.model_validate(
        {
            **common,
            "writable_paths": fix.writable_paths,
            "max_patch_bytes": fix.max_patch_bytes,
            "max_changed_files": fix.max_changed_files,
            "review_timeout_seconds": min(300.0, fix.task_timeout_seconds * 0.4),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prguard")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="execute a deterministic local PR case")
    run.add_argument("case", type=Path)
    run.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    verify = subparsers.add_parser(
        "verify-manifest", help="verify artifact hashes without execution"
    )
    verify.add_argument("manifest", type=Path)
    replay = subparsers.add_parser("replay", help="rerun a verified archived task")
    replay.add_argument("manifest", type=Path)
    replay.add_argument("--repository", type=Path)
    replay.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    inspect_symbol = subparsers.add_parser(
        "inspect-symbol",
        help="trace a bounded static Python call graph at a frozen FixTask base commit",
    )
    inspect_symbol.add_argument("task", type=Path)
    inspect_symbol.add_argument("--symbol", required=True)
    inspect_symbol.add_argument(
        "--direction", choices=("callers", "callees", "both"), default="both"
    )
    inspect_symbol.add_argument("--max-depth", type=int, choices=(1, 2, 3), default=2)
    inspect_symbol.add_argument("--max-results", type=int, default=100)
    inspect_policy = subparsers.add_parser(
        "inspect-policy",
        help="explain local project-policy discovery without running repository code",
    )
    inspect_policy.add_argument("--repository", type=Path, required=True)
    inspect_policy.add_argument("--base-commit", default="HEAD")
    policy_issue = inspect_policy.add_mutually_exclusive_group()
    policy_issue.add_argument("--issue", help="optional Issue text for related-test discovery")
    policy_issue.add_argument("--issue-file", type=Path, help="UTF-8 Issue text file")
    prepare = subparsers.add_parser(
        "prepare-github",
        help="freeze a public GitHub Issue and repository into a validated FixTask",
    )
    prepare.add_argument("issue_url")
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--base-commit")
    prepare.add_argument(
        "--source-repository",
        type=Path,
        help="same-origin local Git repository to use as a download cache",
    )
    execution = prepare.add_mutually_exclusive_group(required=True)
    execution.add_argument(
        "--trust-host",
        action="store_true",
        help="explicitly allow unsandboxed host verification for this repository",
    )
    execution.add_argument(
        "--container-image",
        help="immutable sha256 image ID/digest for container verification",
    )
    prepare_local = subparsers.add_parser(
        "prepare-local",
        help="freeze a local Git repository and natural-language Issue into a FixTask",
    )
    prepare_local.add_argument("--repository", type=Path, required=True)
    local_issue = prepare_local.add_mutually_exclusive_group(required=True)
    local_issue.add_argument("--issue", help="natural-language Issue text")
    local_issue.add_argument("--issue-file", type=Path, help="UTF-8 Issue text file")
    prepare_local.add_argument("--output", type=Path, required=True)
    prepare_local.add_argument("--base-commit", default="HEAD")
    local_execution = prepare_local.add_mutually_exclusive_group(required=True)
    local_execution.add_argument(
        "--trust-host",
        action="store_true",
        help="explicitly allow unsandboxed host verification for this repository",
    )
    local_execution.add_argument(
        "--container-image",
        help="immutable sha256 image ID/digest for container verification",
    )
    fix = subparsers.add_parser(
        "fix",
        help="generate and verify a patch from Task JSON, GitHub Issue, or local Issue text",
    )
    fix.add_argument(
        "task",
        nargs="?",
        help="FixTask JSON, GitHub Issue URL, or Issue text when --repository is used",
    )
    fix.add_argument(
        "--repository",
        type=Path,
        help="clean local Git repository used with positional Issue text or --issue-file",
    )
    fix.add_argument(
        "--issue-file",
        type=Path,
        help="UTF-8 local Issue text file; requires --repository",
    )
    fix.add_argument(
        "--workspace",
        type=Path,
        help="new preparation workspace required for GitHub or local Issue input",
    )
    fix.add_argument("--base-commit")
    fix.add_argument(
        "--source-repository",
        type=Path,
        help="same-origin local Git repository to use as a download cache",
    )
    fix_execution = fix.add_mutually_exclusive_group()
    fix_execution.add_argument(
        "--trust-host",
        action="store_true",
        help="explicitly allow unsandboxed host verification for a prepared repository",
    )
    fix_execution.add_argument(
        "--container-image",
        help="immutable sha256 image ID/digest for prepared repository verification",
    )
    fix.add_argument(
        "--artifacts",
        type=Path,
        help="run artifact root (defaults to WORKSPACE/fix-runs or artifacts/fix)",
    )
    fix.add_argument(
        "--provider", choices=("deepseek", "openai", "scripted"), default="openai"
    )
    fix.add_argument("--model")
    fix.add_argument("--reasoning-effort")
    fix.add_argument(
        "--progress",
        action="store_true",
        help="print human-readable stages and heartbeats to stderr",
    )
    fix.add_argument("--proposal-sequence", type=Path)
    fix.add_argument(
        "--review",
        action="store_true",
        help="continue an accepted fix through independent review and optional repair",
    )
    fix.add_argument(
        "--review-policy",
        choices=("always", "shadow", "selective"),
        help=(
            "Reviewer routing for fix --review; default Task policy is always, shadow records "
            "a recommendation but still reviews, selective may skip only low-risk patches"
        ),
    )
    fix.add_argument(
        "--review-provider", choices=("deepseek", "scripted"), default="deepseek"
    )
    fix.add_argument("--review-model")
    fix.add_argument("--review-reasoning-effort", default="high")
    fix.add_argument("--scripted-review", type=Path)
    fix.add_argument(
        "--review-repair-provider", choices=("deepseek", "openai", "scripted")
    )
    fix.add_argument("--review-repair-model")
    fix.add_argument("--review-repair-reasoning-effort")
    fix.add_argument("--review-repair-proposal-sequence", type=Path)
    review = subparsers.add_parser("review", help="independently review a candidate patch")
    review.add_argument("task", type=Path)
    review.add_argument(
        "--candidate-patch",
        type=Path,
        help="reuse a frozen FixTask JSON and supply its candidate Patch directly",
    )
    review.add_argument("--artifacts", type=Path, default=Path("artifacts/review"))
    review.add_argument("--provider", choices=("deepseek", "scripted"), default="deepseek")
    review.add_argument("--model")
    review.add_argument("--reasoning-effort", default="high")
    review.add_argument("--scripted-review", type=Path)
    review.add_argument(
        "--repair",
        action="store_true",
        help="allow one controlled full replacement-patch attempt after a blocking review",
    )
    review.add_argument(
        "--repair-provider",
        choices=("deepseek", "openai", "scripted"),
        default="deepseek",
    )
    review.add_argument("--repair-model")
    review.add_argument("--repair-reasoning-effort")
    review.add_argument("--repair-proposal-sequence", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "inspect-policy":
        from prguard.onboarding import inspect_project_policy, read_issue_file
        from prguard.onboarding.errors import OnboardingError, ProjectDiscoveryError

        try:
            issue = read_issue_file(args.issue_file) if args.issue_file else args.issue
            report = inspect_project_policy(
                args.repository,
                issue=issue,
                base_commit=args.base_commit,
            )
        except (OnboardingError, ProjectDiscoveryError, ValueError) as exc:
            print(f"policy inspection failed: {exc}", file=sys.stderr)
            return 2
        print(report.model_dump_json(indent=2))
        return 0 if report.status == "ready" else 1
    if args.command == "prepare-local":
        from prguard.onboarding import prepare_local_issue, read_issue_file
        from prguard.onboarding.errors import OnboardingError

        try:
            issue = read_issue_file(args.issue_file) if args.issue_file else args.issue
            report = prepare_local_issue(
                args.repository,
                issue,
                args.output,
                base_commit=args.base_commit,
                trust_host=args.trust_host,
                container_image=args.container_image,
            )
        except (OnboardingError, ValueError) as exc:
            print(f"local task preparation failed: {exc}", file=sys.stderr)
            return 2
        print(report.model_dump_json(indent=2))
        return 0
    if args.command == "prepare-github":
        from prguard.onboarding import prepare_github_issue
        from prguard.onboarding.errors import OnboardingError

        try:
            report = prepare_github_issue(
                args.issue_url,
                args.output,
                base_commit=args.base_commit,
                trust_host=args.trust_host,
                container_image=args.container_image,
                source_repository=args.source_repository,
            )
        except (OnboardingError, ValueError) as exc:
            print(f"GitHub task preparation failed: {exc}", file=sys.stderr)
            return 2
        print(report.model_dump_json(indent=2))
        return 0
    if args.command == "run":
        task = load_task(args.case)
        report = VerificationHarness(args.artifacts).run(task)
        print(report.model_dump_json(indent=2))
        return 0 if report.outcome == RunOutcome.PASSED else 1
    if args.command == "replay":
        try:
            task = load_replay_task(args.manifest, repository=args.repository)
        except ArtifactIntegrityError as exc:
            print(f"replay rejected: {exc}")
            return 1
        report = VerificationHarness(args.artifacts).run(task)
        print(report.model_dump_json(indent=2))
        return 0 if report.outcome == RunOutcome.PASSED else 1
    if args.command == "inspect-symbol":
        from prguard.harness.errors import PreflightError
        from prguard.harness.git import GitRepository
        from prguard.implementer.errors import RepositoryAccessError
        from prguard.implementer.tools import RepositoryTools

        try:
            task = load_fix_task(args.task)
            repository = GitRepository(task.repository)
            resolved = repository.preflight(task.base_commit)
            with tempfile.TemporaryDirectory(prefix="prguard-inspect-") as temporary:
                worktree = Path(temporary) / "worktree"
                repository.add_worktree(worktree, resolved)
                try:
                    result = RepositoryTools(worktree, task).trace_call_graph(
                        args.symbol,
                        args.direction,
                        args.max_depth,
                        args.max_results,
                    )
                finally:
                    repository.remove_worktree(worktree)
        except (OSError, ValueError, PreflightError, RepositoryAccessError) as exc:
            print(f"symbol inspection failed: {exc}", file=sys.stderr)
            return 2
        print(
            json.dumps(
                {"resolved_base_commit": resolved, "call_graph": result},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "fix":
        from prguard.fix import FixRunner
        from prguard.implementer.errors import ProviderError
        from prguard.implementer.providers import (
            DeepSeekChatProvider,
            OpenAIResponsesProvider,
            ScriptedProvider,
        )
        from prguard.onboarding import (
            prepare_github_issue,
            prepare_local_issue,
            read_issue_file,
        )
        from prguard.onboarding.errors import OnboardingError

        progress = _ProgressReporter(args.progress)
        progress.start()
        try:
            if args.review_policy is not None and not args.review:
                raise ProviderError("--review-policy requires --review")
            target = args.task
            is_url = target is not None and target.startswith("https://github.com/")
            is_local_issue = args.repository is not None or args.issue_file is not None
            if is_url and is_local_issue:
                raise OnboardingError(
                    "GitHub Issue URL cannot be combined with local Issue options"
                )
            if is_local_issue:
                if args.repository is None:
                    raise OnboardingError("--issue-file requires --repository")
                if target is not None and args.issue_file is not None:
                    raise OnboardingError(
                        "choose positional Issue text or --issue-file, not both"
                    )
                if target is None and args.issue_file is None:
                    raise OnboardingError(
                        "local repository mode requires positional Issue text or --issue-file"
                    )
                if args.workspace is None:
                    raise OnboardingError(
                        "--workspace is required when fix receives a local Issue"
                    )
                if args.source_repository is not None:
                    raise OnboardingError(
                        "--source-repository is only valid for a GitHub Issue URL"
                    )
                issue = read_issue_file(args.issue_file) if args.issue_file else target
                progress(
                    "onboarding.local_started",
                    {"repository": str(args.repository)},
                )
                preparation = prepare_local_issue(
                    args.repository,
                    issue,
                    args.workspace,
                    base_commit=args.base_commit or "HEAD",
                    trust_host=args.trust_host,
                    container_image=args.container_image,
                )
                progress(
                    "onboarding.local_completed",
                    {
                        "case_id": preparation.issue.issue_sha256[:12],
                        "base_commit": preparation.issue.base_commit,
                    },
                )
                task_path = preparation.task_path
                artifact_root = args.artifacts or (args.workspace / "fix-runs")
            elif is_url:
                if args.workspace is None:
                    raise OnboardingError(
                        "--workspace is required when fix receives a GitHub Issue URL"
                    )
                progress("onboarding.started", {"issue_url": target})
                preparation = prepare_github_issue(
                    target,
                    args.workspace,
                    base_commit=args.base_commit,
                    trust_host=args.trust_host,
                    container_image=args.container_image,
                    source_repository=args.source_repository,
                )
                progress(
                    "onboarding.completed",
                    {
                        "case_id": preparation.issue.reference.number,
                        "base_commit": preparation.issue.base_commit,
                    },
                )
                task_path = preparation.task_path
                artifact_root = args.artifacts or (args.workspace / "fix-runs")
            else:
                if target is None:
                    raise OnboardingError(
                        "fix requires Task JSON, a GitHub Issue URL, or local Issue input"
                    )
                if any(
                    value is not None and value is not False
                    for value in (
                        args.workspace,
                        args.base_commit,
                        args.source_repository,
                        args.trust_host,
                        args.container_image,
                        args.repository,
                        args.issue_file,
                    )
                ):
                    raise OnboardingError(
                        "preparation options require a GitHub Issue URL or local Issue input"
                    )
                task_path = Path(target)
                artifact_root = args.artifacts or Path("artifacts/fix")
            task = (
                load_issue_to_pr_task(task_path)
                if args.review
                else load_fix_task(task_path)
            )
            if args.review and args.review_policy is not None:
                task = task.model_copy(
                    update={
                        "review_routing_mode": ReviewRoutingMode(args.review_policy)
                    }
                )
            if args.provider == "scripted":
                if args.proposal_sequence is None:
                    raise ProviderError("--proposal-sequence is required for scripted provider")
                provider = ScriptedProvider.from_file(args.proposal_sequence)
            elif args.provider == "deepseek":
                provider = DeepSeekChatProvider(
                    model=args.model or DeepSeekChatProvider.default_model,
                    reasoning_effort=args.reasoning_effort or "high",
                )
            else:
                provider = OpenAIResponsesProvider(
                    model=args.model or "gpt-5.6-terra",
                    reasoning_effort=args.reasoning_effort or "medium",
                )
            if args.review:
                from prguard.pipeline import IssueToPRRunner
                from prguard.reviewer import (
                    DeepSeekReviewerProvider,
                    ScriptedReviewerProvider,
                )

                if args.review_provider == "scripted":
                    def reviewer_source():
                        if args.scripted_review is None:
                            raise ProviderError(
                                "--scripted-review is required for scripted Reviewer"
                            )
                        return ScriptedReviewerProvider.from_file(args.scripted_review)
                else:
                    def reviewer_source():
                        return DeepSeekReviewerProvider(
                            model=(
                                args.review_model
                                or DeepSeekReviewerProvider.default_model
                            ),
                            reasoning_effort=args.review_reasoning_effort,
                        )
                repair_provider_name = args.review_repair_provider or args.provider
                if repair_provider_name == "scripted":
                    def repair_source():
                        if args.review_repair_proposal_sequence is None:
                            raise ProviderError(
                                "--review-repair-proposal-sequence is required for scripted repair"
                            )
                        return ScriptedProvider.from_file(
                            args.review_repair_proposal_sequence
                        )
                elif repair_provider_name == "deepseek":
                    def repair_source():
                        return DeepSeekChatProvider(
                            model=(
                                args.review_repair_model
                                or args.model
                                or DeepSeekChatProvider.default_model
                            ),
                            reasoning_effort=(
                                args.review_repair_reasoning_effort
                                or args.reasoning_effort
                                or "high"
                            ),
                        )
                else:
                    def repair_source():
                        return OpenAIResponsesProvider(
                            model=(
                                args.review_repair_model
                                or args.model
                                or "gpt-5.6-terra"
                            ),
                            reasoning_effort=(
                                args.review_repair_reasoning_effort
                                or args.reasoning_effort
                                or "medium"
                            ),
                        )
                report = IssueToPRRunner(
                    artifact_root, provider, reviewer_source, repair_source
                ).run(task)
            else:
                report = FixRunner(artifact_root, provider, progress=progress).run(task)
        except (OnboardingError, ProviderError) as exc:
            print(f"fix configuration failed: {exc}", file=sys.stderr)
            return 2
        finally:
            progress.stop()
        print(report.model_dump_json(indent=2))
        if args.review:
            return 0 if report.outcome == IssueToPROutcome.ACCEPTED else 1
        return 0 if report.outcome == FixOutcome.ACCEPTED else 1
    if args.command == "review":
        from prguard.implementer.errors import ProviderError
        from prguard.implementer.providers import (
            DeepSeekChatProvider,
            OpenAIResponsesProvider,
            ScriptedProvider,
        )
        from prguard.review import ReviewRepairRunner, ReviewRunner
        from prguard.reviewer import DeepSeekReviewerProvider, ScriptedReviewerProvider

        try:
            if args.provider == "scripted":
                if args.scripted_review is None:
                    raise ProviderError("--scripted-review is required for scripted Reviewer")
                provider = ScriptedReviewerProvider.from_file(args.scripted_review)
            else:
                provider = DeepSeekReviewerProvider(
                    model=args.model or DeepSeekReviewerProvider.default_model,
                    reasoning_effort=args.reasoning_effort,
                )
            if args.repair:
                task = (
                    review_task_from_fix_task(
                        args.task, args.candidate_patch, repair=True
                    )
                    if args.candidate_patch is not None
                    else load_review_repair_task(args.task)
                )
                if args.repair_provider == "scripted":
                    if args.repair_proposal_sequence is None:
                        raise ProviderError(
                            "--repair-proposal-sequence is required for scripted repair"
                        )
                    implementer = ScriptedProvider.from_file(args.repair_proposal_sequence)
                elif args.repair_provider == "deepseek":
                    implementer = DeepSeekChatProvider(
                        model=args.repair_model or DeepSeekChatProvider.default_model,
                        reasoning_effort=args.repair_reasoning_effort or "high",
                    )
                else:
                    implementer = OpenAIResponsesProvider(
                        model=args.repair_model or "gpt-5.6-terra",
                        reasoning_effort=args.repair_reasoning_effort or "medium",
                    )
                report = ReviewRepairRunner(args.artifacts, provider, implementer).run(task)
            else:
                task = (
                    review_task_from_fix_task(
                        args.task, args.candidate_patch, repair=False
                    )
                    if args.candidate_patch is not None
                    else load_review_task(args.task)
                )
                report = ReviewRunner(args.artifacts, provider).run(task)
        except ProviderError as exc:
            print(f"review configuration failed: {exc}", file=sys.stderr)
            return 2
        print(report.model_dump_json(indent=2))
        if args.repair:
            return 0 if report.outcome in {
                ReviewRepairOutcome.ACCEPTED_WITHOUT_REPAIR,
                ReviewRepairOutcome.ACCEPTED_AFTER_REPAIR,
            } else 1
        return 0 if report.outcome == ReviewOutcome.REVIEWED else 1
    try:
        manifest = verify_manifest(args.manifest)
    except ArtifactIntegrityError as exc:
        print(f"manifest verification failed: {exc}")
        return 1
    print(f"manifest verified: {manifest.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
