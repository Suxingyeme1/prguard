import json
from pathlib import Path

import pytest

from prguard.cli import main
from prguard.schemas import CommandSpec, FixTask
from tests.conftest import run_git


@pytest.mark.integration
def test_inspect_symbol_uses_frozen_detached_worktree_and_cleans_it(
    make_repo,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository, base = make_repo(
        {
            "app.py": (
                "def leaf():\n"
                "    return 1\n\n"
                "def entry():\n"
                "    return leaf()\n"
            ),
            "tests/test_app.py": (
                "from app import entry\n\n"
                "def test_entry():\n"
                "    assert entry() == 1\n"
            ),
        }
    )
    task = FixTask(
        case_id="inspect-symbol-cli",
        repository=repository,
        base_commit=base,
        issue="Inspect leaf impact.",
        commands=[CommandSpec(argv=["pytest", "-q"], kind="pytest")],
        allowed_commands=[["pytest", "-q"]],
        writable_paths=["*.py", "tests/**"],
    )
    task_path = tmp_path / "task.json"
    task_path.write_text(task.model_dump_json(indent=2), encoding="utf-8")

    exit_code = main(
        [
            "inspect-symbol",
            str(task_path),
            "--symbol",
            "app.leaf",
            "--direction",
            "callers",
            "--max-depth",
            "2",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["resolved_base_commit"] == base
    graph = payload["call_graph"]
    assert graph["root_resolution"] == "exact"
    assert [item["symbol"] for item in graph["reachable_tests"]] == [
        "test_app.test_entry"
    ]
    assert run_git(repository, "status", "--porcelain") == ""
    worktrees = run_git(repository, "worktree", "list", "--porcelain")
    assert worktrees.count("worktree ") == 1
