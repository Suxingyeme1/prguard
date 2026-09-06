import json
import sys
from pathlib import Path

import pytest

from prguard.cli import main
from prguard.harness import verify_manifest


@pytest.mark.integration
def test_gate_cli_reuses_fix_boundary_and_records_python_runtime(
    materialized_fix_cases: dict[str, Path], tmp_path: Path, capsys
) -> None:
    task = materialized_fix_cases["direct-success"]
    patch = (
        Path(__file__).resolve().parents[2]
        / "benchmark"
        / "fix-fixtures"
        / "direct-success"
        / "attempt-0.patch"
    )
    artifacts = tmp_path / "gate-artifacts"

    exit_code = main(
        [
            "gate",
            str(task),
            "--candidate-patch",
            str(patch),
            "--artifacts",
            str(artifacts),
        ]
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["outcome"] == "passed"
    assert report["patch"]["attempted"] is True
    runtime = report["commands"][0]["runtime"]
    assert runtime["implementation"] == sys.implementation.name
    assert runtime["version"] == ".".join(str(value) for value in sys.version_info[:3])
    assert runtime["provenance"] == "host_process"
    manifest = verify_manifest(Path(report["artifact_directory"]) / "manifest.json")
    assert manifest.case_id == "fix-direct-success-gate"


def test_gate_cli_can_check_unpatched_base_without_model(
    materialized_fix_cases: dict[str, Path], tmp_path: Path, capsys
) -> None:
    task = materialized_fix_cases["direct-success"]

    exit_code = main(
        [
            "gate",
            str(task),
            "--artifacts",
            str(tmp_path / "base-artifacts"),
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert report["outcome"] == "failed_verification"
    assert report["patch"] == {
        "attempted": False,
        "applied": True,
        "patch_sha256": None,
        "stderr": "",
    }


def test_gate_cli_blocks_candidate_outside_frozen_writable_scope(
    materialized_fix_cases: dict[str, Path], tmp_path: Path, capsys
) -> None:
    task = materialized_fix_cases["direct-success"]
    patch = tmp_path / "outside-scope.patch"
    patch.write_text(
        "diff --git a/README.md b/README.md\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/README.md\n"
        "@@ -0,0 +1 @@\n"
        "+unrelated change\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "gate",
            str(task),
            "--candidate-patch",
            str(patch),
            "--artifacts",
            str(tmp_path / "outside-artifacts"),
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert report["outcome"] == "policy_blocked"
    assert report["policy_violations"] == [
        {
            "code": "outside_writable_scope",
            "message": (
                "candidate changes include paths outside the declared writable scope"
            ),
            "paths": ["README.md"],
        }
    ]
