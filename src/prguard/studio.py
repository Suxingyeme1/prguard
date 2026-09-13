"""Loopback browser adapter for frozen Fix and independently reviewed Fix tasks."""

from __future__ import annotations

import hmac
import json
import mimetypes
import os
import platform
import re
import secrets
import stat
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import Field, ValidationError, field_validator, model_validator

from prguard.demo import _demo_proposals, prepare_demo_task
from prguard.fix import FixRunner
from prguard.harness import verify_manifest
from prguard.harness.artifacts import canonical_json, sha256_bytes
from prguard.implementer.providers import (
    DeepSeekChatProvider,
    OpenAIResponsesProvider,
    ScriptedProvider,
)
from prguard.onboarding import prepare_local_issue
from prguard.pipeline import IssueToPRRunner
from prguard.reviewer import DeepSeekReviewerProvider, ScriptedReviewerProvider
from prguard.schemas import (
    FixReport,
    FixTask,
    HarnessReport,
    ImplementerProposal,
    IssueToPRReport,
    IssueToPRTask,
    ReviewerSubmission,
    ReviewRepairOutcome,
    ReviewRoutingMode,
    Verdict,
)
from prguard.schemas.common import StrictModel
from prguard.studio_demo import (
    REVIEW_DEMO_ISSUE,
    prepare_review_demo_task,
    review_demo_initial,
    review_demo_repair,
    review_demo_submission,
)
from prguard.studio_guidance import recovery_code

MAX_BODY = 60_000
MAX_ARTIFACT = 10_000_000
ASSETS = ("index.html", "styles.css", "app.js", "i18n.js", "live.js", "diff.js", "data/cases.js")


class StudioError(ValueError):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class PrepareRequest(StrictModel):
    mode: Literal["demo", "local"] = "demo"
    issue: str = Field(default="", max_length=50_000)
    base_commit: str = Field(default="HEAD", min_length=1, max_length=128)
    workflow: Literal["fix", "reviewed_fix"] = "fix"
    demo_case: Literal["clamp", "review_regression"] = "clamp"

    @field_validator("issue", "base_commit")
    @classmethod
    def no_control_characters(cls, value: str) -> str:
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("unsupported control character")
        return value.strip()

    @field_validator("base_commit")
    @classmethod
    def safe_ref(cls, value: str) -> str:
        if not value or value.startswith("-") or any(char.isspace() for char in value):
            raise ValueError("invalid Git version")
        return value


class ApprovalRequest(StrictModel):
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value: object) -> object:
        if value is not True:
            raise ValueError("explicit confirmation is required")
        return value


class FrozenReviewSpec(StrictModel):
    """Non-secret Reviewer configuration bound into an approved Studio contract."""

    provider: Literal["deepseek", "scripted"]
    model: str = Field(min_length=1, max_length=200)
    reasoning_effort: Literal["high", "max"] | None = None
    max_tool_calls: int = Field(default=12, ge=1, le=100)
    routing: Literal["always"] = "always"
    scripted_submission: ReviewerSubmission | None = None

    @model_validator(mode="after")
    def source_is_complete(self) -> FrozenReviewSpec:
        if self.provider == "scripted" and self.scripted_submission is None:
            raise ValueError("scripted Reviewer requires a frozen submission")
        if self.provider == "deepseek" and self.reasoning_effort is None:
            raise ValueError("DeepSeek Reviewer requires a reasoning effort")
        return self


class FrozenTaskEnvelope(StrictModel):
    """Hash-bound execution description; the browser never supplies this object."""

    version: Literal["studio-approved-task-v2"] = "studio-approved-task-v2"
    workflow: Literal["fix", "reviewed_fix"]
    task: dict[str, object]
    review: FrozenReviewSpec | None = None
    scripted_proposals: list[ImplementerProposal] | None = Field(default=None, max_length=2)
    scripted_repair_proposals: list[ImplementerProposal] | None = Field(default=None, max_length=2)

    @model_validator(mode="after")
    def workflow_has_matching_review_spec(self) -> FrozenTaskEnvelope:
        if (self.workflow == "reviewed_fix") != (self.review is not None):
            raise ValueError("approved workflow and Reviewer specification disagree")
        return self


