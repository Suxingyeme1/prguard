import json
import os
from pathlib import Path

import pytest

from prguard.cli import load_fix_task, main
from prguard.harness import verify_manifest
from prguard.onboarding import prepare_local_issue, read_issue_file
from prguard.onboarding.errors import OnboardingError
from tests.conftest import run_git

_FILES = {
    "src/calc.py": "def add(left, right):\n    return left - right\n",
    "tests/test_calc.py": (
        "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    ),
    "pyproject.toml": "[tool.pytest.ini_options]\npythonpath = ['src']\n",
}

@pytest.mark.integration
def test_prepare_local_issue_freezes_detached_checkout_and_manifest(
    make_repo, tmp_path: Path
) -> None:
    source, commit = make_repo(_FILES)
    output = tmp_path / "prepared"

    report = prepare_local_issue(
        source,
        "Fix add() so it returns the sum of both operands.",
        output,
        trust_host=True,
    )
    task = load_fix_task(report.task_path)

    assert task.repository == report.checkout
    assert task.repository != source
    assert task.base_commit == commit
    assert task.issue == "Fix add() so it returns the sum of both operands."
    assert report.issue.requested_base_commit == "HEAD"
    assert report.issue.base_commit == commit
    assert run_git(source, "status", "--porcelain=v1") == ""
    assert run_git(report.checkout, "rev-parse", "HEAD") == commit
    manifest = verify_manifest(output / "artifacts" / "preparation-manifest.json")
    assert manifest.policy_version == "local-onboarding-v1"


def test_prepare_local_issue_rejects_dirty_source(make_repo, tmp_path: Path) -> None:
    source, _ = make_repo(_FILES)
    (source / "untracked.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(OnboardingError, match="must be clean"):
        prepare_local_issue(
            source,
            "Fix add().",
            tmp_path / "prepared",
            trust_host=True,
        )

    assert not (tmp_path / "prepared").exists()


def test_prepare_local_rejects_output_inside_source(make_repo) -> None:
    source, _ = make_repo(_FILES)

    with pytest.raises(OnboardingError, match="outside the source"):
        prepare_local_issue(
            source,
            "Fix add().",
            source / "work" / "run",
            trust_host=True,
        )

    assert not (source / "work").exists()


def test_local_materialization_does_not_execute_source_hooks(
    make_repo, tmp_path: Path
) -> None:
    source, _ = make_repo(_FILES)
    marker = tmp_path / "hook-ran"
    hook = source / ".git" / "hooks" / "post-checkout"
    hook.write_text(f"#!/bin/sh\nprintf ran > '{marker}'\n", encoding="utf-8")
    hook.chmod(0o700)

    prepare_local_issue(
        source,
        "Fix add().",
        tmp_path / "prepared",
        trust_host=True,
    )

    assert not marker.exists()
    assert os.access(hook, os.X_OK)


def test_issue_file_boundary_rejects_symlink_and_nul(tmp_path: Path) -> None:
    issue = tmp_path / "issue.txt"
    issue.write_text("Fix the parser.\n", encoding="utf-8")
    link = tmp_path / "issue-link.txt"
    link.symlink_to(issue)

    assert read_issue_file(issue) == "Fix the parser."
    with pytest.raises(OnboardingError, match="non-symlink"):
        read_issue_file(link)
    issue.write_bytes(b"bad\x00issue")
    with pytest.raises(OnboardingError, match="NUL"):
        read_issue_file(issue)


def test_operator_policy_rejects_symlink_before_creating_workspace(
    make_repo, tmp_path: Path
) -> None:
    source, _ = make_repo(_FILES)
    policy = tmp_path / "policy.toml"
    policy.write_text(
        "version = 1\n"
        "verification_commands = [['pytest', '-q']]\n"
        "writable_paths = ['src/**']\n",
        encoding="utf-8",
    )
    link = tmp_path / "policy-link.toml"
    link.symlink_to(policy)
    output = tmp_path / "policy-output"

    with pytest.raises(OnboardingError, match="non-symlink"):
        prepare_local_issue(
            source,
            "Fix add().",
            output,
            trust_host=True,
            policy_file=link,
        )

    assert not output.exists()


@pytest.mark.integration
def test_fix_cli_accepts_local_repository_and_natural_language_issue(
    make_repo, tmp_path: Path, capsys
) -> None:
    source, commit = make_repo(_FILES)
    proposals = tmp_path / "proposals.json"
    proposals.write_text(
        json.dumps(
            [
                {
                    "plan": ["Correct add using one structured source edit."],
                    "summary": "Return the sum.",
                    "edits": [
                        {
                            "operation": "replace_text",
                            "path": "src/calc.py",
                            "old_text": "    return left - right\n",
                            "new_text": "    return left + right\n"
                        }
                    ],
                    "tests_changed": False
                }
            ]
        ),
        encoding="utf-8",
    )
    workspace = tmp_path / "local-workspace"

    exit_code = main(
        [
            "fix",
            "Fix add() so it returns the sum of both operands.",
            "--repository",
            str(source),
            "--workspace",
            str(workspace),
            "--base-commit",
            commit,
            "--trust-host",
            "--provider",
            "scripted",
            "--proposal-sequence",
            str(proposals),
            "--progress",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    result = json.loads(captured.out)
    assert result["outcome"] == "accepted"
    final_patch = Path(result["final_patch"]).read_text(encoding="utf-8")
    assert "-    return left - right" in final_patch
    assert "+    return left + right" in final_patch
    assert Path(result["artifact_directory"]).is_relative_to(workspace / "fix-runs")
    assert "[prguard] freezing local repository and Issue" in captured.err
    assert "[prguard] local task prepared" in captured.err
    assert run_git(source, "status", "--porcelain=v1") == ""


def test_prepare_local_cli_reads_issue_file(make_repo, tmp_path: Path, capsys) -> None:
    source, commit = make_repo(_FILES)
    issue = tmp_path / "issue.txt"
    issue.write_text("Fix add() from an Issue file.\n", encoding="utf-8")
    output = tmp_path / "prepared"

    exit_code = main(
        [
            "prepare-local",
            "--repository",
            str(source),
            "--issue-file",
            str(issue),
            "--output",
            str(output),
            "--base-commit",
            commit,
            "--trust-host",
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["issue"]["issue_text"] == "Fix add() from an Issue file."
    assert Path(report["task_path"]).is_file()
