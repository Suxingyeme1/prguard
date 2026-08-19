from pathlib import Path

import pytest

from prguard.harness import VerificationHarness, load_replay_task, verify_manifest
from prguard.harness.errors import ArtifactIntegrityError
from prguard.schemas import RunOutcome


@pytest.mark.integration
def test_manifest_detects_artifact_tampering(task_for_case, tmp_path: Path) -> None:
    report = VerificationHarness(tmp_path / "artifacts").run(task_for_case("correct-patch"))
    run_directory = Path(report.artifact_directory)
    verify_manifest(run_directory / "manifest.json")
    (run_directory / "report.md").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ArtifactIntegrityError, match="hash mismatch"):
        verify_manifest(run_directory / "manifest.json")


@pytest.mark.integration
def test_manifest_detects_unlisted_file(task_for_case, tmp_path: Path) -> None:
    report = VerificationHarness(tmp_path / "artifacts").run(task_for_case("correct-patch"))
    run_directory = Path(report.artifact_directory)
    (run_directory / "unlisted.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(ArtifactIntegrityError, match="unlisted"):
        verify_manifest(run_directory / "manifest.json")


@pytest.mark.integration
def test_replay_uses_manifest_archived_patch(task_for_case, tmp_path: Path) -> None:
    original_task = task_for_case("correct-patch")
    first = VerificationHarness(tmp_path / "first").run(original_task)
    manifest_path = Path(first.artifact_directory) / "manifest.json"
    external_patch = original_task.candidate_patch
    original_bytes = external_patch.read_bytes()
    try:
        external_patch.write_text("tampered external patch\n", encoding="utf-8")
        replay_task = load_replay_task(manifest_path)
    finally:
        external_patch.write_bytes(original_bytes)
    assert replay_task.candidate_patch == Path(first.artifact_directory) / "candidate.patch"
    replay = VerificationHarness(tmp_path / "replay").run(replay_task)
    assert replay.outcome is RunOutcome.PASSED