@dataclass(frozen=True)
class StudioConfig:
    workspace: Path
    repository: Path | None = None
    trust_host: bool = False
    container_image: str | None = None
    policy_file: Path | None = None
    provider: Literal["deepseek", "openai", "scripted"] = "deepseek"
    model: str | None = None
    proposal_sequence: Path | None = None
    enable_independent_review: bool = False
    review_provider: Literal["deepseek", "scripted"] = "deepseek"
    review_model: str | None = None
    review_reasoning_effort: Literal["high", "max"] = "high"
    review_max_tool_calls: int = 12
    review_submission: Path | None = None
    review_repair_proposal_sequence: Path | None = None

    def validate(self) -> None:
        if self.repository is not None:
            if self.trust_host == bool(self.container_image):
                raise StudioError("select --trust-host or --container-image for the repository")
            source = self.repository.expanduser().resolve()
            if self.workspace.expanduser().resolve().is_relative_to(source):
                raise StudioError("Studio workspace must be outside the source repository")
            if self.provider == "scripted" and self.proposal_sequence is None:
                raise StudioError("scripted repository mode requires --proposal-sequence")
        if not 1 <= self.review_max_tool_calls <= 100:
            raise StudioError("Reviewer read budget must be between 1 and 100")
        if self.review_provider not in {"scripted", "deepseek"}:
            raise StudioError("unsupported Reviewer provider")
        if self.review_reasoning_effort not in {"high", "max"}:
            raise StudioError("Reviewer reasoning effort must be high or max")
        if (
            self.enable_independent_review
            and self.repository is not None
            and self.review_provider == "scripted"
            and self.review_submission is None
        ):
            raise StudioError(
                "scripted repository review requires --review-submission"
            )
        if (
            self.enable_independent_review
            and self.repository is not None
            and self.provider == "scripted"
            and self.review_repair_proposal_sequence is None
        ):
            raise StudioError(
                "scripted review repair requires --review-repair-proposal-sequence"
            )


@dataclass
class _Run:
    id: str
    mode: str
    root: Path
    state: str = "preparing"
    created: float = field(default_factory=time.monotonic)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    issue_summary: str = ""
    workflow: str = "fix"
    request: PrepareRequest | None = None
    guidance: dict | None = None
    events: list[dict] = field(default_factory=list)
    preview: dict | None = None
    task: bytes | None = None
    task_hash: str | None = None
    result: dict | None = None
    error: str | None = None
    files: dict[str, tuple[Path, str]] = field(default_factory=dict)


