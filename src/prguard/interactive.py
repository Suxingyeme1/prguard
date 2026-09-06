"""Dependency-free guided terminal entry for a local Issue-to-Patch run."""

from __future__ import annotations

import shlex
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from prguard.fix import FixRunner
from prguard.implementer.providers import ImplementerProvider
from prguard.onboarding import (
    inspect_project_policy,
    load_operator_project_config,
    prepare_local_issue,
)
from prguard.onboarding.errors import OnboardingError, ProjectDiscoveryError
from prguard.schemas import FixOutcome, FixReport, FixTask, ProjectPolicyInspection

InputFunction = Callable[[str], str]
ProviderSource = ImplementerProvider | Callable[[], ImplementerProvider]


class InteractiveTerminal:
    """Small line-oriented UI that stays usable over SSH and inside plain terminals."""

    def __init__(self, *, stream=None, color: bool | None = None) -> None:
        self.stream = stream or sys.stdout
        self.color = self.stream.isatty() if color is None else color
        self.width = min(92, max(68, shutil.get_terminal_size((92, 24)).columns))

    def _paint(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.color else text

    @staticmethod
    def _terminal_safe(text: str) -> str:
        """Render untrusted repository/model text without terminal control sequences."""

        return "".join(
            character
            if character == "\t" or (ord(character) >= 32 and not 127 <= ord(character) <= 159)
            else "�"
            for character in text
        )

    def line(self, text: str = "") -> None:
        print(text, file=self.stream, flush=True)

    def header(self) -> None:
        self.line(self._paint("━" * self.width, "36"))
        self.line(self._paint("  PRGuard · Repository Coding Session", "1;36"))
        self.line(self._paint("━" * self.width, "36"))
        self.line("  Describe the change, inspect the frozen policy, then approve execution.")
        self.line()

    def section(self, label: str) -> None:
        self.line(self._paint(f"  {label}", "1;36"))

    def policy(self, report: ProjectPolicyInspection, issue: str) -> None:
        self.line(self._paint("  TASK", "1;36"))
        self.line(f"  Repository   {self._terminal_safe(str(report.repository))}")
        self.line(f"  Base         {report.requested_base_commit} → {report.base_commit[:12]}")
        summary = self._terminal_safe(" ".join(issue.split()))
        self.line(f"  Issue        {summary[:110]}{'…' if len(summary) > 110 else ''}")
        self.line()
        self.line(self._paint("  DETERMINISTIC POLICY", "1;36"))
        source = report.policy_source or "unavailable"
        self.line(f"  Source       {self._terminal_safe(source)}")
        for command in report.commands:
            command_text = self._terminal_safe(" ".join(command.argv))
            self.line(f"  Verify       $ {command_text}")
        writable = self._terminal_safe(", ".join(report.writable_paths))
        self.line(f"  Writable     {writable}")
        protected = self._terminal_safe(", ".join(report.protected_paths[:5]))
        if len(report.protected_paths) > 5:
            protected += f", … (+{len(report.protected_paths) - 5})"
        self.line(f"  Protected    {protected}")
        for warning in report.warnings:
            self.line(self._paint(f"  ! {self._terminal_safe(warning)}", "33"))
        self.line()

    def boundary(self, *, host: bool, container_image: str | None) -> None:
        self.line(self._paint("  EXECUTION BOUNDARY", "1;36"))
        if host:
            self.line(self._paint("  HOST · repository tests run with the current user", "1;33"))
        else:
            self.line(f"  CONTAINER · {self._terminal_safe(container_image or '')}")
        self.line()

    def progress(self, event: str, data: dict[str, object]) -> None:
        labels = {
            "run.started": ("○", "Run", "created"),
            "preflight.started": ("○", "Git", "validating frozen commit"),
            "readiness.started": ("○", "Readiness", "checking Base"),
            "readiness.completed": (
                "✓",
                "Readiness",
                str(data.get("outcome", "completed")),
            ),
            "preflight.completed": (
                "✓",
                "Worktree",
                str(data.get("resolved_base_commit", ""))[:12],
            ),
            "attempt.started": (
                "◆",
                "Repair" if data.get("repair") else "Implementer",
                f"attempt {int(data.get('attempt', 0)) + 1}",
            ),
            "proposal.completed": (
                "✓",
                "Candidate",
                f"{data.get('tool_calls', 0)} tool calls · {data.get('patch_bytes', 0)} bytes",
            ),
            "verification.started": ("○", "Harness", "running fixed commands"),
            "verification.completed": (
                "✓" if data.get("outcome") == "passed" else "✗",
                "Verification",
                str(data.get("outcome", "unknown")),
            ),
            "repair.requested": ("↳", "Feedback", "one bounded repair requested"),
            "attempt.failed": ("✗", "Implementer", "attempt failed"),
        }
        item = labels.get(event)
        if item is None:
            return
        icon, label, detail = item
        color = "32" if icon == "✓" else "31" if icon == "✗" else "36"
        self.line(
            f"  {self._paint(icon, color)} {label:<14} {self._terminal_safe(detail)}"
        )

    def result(self, report: FixReport, *, repository: Path) -> None:
        self.line()
        self.section("VERIFICATION")
        for attempt in report.attempts:
            verification = attempt.verification
            if verification is None:
                detail = self._terminal_safe(attempt.error or "verification was not reached")
                self.line(self._paint(f"  ✗ Attempt {attempt.attempt + 1}  {detail}", "31"))
                continue
            passed = verification.outcome.value == "passed"
            marker = self._paint("✓" if passed else "✗", "32" if passed else "31")
            self.line(f"  {marker} Attempt {attempt.attempt + 1}  {verification.outcome.value}")
            for command in verification.commands:
                summary = self._pytest_summary(command.stdout)
                runtime = (
                    f" · {command.runtime.implementation} {command.runtime.version}"
                    if command.runtime is not None
                    else ""
                )
                result = self._terminal_safe(summary or f"exit {command.exit_code}")
                command_text = self._terminal_safe(" ".join(command.argv))
                self.line(f"     $ {command_text} → {result}{runtime}")
                if not command.passed:
                    failure = self._terminal_safe(self._failure_line(command.stdout))
                    self.line(self._paint(f"       {failure}", "31"))

        if report.final_patch is not None:
            self.line()
            self.section("PATCH PREVIEW")
            patch_lines = report.final_patch.read_text(encoding="utf-8").splitlines()
            limit = 160
            for raw_line in patch_lines[:limit]:
                line = self._terminal_safe(raw_line)
                if line.startswith("+") and not line.startswith("+++"):
                    rendered = self._paint(line, "32")
                elif line.startswith("-") and not line.startswith("---"):
                    rendered = self._paint(line, "31")
                elif line.startswith("@@"):
                    rendered = self._paint(line, "36")
                else:
                    rendered = line
                self.line(f"  {rendered}")
            if len(patch_lines) > limit:
                hidden = len(patch_lines) - limit
                self.line(self._paint(f"  … {hidden} more lines in final.patch", "33"))

        self.line()
        self.section("DELIVERY")
        accepted = report.outcome is FixOutcome.ACCEPTED
        status = self._paint(report.outcome.value.upper(), "1;32" if accepted else "1;31")
        self.line(f"  Outcome      {status}")
        self.line(f"  Attempts     {len(report.attempts)}")
        self.line(f"  Base         {(report.resolved_base_commit or '')[:12]}")
        self.line(f"  Duration     {report.duration_seconds:.1f}s")
        total_tokens = report.token_usage.input_tokens + report.token_usage.output_tokens
        if total_tokens:
            self.line(f"  Tokens       {total_tokens:,}")
        if report.final_patch is not None:
            self.line(f"  Patch        {self._terminal_safe(str(report.final_patch))}")
        artifacts = self._terminal_safe(str(report.artifact_directory))
        manifest = self._terminal_safe(str(report.artifact_directory / "fix-manifest.json"))
        self.line(f"  Artifacts    {artifacts}")
        self.line(f"  Manifest     {manifest}")
        if accepted and report.final_patch is not None:
            repository_arg = shlex.quote(str(repository))
            patch = shlex.quote(str(report.final_patch))
            self.line()
            self.section("NEXT")
            self.line("  Review the Patch and Manifest, then validate it against your checkout:")
            command = self._terminal_safe(f"git -C {repository_arg} apply --check {patch}")
            self.line(f"  {command}")
        self.line(self._paint("━" * self.width, "36"))

    @staticmethod
    def _pytest_summary(stdout: str) -> str:
        for line in reversed(stdout.splitlines()):
            if " passed" in line or " failed" in line:
                return line.strip().split(" in ", 1)[0]
        return ""

    @staticmethod
    def _failure_line(stdout: str) -> str:
        for line in stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("E ") or stripped.startswith("FAILED "):
                return stripped[:160]
        return "See the verification Artifact for complete failure evidence"


def _read_issue(input_fn: InputFunction, terminal: InteractiveTerminal) -> str:
    terminal.line("  Enter the Issue in natural language.")
    terminal.line("  Finish with a line containing only a single period (.).")
    lines: list[str] = []
    while True:
        value = input_fn("  > ")
        if value.strip() == ".":
            break
        lines.append(value)
    issue = "\n".join(lines).strip()
    if not issue:
        raise OnboardingError("interactive Issue text must not be empty")
    return issue


def _read_boundary(
    input_fn: InputFunction,
    terminal: InteractiveTerminal,
) -> tuple[bool, str | None]:
    terminal.line("  Choose how repository tests execute:")
    terminal.line("  [h] Host      for code you trust")
    terminal.line("  [c] Container for external or higher-risk code")
    choice = input_fn("  Boundary [h/c]: ").strip().casefold()
    if choice == "h":
        return True, None
    if choice == "c":
        image = input_fn("  Immutable container image (name@sha256:…): ").strip()
        if not image:
            raise OnboardingError("container execution requires an immutable image digest")
        return False, image
    raise OnboardingError("execution boundary must be 'h' or 'c'")


def run_interactive_fix(
    *,
    repository: Path,
    provider: ProviderSource,
    issue: str | None = None,
    base_commit: str = "HEAD",
    workspace: Path | None = None,
    trust_host: bool = False,
    container_image: str | None = None,
    assume_yes: bool = False,
    input_fn: InputFunction | None = None,
    stream=None,
    color: bool | None = None,
    policy_file: Path | None = None,
) -> FixReport:
    """Preview and explicitly approve one local Issue-to-Patch session."""

    input_fn = input_fn or input
    terminal = InteractiveTerminal(stream=stream, color=color)
    terminal.header()
    repository = repository.expanduser().resolve()
    if issue is None:
        issue = _read_issue(input_fn, terminal)
    issue = issue.strip()
    if not issue:
        raise OnboardingError("interactive Issue text must not be empty")

    try:
        operator_config = (
            load_operator_project_config(policy_file) if policy_file is not None else None
        )
        inspection = inspect_project_policy(
            repository,
            issue=issue,
            base_commit=base_commit,
            operator_config=operator_config,
            operator_config_path=policy_file,
        )
    except ProjectDiscoveryError as exc:
        raise OnboardingError(f"policy inspection failed: {exc}") from exc
    terminal.policy(inspection, issue)
    if inspection.status != "ready":
        reasons = "; ".join(inspection.blocking_reasons)
        raise OnboardingError(f"repository needs a reviewed .prguard.toml: {reasons}")

    if trust_host and container_image is not None:
        raise OnboardingError("choose only one execution boundary")
    if not trust_host and container_image is None:
        if assume_yes:
            raise OnboardingError(
                "--yes still requires an explicit --trust-host or --container-image boundary"
            )
        trust_host, container_image = _read_boundary(input_fn, terminal)
    terminal.boundary(host=trust_host, container_image=container_image)

    if not assume_yes:
        approval = input_fn("  Type 'run' to start, or anything else to cancel: ")
        if approval.strip().casefold() != "run":
            raise OnboardingError("interactive run cancelled before repository execution")

    if workspace is None:
        workspace = (
            Path(tempfile.gettempdir())
            / "prguard-sessions"
            / f"{repository.name}-{uuid4().hex[:10]}"
        )
    workspace = workspace.expanduser().resolve()
    terminal.line()
    terminal.section("PIPELINE")
    preparation = prepare_local_issue(
        repository,
        issue,
        workspace,
        base_commit=inspection.base_commit,
        trust_host=trust_host,
        container_image=container_image,
        policy_file=policy_file,
    )
    selected_provider = provider() if callable(provider) else provider
    report = FixRunner(
        workspace / "fix-runs",
        selected_provider,
        progress=terminal.progress,
    ).run(FixTask.model_validate_json(preparation.task_path.read_text(encoding="utf-8")))
    terminal.result(report, repository=repository)
    return report
