"""Create independent Git repositories and scripted proposals for fix demos."""

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


def materialize_fix_fixtures(source_root: Path, output_root: Path) -> list[Path]:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    tasks: list[Path] = []
    for template in sorted(path for path in source_root.iterdir() if path.is_dir()):
        destination = output_root / template.name
        repo = destination / "repo"
        shutil.copytree(template / "repo", repo)
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.name", "PRGuard Fix Fixture")
        git(repo, "config", "user.email", "fix-fixture@prguard.invalid")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "fix fixture base")
        commit = git(repo, "rev-parse", "HEAD")
        task = json.loads((template / "task.template.json").read_text(encoding="utf-8"))
        task["base_commit"] = commit
        task_path = destination / "task.json"
        task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
        proposals = json.loads((template / "proposals.template.json").read_text(encoding="utf-8"))
        for proposal in proposals:
            patch_file = proposal.pop("patch_file")
            proposal["patch"] = (template / patch_file).read_text(encoding="utf-8")
        (destination / "proposals.json").write_text(
            json.dumps(proposals, indent=2) + "\n", encoding="utf-8"
        )
        shutil.copy2(template / "expected.json", destination / "expected.json")
        tasks.append(task_path)
    return tasks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("benchmark/generated-fix"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    tasks = materialize_fix_fixtures(root / "benchmark" / "fix-fixtures", args.output.resolve())
    for task in tasks:
        print(task)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
