from pathlib import Path

from prguard.cli import main
from prguard.demo import run_terminal_demo
from prguard.harness import verify_manifest
from prguard.schemas import FixOutcome, RunOutcome


def test_terminal_demo_visualizes_failed_attempt_repair_and_delivery(
    tmp_path: Path, capsys
) -> None:
    report = run_terminal_demo(tmp_path, color=False)

    output = capsys.readouterr().out
    assert "PRGuard · Verified Coding Agent" in output
    assert "FAILED_VERIFICATION" in output
    assert "Failed-test evidence returned for one repair" in output
    assert "FINAL PATCH" in output
    assert "+    return max(lower, min(value, upper))" in output
    assert "ACCEPTED" in output
    assert report.outcome is FixOutcome.ACCEPTED
    assert len(report.attempts) == 2
    assert report.attempts[0].verification is not None
    assert report.attempts[0].verification.outcome is RunOutcome.FAILED_VERIFICATION
    assert report.attempts[1].verification is not None
    assert report.attempts[1].verification.outcome is RunOutcome.PASSED
    verify_manifest(report.artifact_directory / "fix-manifest.json")


def test_demo_cli_runs_without_color_or_model_key(tmp_path: Path, capsys) -> None:
    exit_code = main(["demo", "--output", str(tmp_path), "--no-color"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Offline guided demo · no API key" in captured.out
    assert "[PASS]" in captured.out
    assert "\033[" not in captured.out
