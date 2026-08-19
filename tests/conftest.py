from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from prguard.cli import load_task
from prguard.schemas import Task
from scripts.materialize_fix_fixtures import materialize_fix_fixtures
from scripts.materialize_fixtures import materialize


def run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        shell=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


@pytest.fixture(scope="session")
def materialized_cases(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    project_root = Path(__file__).resolve().parents[1]
    output = tmp_path_factory.mktemp("materialized-cases")
    cases = materialize(project_root / "benchmark" / "fixtures", output)
    return {path.parent.name: path for path in cases}


@pytest.fixture
def task_for_case(materialized_cases: dict[str, Path]):
    def factory(name: str) -> Task:
        return load_task(materialized_cases[name])

    return factory


@pytest.fixture(scope="session")
def materialized_fix_cases(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    project_root = Path(__file__).resolve().parents[1]
    output = tmp_path_factory.mktemp("materialized-fix-cases")
    tasks = materialize_fix_fixtures(project_root / "benchmark" / "fix-fixtures", output)
    return {path.parent.name: path for path in tasks}


@pytest.fixture
def make_repo(tmp_path: Path):
    def factory(files: dict[str, str]) -> tuple[Path, str]:
        repo = tmp_path / "source"
        repo.mkdir()
        for relative, contents in files.items():
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8")
        run_git(repo, "init", "-b", "main")
        run_git(repo, "config", "user.name", "PRGuard Test")
        run_git(repo, "config", "user.email", "test@prguard.invalid")
        run_git(repo, "add", ".")
        run_git(repo, "commit", "-m", "base")
        return repo, run_git(repo, "rev-parse", "HEAD")

    return factory


def read_expected(case_path: Path) -> dict[str, object]:
    return json.loads((case_path.parent / "expected.json").read_text(encoding="utf-8"))