class StudioService:
    """One worker; immutable Task approval; bounded, run-scoped artifact reads."""

    def __init__(self, config: StudioConfig) -> None:
        config.validate()
        self.config = config
        self.root = config.workspace.expanduser().resolve() / f"session-{uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="prguard-studio")
        self.runs: dict[str, _Run] = {}
        self.current_run_id: str | None = None
        self.closed = False
        self.sensitive = [
            value for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY")
            if (value := os.environ.get(name))
        ]
        self.sensitive.append(self.token)

    def close(self) -> None:
        with self.lock:
            self.closed = True
        # Running verification owns its deadlines and must finish writing its artifacts.
        self.worker.shutdown(wait=True)

    def _safe_text(self, text: str) -> str:
        for value in self.sensitive:
            text = text.replace(value, "[redacted]")
        return text

    def session(self) -> dict:
        with self.lock:
            return {
                "mode": "local-adapter",
                "repository": str(self.config.repository) if self.config.repository else None,
                "provider": self.config.provider if self.config.repository else "scripted",
                "boundary": "container" if self.config.container_image else "host",
                "runtime": f"{platform.python_implementation()} {platform.python_version()}",
                "demo_issue": "clamp() must enforce both lower and upper bounds.",
                "demo_cases": [
                    {"id": "clamp", "issue": "clamp() must enforce both lower and upper bounds."},
                    *([{"id": "review_regression", "issue": REVIEW_DEMO_ISSUE}]
                      if self.config.enable_independent_review else []),
                ],
                "review_available": self.config.enable_independent_review,
                "review_policy": (
                    {
                        "routing": "always",
                        "max_tool_calls": self.config.review_max_tool_calls,
                        "provider": (
                            "scripted" if self.config.repository is None
                            else self.config.review_provider
                        ),
                    }
                    if self.config.enable_independent_review
                    else None
                ),
                "latest_run_id": self.current_run_id,
            }

    def _available(self) -> None:
        if self.closed:
            raise StudioError("Studio is shutting down", 503)
        if any(run.state in {"preparing", "running"} for run in self.runs.values()):
            raise StudioError("A task is already running", 409)

    def prepare(self, request: PrepareRequest) -> str:
        with self.lock:
            self._available()
            if len(self.runs) >= 50:
                raise StudioError("Session limit reached; restart Studio for more tasks", 429)
            if request.mode == "local" and (not self.config.repository or not request.issue):
                raise StudioError("Local mode requires a configured repository and an Issue")
            if request.demo_case == "review_regression" and (
                request.mode != "demo" or request.workflow != "reviewed_fix"
            ):
                raise StudioError("The regression demo requires demo mode with independent review")
            if request.workflow == "reviewed_fix" and not self.config.enable_independent_review:
                raise StudioError(
                    "Independent review was not enabled when this Studio session started"
                )
            run_id = uuid4().hex
            run = _Run(
                run_id, request.mode, self.root / run_id,
                issue_summary=request.issue[:160], workflow=request.workflow,
                request=request.model_copy(deep=True),
            )
            self.runs[run_id] = run
            self.current_run_id = run_id
            self.worker.submit(self._prepare, run, request)
            return run_id

    def _event(self, run: _Run, name: str, data: dict) -> None:
        with self.lock:
            if len(run.events) < 500:
                run.events.append({
                    "sequence": len(run.events), "event": name,
                    "elapsed": round(time.monotonic() - run.created, 2), "data": data,
                })

    @staticmethod
    def _review_task(task: FixTask, max_tool_calls: int) -> IssueToPRTask:
        """Allocate fixed stage budgets without silently expanding the approved deadline."""

        if task.task_timeout_seconds < 15:
            raise StudioError(
                "Independent review requires a Task timeout of at least 15 seconds"
            )
        payload = task.model_dump(mode="json")
        payload.update({
            "fix_timeout_seconds": min(600.0, task.task_timeout_seconds * 0.55),
            "review_timeout_seconds": min(300.0, task.task_timeout_seconds * 0.25),
            "review_max_tool_calls": max_tool_calls,
            "review_routing_mode": ReviewRoutingMode.ALWAYS.value,
        })
        return IssueToPRTask.model_validate(payload)

    def _review_spec(self, mode: str, demo_case: str = "clamp") -> FrozenReviewSpec:
        """Freeze provider identity and scripted evidence before explicit approval."""

        if mode == "demo":
            return FrozenReviewSpec(
                provider="scripted",
                model="deterministic-fixture",
                max_tool_calls=self.config.review_max_tool_calls,
                scripted_submission=review_demo_submission() if demo_case == "review_regression"
                else ReviewerSubmission(
                    summary="No evidence-backed defects in the verified clamp patch.",
                    findings=[],
                ),
            )
        if self.config.review_provider == "scripted":
            if self.config.review_submission is None:
                raise StudioError("scripted Reviewer has no frozen submission")
            provider = ScriptedReviewerProvider.from_file(self.config.review_submission)
            return FrozenReviewSpec(
                provider="scripted",
                model=provider.model,
                max_tool_calls=self.config.review_max_tool_calls,
                scripted_submission=provider.submission,
            )
        return FrozenReviewSpec(
            provider="deepseek",
            model=self.config.review_model or DeepSeekReviewerProvider.default_model,
            reasoning_effort=self.config.review_reasoning_effort,
            max_tool_calls=self.config.review_max_tool_calls,
        )

    @staticmethod
    def _scripted_proposals(path: Path | None) -> list[ImplementerProposal]:
        if path is None:
            raise StudioError("scripted execution requires a proposal file")
        if path.stat().st_size > MAX_ARTIFACT:
            raise StudioError("scripted proposal file exceeds size limit")
        values = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, list) or not 1 <= len(values) <= 2:
            raise StudioError("scripted proposal file must contain one or two proposals")
        return [ImplementerProposal.model_validate(value) for value in values]

    def _prepare(self, run: _Run, request: PrepareRequest) -> None:
        try:
            self._event(run, "preparation.started", {})
            policy_source = "demo_fixture"
            policy_warnings: list[str] = []
            regression_demo = request.mode == "demo" and request.demo_case == "review_regression"
            if request.mode == "demo":
                run.root.mkdir(mode=0o700)
                task = (
                    prepare_review_demo_task(run.root) if regression_demo
                    else prepare_demo_task(run.root)
                )
            else:
                preparation = prepare_local_issue(
                    self.config.repository, request.issue, run.root,
                    base_commit=request.base_commit,
                    trust_host=self.config.trust_host,
                    container_image=self.config.container_image,
                    policy_file=self.config.policy_file,
                )
                verify_manifest(run.root / "artifacts" / "preparation-manifest.json")
                task = FixTask.model_validate_json(preparation.task_path.read_bytes())
                policy_source = preparation.policy_source
                policy_warnings = preparation.warnings
            review = None
            execution_task: FixTask | IssueToPRTask = task
            if request.workflow == "reviewed_fix":
                review = self._review_spec(run.mode, request.demo_case)
                execution_task = self._review_task(task, review.max_tool_calls)
            envelope = FrozenTaskEnvelope(
                workflow=request.workflow,
                task=execution_task.model_dump(mode="json"),
                review=review,
                scripted_proposals=(
                    review_demo_initial() if regression_demo
                    else _demo_proposals() if run.mode == "demo"
                    else self._scripted_proposals(self.config.proposal_sequence)
                    if self.config.provider == "scripted" else None
                ),
                scripted_repair_proposals=(
                    review_demo_repair() if regression_demo
                    else [_demo_proposals()[-1]] if run.mode == "demo" and review
                    else self._scripted_proposals(self.config.review_repair_proposal_sequence)
                    if review and self.config.provider == "scripted" else None
                ),
            )
            payload = canonical_json(envelope.model_dump(mode="json"))
            (run.root / "approved-task.json").write_bytes(payload)
            with self.lock:
                run.task = payload
                run.task_hash = sha256_bytes(payload)
                run.issue_summary = execution_task.issue[:160]
                run.preview = {
                    "issue": execution_task.issue,
                    "base_commit": execution_task.base_commit,
                    "repository": str(self.config.repository or execution_task.repository),
                    "commands": [command.argv for command in execution_task.commands],
                    "writable_paths": execution_task.writable_paths,
                    "protected_paths": execution_task.protected_paths,
                    "boundary": "container" if execution_task.container else "host",
                    "provider": "scripted" if run.mode == "demo" else self.config.provider,
                    "task_sha256": run.task_hash,
                    "task_timeout_seconds": execution_task.task_timeout_seconds,
                    "max_repair_attempts": execution_task.max_repair_attempts,
                    "workflow": request.workflow,
                    "demo_case": request.demo_case if run.mode == "demo" else None,
                    "policy_source": policy_source,
                    "policy_warnings": policy_warnings,
                    "review": {
                        "enabled": review is not None,
                        "provider": review.provider if review else None,
                        "routing": review.routing if review else None,
                        "max_tool_calls": review.max_tool_calls if review else None,
                        "review_timeout_seconds": (
                            execution_task.review_timeout_seconds
                            if isinstance(execution_task, IssueToPRTask)
                            else None
                        ),
                    },
                }
                self._event(
                    run,
                    "preparation.completed",
                    {"base_commit": execution_task.base_commit, "workflow": request.workflow},
                )
                run.state = "ready"
        except Exception as exc:
            self._fail(run, exc)

    def approve(self, run_id: str) -> None:
        with self.lock:
            self._available()
            run = self._get(run_id)
            if run.state != "ready":
                raise StudioError("Only a prepared task can be started once", 409)
            if time.monotonic() - run.created > 1800:
                raise StudioError("Task preview expired; prepare a new task", 409)
            run.state = "running"
            self._event(run, "execution.approved", {"workflow": run.workflow})
            self.current_run_id = run_id
            self.worker.submit(self._execute, run)

    def _provider(self, mode: str, proposals: list[ImplementerProposal] | None):
        if mode == "demo" or self.config.provider == "scripted":
            if not proposals:
                raise StudioError("approved scripted proposals are missing")
            return ScriptedProvider(proposals)
        if self.config.provider == "deepseek":
            return DeepSeekChatProvider(
                model=self.config.model or DeepSeekChatProvider.default_model,
            )
        return OpenAIResponsesProvider(model=self.config.model or "gpt-5.6-terra")

    @staticmethod
    def _reviewer(spec: FrozenReviewSpec):
        """Create a fresh Reviewer from the frozen non-secret contract."""

        if spec.provider == "scripted":
            assert spec.scripted_submission is not None
            return ScriptedReviewerProvider(spec.scripted_submission)
        assert spec.reasoning_effort is not None
        return DeepSeekReviewerProvider(
            model=spec.model,
            reasoning_effort=spec.reasoning_effort,
        )

    def _load_approved_task(
        self, run: _Run
    ) -> tuple[FrozenTaskEnvelope, FixTask | IssueToPRTask]:
        if run.task is None:
            raise StudioError("Prepared task is missing; prepare it again", 409)
        on_disk = self._read_regular(run.root / "approved-task.json", run.root)
        if on_disk != run.task:
            raise StudioError("Prepared task changed; prepare it again", 409)
        envelope = FrozenTaskEnvelope.model_validate_json(run.task)
        if envelope.workflow == "fix":
            return envelope, FixTask.model_validate(envelope.task)
        return envelope, IssueToPRTask.model_validate(envelope.task)

    def _delivery_files(
        self, run: _Run, artifact_root: Path, names: tuple[str, ...]
    ) -> dict[str, tuple[Path, str]]:
        files: dict[str, tuple[Path, str]] = {}
        for name in names:
            path = artifact_root / name
            if not path.exists():
                continue
            payload = self._read_regular(path, run.root)
            # Downloaded evidence is either byte-exact or blocked, never silently rewritten.
            text = payload.decode("utf-8")
            if self._safe_text(text) != text:
                continue
            files[name] = (path, sha256_bytes(payload))
        return files

    def _complete(
        self,
        run: _Run,
        result: dict,
        artifact_root: Path,
        names: tuple[str, ...],
        *,
        outcome: str,
        event: str = "delivery.completed",
    ) -> None:
        if outcome != "accepted":
            names = tuple(name for name in names if name != "final.patch")
            result["patch"] = ""
        files = self._delivery_files(run, artifact_root, names)
        result["artifacts"] = [
            {"name": name, "sha256": digest} for name, (_, digest) in files.items()
        ]
        result["manifest_verified"] = True
        self._event(run, event, {"outcome": outcome, "artifact_count": len(files)})
        (run.root / "studio-events.json").write_bytes(canonical_json(run.events))
        with self.lock:
            run.files = files
            run.result = result
            run.state = "completed"

    def _execute(self, run: _Run) -> None:
        try:
            envelope, task = self._load_approved_task(run)
            if envelope.workflow == "fix":
                assert isinstance(task, FixTask)
                report = FixRunner(
                    run.root / "fix-runs", self._provider(run.mode, envelope.scripted_proposals),
                    progress=lambda name, data: self._event(run, name, data),
                ).run(task)
                verify_manifest(report.artifact_directory / "fix-manifest.json")
                self._complete(
                    run,
                    self._result(report),
                    report.artifact_directory,
                    ("fix-report.json", "fix-report.md", "fix-manifest.json", "final.patch"),
                    outcome=report.outcome.value,
                )
                return
            assert isinstance(task, IssueToPRTask)
            assert envelope.review is not None
            report = IssueToPRRunner(
                run.root / "issue-to-pr-runs",
                self._provider(run.mode, envelope.scripted_proposals),
                lambda: self._reviewer(envelope.review),
                lambda: self._provider(run.mode, envelope.scripted_repair_proposals),
                progress=lambda name, data: self._event(run, name, data),
            ).run(task)
            verify_manifest(report.artifact_directory / "issue-to-pr-manifest.json")
            self._complete(
                run,
                self._issue_to_pr_result(report),
                report.artifact_directory,
                (
                    "issue-to-pr-report.json",
                    "issue-to-pr-report.md",
                    "issue-to-pr-manifest.json",
                    "review-routing.json",
                    "final.patch",
                ),
                outcome=report.outcome.value,
                event="studio.delivery.completed",
            )
        except Exception as exc:
            self._fail(run, exc)

    @staticmethod
    def _commands(
        verification: HarnessReport | None, *, reference_probe: bool = False,
    ) -> list[dict]:
        if verification is None:
            return []
        commands = (
            verification.changed_test_base_results if reference_probe else verification.commands
        )
        return [{
            "argv": command.argv, "passed": command.passed,
            "exit_code": command.exit_code, "timed_out": command.timed_out,
            "stdout": command.stdout[-6000:], "stderr": command.stderr[-2000:],
            "duration_seconds": command.duration_seconds,
        } for command in commands]

    @classmethod
    def _attempts(cls, report: FixReport | None) -> list[dict]:
        attempts = []
        for attempt in report.attempts if report else []:
            verification = attempt.verification
            attempts.append({
                "attempt": attempt.attempt + 1,
                "summary": attempt.proposal.proposal.summary if attempt.proposal else None,
                "plan": attempt.proposal.proposal.plan if attempt.proposal else [],
                "error": attempt.error,
                "outcome": verification.outcome.value if verification else "not_run",
                "commands": cls._commands(verification),
            })
        return attempts

    def _patch(self, path: Path | None, root: Path) -> str:
        patch = ""
        if path:
            patch = self._read_regular(
                path, root
            ).decode("utf-8")
        return patch

    def _result(self, report: FixReport) -> dict:
        return {
            "workflow": "fix",
            "outcome": report.outcome.value,
            "attempts": self._attempts(report),
            "base_commit": report.resolved_base_commit,
            "patch": self._patch(report.final_patch, report.artifact_directory),
            "duration_seconds": report.duration_seconds,
            "token_usage": report.token_usage.model_dump(mode="json"),
            "artifact_directory": str(report.artifact_directory),
            "review_status": "not_run",
        }

    def _issue_to_pr_result(self, report: IssueToPRReport) -> dict:
        repair = report.review_repair
        initial = repair.initial_review if repair else None
        submission = initial.review.submission if initial and initial.review else None
        if repair is None:
            review_status = (
                "skipped" if report.review_routing
                and report.review_routing.effective_route.value == "skip"
                else "failed" if report.review_routing else "not_reached"
            )
        elif repair.outcome is ReviewRepairOutcome.ACCEPTED_WITHOUT_REPAIR:
            review_status = "accepted"
        elif repair.outcome is ReviewRepairOutcome.ACCEPTED_AFTER_REPAIR:
            review_status = "accepted_after_repair"
        elif initial and initial.verdict is Verdict.REQUEST_CHANGES:
            review_status = "changes_requested"
        else:
            review_status = "failed"
        routing = report.review_routing
        return {
            "workflow": "reviewed_fix",
            "outcome": report.outcome.value,
            "attempts": self._attempts(report.fix),
            "base_commit": report.resolved_base_commit,
            "patch": self._patch(report.final_patch, report.artifact_directory),
            "duration_seconds": report.duration_seconds,
            "token_usage": report.token_usage.model_dump(mode="json"),
            "artifact_directory": str(report.artifact_directory),
            "review_status": review_status,
            "error": report.error,
            "review": {
                "summary": submission.summary if submission else None,
                "verdict": initial.verdict.value if initial else None,
                "findings": [
                    finding.model_dump(mode="json") for finding in submission.findings
                ] if submission else [],
                "verification": {
                    "outcome": initial.verification.outcome.value,
                    "commands": self._commands(initial.verification),
                } if initial and initial.verification else None,
                "error": initial.error if initial else report.error,
                "routing": {
                    "mode": routing.mode.value,
                    "recommended_route": routing.recommended_route.value,
                    "effective_route": routing.effective_route.value,
                    "score": routing.score,
                    "threshold": routing.threshold,
                    "changed_files": routing.changed_files,
                    "factors": [
                        {
                            "code": factor.code,
                            "weight": factor.weight,
                            "summary": factor.summary,
                        }
                        for factor in routing.factors
                    ],
                } if routing else None,
                "repair": {
                    "outcome": repair.outcome.value,
                    "summary": (
                        repair.repair_proposal.proposal.summary
                        if repair.repair_proposal
                        else None
                    ),
                    "verification_outcome": (
                        repair.final_verification.outcome.value
                        if repair.final_verification
                        else None
                    ),
                    "error": repair.error,
                    "commands": self._commands(repair.final_verification),
                    "reference_probe": {
                        "reference": repair.final_verification.changed_test_reference,
                        "patch_sha256": repair.final_verification.changed_test_reference_sha256,
                        "commands": self._commands(repair.final_verification, reference_probe=True),
                    } if repair.final_verification
                    and repair.final_verification.changed_test_base_results else None,
                } if repair else None,
            },
        }

    def _fail(self, run: _Run, exc: Exception) -> None:
        with self.lock:
            run.error = self._safe_text(f"{type(exc).__name__}: {exc}")[:1500]
            run.guidance = {
                "code": recovery_code(exc),
                "stage": "preparation" if run.task is None else "execution",
            }
            run.state = "error"
            self._event(run, "adapter.failed", {"error": run.error})

    def _get(self, run_id: str) -> _Run:
        if run_id not in self.runs:
            raise StudioError("Run not found", 404)
        return self.runs[run_id]

    def snapshot(self, run_id: str) -> dict:
        with self.lock:
            run = self._get(run_id)
            payload = json.dumps({
                "id": run.id, "mode": run.mode, "state": run.state,
                "preview": run.preview, "events": run.events,
                "result": run.result, "error": run.error,
                "guidance": run.guidance,
                "request": run.request.model_dump(mode="json") if run.request else None,
            }, ensure_ascii=False)
            return json.loads(self._safe_text(payload))

    def run_summaries(self) -> dict:
        """Read only records owned by the current authenticated process."""
        with self.lock:
            runs = [{
                "id": run.id,
                "mode": run.mode,
                "workflow": run.workflow,
                "state": run.state,
                "created_at": run.created_at,
                "issue_summary": run.issue_summary,
                "base_commit": run.preview["base_commit"] if run.preview else None,
                "outcome": run.result["outcome"] if run.result else None,
                "artifact_count": len(run.files),
                "manifest_verified": bool(run.result and run.result.get("manifest_verified")),
            } for run in reversed(list(self.runs.values()))]
            return json.loads(self._safe_text(json.dumps({
                "current_run_id": self.current_run_id,
                "active_run_id": next((
                    run.id for run in self.runs.values()
                    if run.state in {"preparing", "running"}
                ), None),
                "runs": runs,
            }, ensure_ascii=False)))

    @staticmethod
    def _read_regular(path: Path, root: Path) -> bytes:
        if not path.resolve().is_relative_to(root.resolve()):
            raise StudioError("Artifact is outside this run", 403)
        relative = path.relative_to(root)
        if any((root / Path(*relative.parts[:index])).is_symlink()
               for index in range(1, len(relative.parts) + 1)):
            raise StudioError("Symlink artifacts are unavailable", 403)
        descriptor = os.open(
            path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
        )
        with os.fdopen(descriptor, "rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARTIFACT:
                raise StudioError("Artifact must be a bounded regular file", 403)
            payload = source.read(MAX_ARTIFACT + 1)
            if len(payload) > MAX_ARTIFACT:
                raise StudioError("Artifact exceeds download limit", 403)
            return payload

    def artifact(self, run_id: str, name: str) -> bytes:
        with self.lock:
            run = self._get(run_id)
            if name not in run.files:
                raise StudioError("Artifact is not available for download", 404)
            path, digest = run.files[name]
            payload = self._read_regular(path, run.root)
            if sha256_bytes(payload) != digest:
                raise StudioError("Artifact integrity check failed", 409)
            return payload


def load_assets() -> dict[str, bytes]:
    source = Path(__file__).resolve().parents[2] / "demo-ui" / "dist"
    if not (source / "index.html").is_file():
        source = Path(__file__).parent / "studio_assets"
    return {"/" if name == "index.html" else f"/{name}": (source / name).read_bytes()
            for name in ASSETS}


def create_server(service: StudioService, port: int = 0) -> ThreadingHTTPServer:
    assets = load_assets()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format, *args) -> None:
            pass  # Do not persist authentication or request bodies in access logs.

        def _check(self) -> None:
            self.connection.settimeout(10)
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get_all("Host") != [expected]:
                raise StudioError("Unexpected Host", 403)
            origin = self.headers.get_all("Origin")
            if origin is not None and origin != [f"http://{expected}"]:
                raise StudioError("Cross-origin requests are not allowed", 403)
            if self.path.startswith("/api/"):
                provided = self.headers.get_all("Authorization")
                if provided is None or len(provided) != 1 or not hmac.compare_digest(
                    provided[0].encode(), f"Bearer {service.token}".encode()
                ):
                    raise StudioError("Open the local Studio URL printed in your terminal", 401)

        def _send(self, status: int, payload: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
            ))
            self.end_headers()
            self.wfile.write(payload)

        def _json(self, status: int, value: dict) -> None:
            self._send(status, canonical_json(value), "application/json; charset=utf-8")

        def _dispatch(self, post: bool) -> None:
            try:
                self._check()
                if post:
                    self._post()
                elif self.path in assets:
                    content_type = mimetypes.guess_type(self.path)[0] or "text/html"
                    self._send(200, assets[self.path], f"{content_type}; charset=utf-8")
                elif self.path == "/api/session":
                    self._json(200, service.session())
                elif self.path == "/api/runs":
                    self._json(200, service.run_summaries())
                elif match := re.fullmatch(r"/api/runs/([0-9a-f]{32})", self.path):
                    self._json(200, service.snapshot(match[1]))
                elif match := re.fullmatch(
                    r"/api/runs/([0-9a-f]{32})/artifacts/([a-z.-]+)", self.path
                ):
                    self._send(200, service.artifact(match[1], match[2]),
                               "application/octet-stream")
                else:
                    raise StudioError("Not found", 404)
            except StudioError as exc:
                self._json(exc.status, {"error": str(exc)})
            except (ValidationError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
                self._json(400, {"error": "Invalid request; check Issue and version fields"})
            except FileNotFoundError:
                self._json(404, {"error": "Artifact is no longer available"})
            except (OSError, TimeoutError):
                self.close_connection = True

        def _post(self) -> None:
            if self.headers.get_content_type() != "application/json":
                raise StudioError("JSON request required", 415)
            if self.headers.get("Transfer-Encoding"):
                raise StudioError("Transfer encoding is not supported")
            lengths = self.headers.get_all("Content-Length") or []
            if len(lengths) != 1 or not lengths[0].isdecimal():
                raise StudioError("Content-Length is required", 411)
            length = int(lengths[0])
            if not 0 < length <= MAX_BODY:
                raise StudioError("Request exceeds size limit", 413)
            payload = self.rfile.read(length)
            if len(payload) != length:
                raise StudioError("Incomplete request")
            if self.path == "/api/prepare":
                request = PrepareRequest.model_validate_json(payload)
                self._json(202, {"id": service.prepare(request)})
            elif match := re.fullmatch(r"/api/runs/([0-9a-f]{32})/start", self.path):
                ApprovalRequest.model_validate_json(payload)
                service.approve(match[1])
                self._json(202, {"id": match[1]})
            else:
                raise StudioError("Not found", 404)

        def do_GET(self) -> None:
            self._dispatch(False)

        def do_POST(self) -> None:
            self._dispatch(True)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def run_studio(config: StudioConfig, *, port: int = 4318, open_browser: bool = True) -> None:
    service = StudioService(config)
    try:
        server = create_server(service, port)
        url = f"http://127.0.0.1:{server.server_port}/#token={service.token}"
        print(f"PRGuard Studio: {url}", flush=True)
        print("Ctrl+C closes Studio after any active task finishes its verification.", flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Waiting for any active verification to finish…", flush=True)
        finally:
            server.server_close()
    finally:
        service.close()
