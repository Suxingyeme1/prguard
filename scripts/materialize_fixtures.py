"""Materialize committed fixture templates as runnable local Git cases."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        shell=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def materialize(source_root: Path, output_root: Path) -> list[Path]:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    cases: list[Path] = []
    for template in sorted(path for path in source_root.iterdir() if path.is_dir()):
        destination = output_root / template.name
        repo = destination / "repo"
        shutil.copytree(template / "repo", repo)
        for name in ("candidate.patch", "expected.json"):
            source = template / name
            if source.exists():
                shutil.copy2(source, destination / name)
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.name", "PRGuard Fixture")
        git(repo, "config", "user.email", "fixture@prguard.invalid")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "fixture base")
        commit = git(repo, "rev-parse", "HEAD")
        payload = json.loads((template / "case.template.json").read_text(encoding="utf-8"))
        payload["base_commit"] = commit
        case_path = destination / "case.json"
        case_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        cases.append(case_path)
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("benchmark/generated"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cases = materialize(root / "benchmark" / "fixtures", args.output.resolve())
    for case in cases:
        print(case)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
