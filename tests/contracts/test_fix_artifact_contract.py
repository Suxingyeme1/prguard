from pathlib import Path

import pytest

from prguard.cli import load_fix_task
from prguard.fix import FixRunner
from prguard.harness import verify_manifest
from prguard.harness.errors import ArtifactIntegrityError
from prguard.implementer.providers import ScriptedProvider


@pytest.mark.integration
def test_fix_manifest_covers_nested_verification_artifacts(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case = materialized_fix_cases["direct-success"]
    report = FixRunner(
        tmp_path / "artifacts", ScriptedProvider.from_file(case.parent / "proposals.json")
    ).run(load_fix_task(case))
    root = Path(report.artifact_directory)
    manifest = verify_manifest(root / "fix-manifest.json")
    paths = {entry.path for entry in manifest.artifacts}
    assert "final.patch" in paths
    assert any(path.endswith("/manifest.json") for path in paths)
    report.final_patch.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ArtifactIntegrityError, match="hash mismatch"):
        verify_manifest(root / "fix-manifest.json")
