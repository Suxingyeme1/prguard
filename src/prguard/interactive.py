"""Dependency-free guided terminal entry for a local Issue-to-Patch run."""

from __future__ import annotations

import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from prguard.fix import FixRunner
from prguard.implementer.providers import ImplementerProvider
from prguard.onboarding import inspect_project_policy, prepare_local_issue
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
        self.line(f"  Repository   {report.repository}")
        self.line(f"  Base         {report.requested_base_commit} → {report.base_commit[:12]}")
        summary = " ".join(issue.split())
        self.line(f"  Issue        {summary[:110]}{'…' if len(summary) > 110 else ''}")
        self.line()
        self.line(self._paint("  DETERMINISTIC POLICY", "1;36"))
        source = report.policy_source or "unavailable"
        self.line(f"  Source       {source}")
        for command in report.commands:
            self.line(f"  Verify       $ {' '.join(command.argv)}")
        self.line(f"  Writable     {', '.join(report.writable_paths)}")
        protected = ", ".join(report.protected_paths[:5])
        if len(report.protected_paths) > 5:
            protected += f", … (+{len(report.protected_paths) - 5})"
        self.line(f"  Protected    {protected}")
        for warning in report.warnings:
            self.line(self._paint(f"  ! {warning}", "33"))
        self.line()

    def boundary(self, *, host: bool, container_image: str | None) -> None:
        self.line(self._paint("  EXECUTION BOUNDARY", "1;36"))
        if host:
            self.line(self._paint("  HOST · repository tests run with the current user", "1;33"))
        else:
            self.line(f"  CONTAINER · {container_image}")
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
        self.line(f"  {self._paint(icon, color)} {label:<14} {detail}")

    def result(self, report: FixReport) -> None:
        self.line()
        self.line(self._paint("  DELIVERY", "1;36"))
        accepted = report.outcome is FixOutcome.ACCEPTED
        status = self._paint(report.outcome.value.upper(), "1;32" if accepted else "1;31")
        self.line(f"  Outcome      {status}")
        self.line(f"  Attempts     {len(report.attempts)}")
        self.line(f"  Base         {(report.resolved_base_commit or '')[:12]}")
        if report.final_patch is not None:
            self.line(f"  Patch        {report.final_patch}")
        self.line(f"  Artifacts    {report.artifact_directory}")
        self.line(f"  Manifest     {report.artifact_directory / 'fix-manifest.json'}")
        self.line(self._paint("━" * self.width, "36"))


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
        inspection = inspect_project_policy(
            repository,
            issue=issue,
            base_commit=base_commit,
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
    )
    selected_provider = provider() if callable(provider) else provider
    report = FixRunner(
        workspace / "fix-runs",
        selected_provider,
        progress=terminal.progress,
    ).run(FixTask.model_validate_json(preparation.task_path.read_text(encoding="utf-8")))
    terminal.result(report)
    return report
