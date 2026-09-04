"""A visual, key-free terminal walkthrough of PRGuard's real Fix pipeline."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from prguard.fix import FixRunner
from prguard.harness import verify_manifest
from prguard.implementer.providers import ScriptedProvider
from prguard.schemas import (
    CommandSpec,
    FixOutcome,
    FixReport,
    FixTask,
    ImplementerProposal,
    ReplaceTextEdit,
)

_ISSUE = "clamp() must enforce both lower and upper bounds while preserving values in range."
_BASE_SOURCE = (
    "def clamp(value: int, lower: int, upper: int) -> int:\n"
    "    return min(value, upper)\n"
)
_TEST_SOURCE = """from clamp import clamp


def test_below_lower_bound() -> None:
    assert clamp(-5, 0, 10) == 0


def test_above_upper_bound() -> None:
    assert clamp(15, 0, 10) == 10


def test_inside_range() -> None:
    assert clamp(5, 0, 10) == 5
"""


class TerminalDemoView:
    """Small dependency-free terminal renderer; plain output remains testable and pipe-safe."""

    def __init__(self, *, stream=None, color: bool | None = None) -> None:
        self.stream = stream or sys.stdout
        self.color = self.stream.isatty() if color is None else color
        self.width = min(88, max(64, shutil.get_terminal_size((88, 24)).columns))

    def _paint(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.color else text

    def _line(self, text: str = "") -> None:
        print(text, file=self.stream, flush=True)

    def header(self, repository: Path) -> None:
        self._line(self._paint("━" * self.width, "36"))
        self._line(self._paint("  PRGuard · Verified Coding Agent", "1;36"))
        self._line(self._paint("━" * self.width, "36"))
        self._line(f"  {self._paint('Issue', '1')}       {_ISSUE}")
        self._line(f"  {self._paint('Repository', '1')}  {repository}")
        self._line(f"  {self._paint('Mode', '1')}        Offline guided demo · no API key")
        self._line()

    def event(self, event: str, data: dict[str, object]) -> None:
        if event == "run.started":
            self._line(self._paint("  PIPELINE", "1;36"))
            self._step("○", "Task", "Natural-language Issue accepted")
        elif event == "preflight.started":
            self._step("○", "Git", "Resolving HEAD and checking clean repository")
        elif event == "readiness.completed":
            self._step("✓", "Readiness", "pytest collection is available", "32")
        elif event == "preflight.completed":
            commit = str(data.get("resolved_base_commit", ""))[:12]
            self._step("✓", "Worktree", f"Frozen at {commit}", "32")
        elif event == "attempt.started":
            attempt = int(data.get("attempt", 0))
            label = "Repair" if data.get("repair") else "Implementer"
            self._step("◆", label, f"Attempt {attempt + 1}: inspecting code")
        elif event == "proposal.completed":
            calls = data.get("tool_calls", 0)
            size = data.get("patch_bytes", 0)
            self._step("✓", "Candidate", f"{calls} reads · {size} byte Git Patch", "32")
        elif event == "verification.started":
            self._step("○", "Harness", "Running pytest with fixed argv")
        elif event == "verification.completed":
            outcome = str(data.get("outcome", "unknown"))
            if outcome == "passed":
                self._step("✓", "Verification", "PASSED", "1;32")
            else:
                self._step("✗", "Verification", outcome.upper(), "1;31")
        elif event == "repair.requested":
            self._step("↳", "Feedback", "Failed-test evidence returned for one repair", "33")
        elif event == "run.completed":
            outcome = str(data.get("outcome", "unknown")).upper()
            code = "1;32" if outcome == "ACCEPTED" else "1;31"
            self._step("●", "Final", outcome, code)

    def _step(self, icon: str, label: str, detail: str, code: str = "36") -> None:
        marker = self._paint(icon, code)
        self._line(f"  {marker} {label:<13} {detail}")

    def result(self, report: FixReport) -> None:
        self._line()
        self._line(self._paint("  ATTEMPTS", "1;36"))
        for attempt in report.attempts:
            verification = attempt.verification
            outcome = verification.outcome.value if verification else "not_run"
            passed = outcome == "passed"
            marker = self._paint("PASS" if passed else "FAIL", "1;32" if passed else "1;31")
            summary = attempt.proposal.proposal.summary if attempt.proposal else attempt.error
            self._line(f"  {attempt.attempt + 1}. [{marker}] {summary}")
            if verification:
                for command in verification.commands:
                    tests = self._pytest_summary(command.stdout)
                    suffix = f" · {tests}" if tests else ""
                    self._line(
                        f"     $ {' '.join(command.argv)} → exit {command.exit_code}{suffix}"
                    )
                    if not command.passed:
                        failure = self._failure_line(command.stdout)
                        if failure:
                            self._line(self._paint(f"       {failure}", "31"))

        self._line()
        self._line(self._paint("  FINAL PATCH", "1;36"))
        if report.final_patch:
            for line in report.final_patch.read_text(encoding="utf-8").splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    self._line(self._paint(f"  {line}", "32"))
                elif line.startswith("-") and not line.startswith("---"):
                    self._line(self._paint(f"  {line}", "31"))
                else:
                    self._line(f"  {line}")
        self._line()
        self._line(self._paint("  DELIVERY", "1;36"))
        self._line(f"  Outcome    {self._paint(report.outcome.value.upper(), '1;32')}")
        self._line(f"  Attempts   {len(report.attempts)}")
        self._line(f"  Artifact   {report.artifact_directory}")
        self._line(f"  Manifest   {report.artifact_directory / 'fix-manifest.json'}")
        self._line(self._paint("━" * self.width, "36"))

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
            if stripped.startswith("E ") and "assert" in stripped:
                return stripped
        return "See verification Artifact for failure details"


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", os.fspath(repository), *args],
        check=True,
        shell=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C"},
    )
    return completed.stdout.strip()


def _create_demo_repository(root: Path) -> tuple[Path, str]:
    repository = root / "repository"
    (repository / "tests").mkdir(parents=True)
    (repository / "clamp.py").write_text(_BASE_SOURCE, encoding="utf-8")
    (repository / "tests" / "test_clamp.py").write_text(_TEST_SOURCE, encoding="utf-8")
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.name", "PRGuard Demo")
    _git(repository, "config", "user.email", "demo@prguard.invalid")
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "demo base")
    return repository, _git(repository, "rev-parse", "HEAD")


def _demo_proposals() -> list[ImplementerProposal]:
    return [
        ImplementerProposal(
            plan=["Inspect clamp and its tests", "Enforce the missing lower bound"],
            summary="Enforce the lower bound, but accidentally lose the upper bound.",
            edits=[
                ReplaceTextEdit(
                    operation="replace_text",
                    path="clamp.py",
                    old_text="    return min(value, upper)\n",
                    new_text="    return max(value, lower)\n",
                )
            ],
            tests_changed=False,
        ),
        ImplementerProposal(
            plan=["Read failed upper-bound evidence", "Compose both bounds"],
            summary="Use pytest evidence to enforce both lower and upper bounds.",
            edits=[
                ReplaceTextEdit(
                    operation="replace_text",
                    path="clamp.py",
                    old_text="    return min(value, upper)\n",
                    new_text="    return max(lower, min(value, upper))\n",
                )
            ],
            tests_changed=False,
        ),
    ]


def run_terminal_demo(
    output_root: Path,
    *,
    stream=None,
    color: bool | None = None,
) -> FixReport:
    """Run the real FixRunner on a generated repository and render the result."""

    demo_root = output_root.expanduser().resolve() / f"run-{uuid4().hex[:8]}"
    demo_root.mkdir(parents=True, exist_ok=False)
    repository, commit = _create_demo_repository(demo_root)
    view = TerminalDemoView(stream=stream, color=color)
    view.header(repository)
    commands = [CommandSpec(argv=["pytest", "-q", "tests/test_clamp.py"], kind="pytest")]
    task = FixTask(
        case_id="terminal-demo-clamp",
        repository=repository,
        base_commit=commit,
        issue=_ISSUE,
        commands=commands,
        allowed_commands=[command.argv for command in commands],
        writable_paths=["*.py", "tests/**"],
        protected_paths=[".git/**", ".github/**", ".env*", "**/*.key"],
        command_timeout_seconds=20,
        task_timeout_seconds=90,
        max_repair_attempts=1,
    )
    report = FixRunner(
        demo_root / "artifacts",
        ScriptedProvider(_demo_proposals()),
        progress=view.event,
    ).run(task)
    verify_manifest(report.artifact_directory / "fix-manifest.json")
    view.result(report)
    if report.outcome is not FixOutcome.ACCEPTED:
        raise RuntimeError(f"terminal demo failed: {report.outcome}")
    return report
