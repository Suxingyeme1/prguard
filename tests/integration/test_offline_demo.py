from pathlib import Path

import pytest

from prguard.harness import verify_manifest
from scripts.run_offline_demo import run_demo


@pytest.mark.integration
def test_offline_demo_exercises_repair_and_verifies_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact_directory = run_demo(tmp_path)

    output = capsys.readouterr().out
    assert "PRGuard offline demo: ACCEPTED" in output
    assert "attempt 0: FAILED_VERIFICATION" in output
    assert "attempt 1: PASSED" in output
    assert "max(lower, min(value, upper))" in output
    verify_manifest(artifact_directory / "fix-manifest.json")
