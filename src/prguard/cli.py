"""Small Phase 1 command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
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
    ReviewTask,
    RunOutcome,
    Task,
)


class _ProgressReporter:
    """Human-readable stderr progress while stdout remains a JSON contract."""

    _labels: ClassVar[dict[str, str]] = {
        "run.started": "run created",
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
    fix = subparsers.add_parser("fix", help="generate and verify a patch from an Issue")
    fix.add_argument("task", type=Path)
    fix.add_argument("--artifacts", type=Path, default=Path("artifacts/fix"))
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
    if args.command == "fix":
        from prguard.fix import FixRunner
        from prguard.implementer.errors import ProviderError
        from prguard.implementer.providers import (
            DeepSeekChatProvider,
            OpenAIResponsesProvider,
            ScriptedProvider,
        )

        task = load_issue_to_pr_task(args.task) if args.review else load_fix_task(args.task)
        progress = _ProgressReporter(args.progress)
        progress.start()
        try:
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
                    if args.scripted_review is None:
                        raise ProviderError(
                            "--scripted-review is required for scripted Reviewer"
                        )
                    reviewer = ScriptedReviewerProvider.from_file(args.scripted_review)
                else:
                    reviewer = DeepSeekReviewerProvider(
                        model=args.review_model or DeepSeekReviewerProvider.default_model,
                        reasoning_effort=args.review_reasoning_effort,
                    )
                repair_provider_name = args.review_repair_provider or args.provider
                if repair_provider_name == "scripted":
                    if args.review_repair_proposal_sequence is None:
                        raise ProviderError(
                            "--review-repair-proposal-sequence is required for scripted repair"
                        )
                    repair_provider = ScriptedProvider.from_file(
                        args.review_repair_proposal_sequence
                    )
                elif repair_provider_name == "deepseek":
                    repair_provider = DeepSeekChatProvider(
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
                    repair_provider = OpenAIResponsesProvider(
                        model=args.review_repair_model or args.model or "gpt-5.6-terra",
                        reasoning_effort=(
                            args.review_repair_reasoning_effort
                            or args.reasoning_effort
                            or "medium"
                        ),
                    )
                report = IssueToPRRunner(
                    args.artifacts, provider, reviewer, repair_provider
                ).run(task)
            else:
                report = FixRunner(args.artifacts, provider, progress=progress).run(task)
        except ProviderError as exc:
            print(f"fix configuration failed: {exc}")
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
                task = load_review_repair_task(args.task)
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
                task = load_review_task(args.task)
                report = ReviewRunner(args.artifacts, provider).run(task)
        except ProviderError as exc:
            print(f"review configuration failed: {exc}")
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
