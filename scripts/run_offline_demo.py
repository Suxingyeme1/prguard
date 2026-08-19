"""Run a key-free Issue-to-Patch demo with one evidence-guided repair."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from prguard.cli import load_fix_task
from prguard.fix import FixRunner
from prguard.harness import verify_manifest
from prguard.implementer.providers import ScriptedProvider
from prguard.schemas import FixOutcome, RunOutcome


def run_demo(work_root: Path) -> Path:
    """Materialize and run the repair fixture, returning its artifact directory."""

    project_root = Path(__file__).resolve().parents[1]
    demo_root = work_root.expanduser().resolve() / f"offline-demo-{uuid4().hex[:8]}"
    fixtures_root = demo_root / "fixtures"
    artifact_root = demo_root / "artifacts"

    subprocess.run(
        [
            sys.executable,
            str(project_root / "scripts" / "materialize_fix_fixtures.py"),
            "--output",
            str(fixtures_root),
        ],
        cwd=project_root,
        check=True,
        shell=False,
        capture_output=True,
        text=True,
    )

    case_root = fixtures_root / "repair-once"
    task = load_fix_task(case_root / "task.json")
    provider = ScriptedProvider.from_file(case_root / "proposals.json")
    report = FixRunner(artifact_root, provider).run(task)

    if report.outcome is not FixOutcome.ACCEPTED or len(report.attempts) != 2:
        raise RuntimeError(f"offline demo failed: {report.outcome}")
    first = report.attempts[0].verification
    second = report.attempts[1].verification
    if first is None or first.outcome is not RunOutcome.FAILED_VERIFICATION:
        raise RuntimeError("offline demo did not exercise the expected failed first attempt")
    if second is None or second.outcome is not RunOutcome.PASSED:
        raise RuntimeError("offline demo replacement patch did not pass verification")

    artifact_directory = Path(report.artifact_directory)
    manifest_path = artifact_directory / "fix-manifest.json"
    verify_manifest(manifest_path)

    print("PRGuard offline demo: ACCEPTED")
    print("  attempt 0: FAILED_VERIFICATION (pytest evidence captured)")
    print("  attempt 1: PASSED (complete replacement patch)")
    print(f"  final patch: {report.final_patch}")
    print(f"  manifest:    {manifest_path}")
    print("\nFinal patch:\n")
    print(Path(report.final_patch).read_text(encoding="utf-8"))
    return artifact_directory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-root",
        type=Path,
        default=Path("work"),
        help="parent directory for a uniquely named demo run (default: work)",
    )
    args = parser.parse_args()
    run_demo(args.work_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
