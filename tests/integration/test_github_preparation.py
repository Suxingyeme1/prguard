import json
import shutil
from pathlib import Path

import pytest

from prguard.cli import load_fix_task
from prguard.harness import verify_manifest
from prguard.onboarding.errors import OnboardingError
from prguard.onboarding.prepare import prepare_github_issue
from prguard.schemas import GitHubIssueSnapshot


class FrozenClient:
    def __init__(self, commit: str) -> None:
        self.commit = commit

    def fetch_issue(self, reference, *, base_commit=None):
        return GitHubIssueSnapshot(
            reference=reference,
            title="Correct addition",
            body="Return the sum of both operands.",
            state="open",
            repository_url="https://github.com/acme/calc",
            clone_url="https://github.com/acme/calc.git",
            default_branch="main",
            base_commit=self.commit,
        )


@pytest.mark.integration
def test_prepare_github_issue_materializes_valid_minimal_fix_task(
    make_repo, tmp_path: Path
) -> None:
    source, commit = make_repo(
        {
            "src/calc.py": "def add(left, right):\n    return left - right\n",
            "tests/test_calc.py": (
                "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
            ),
            "pyproject.toml": (
                "[tool.pytest.ini_options]\npythonpath = ['src']\n"
                "[tool.ruff]\nline-length = 100\n"
            ),
        }
    )

    def copy_checkout(_snapshot: GitHubIssueSnapshot, root: Path) -> Path:
        destination = root / "acme-calc"
        root.mkdir(parents=True)
        shutil.copytree(source, destination)
        return destination

    output = tmp_path / "prepared"
    report = prepare_github_issue(
        "https://github.com/acme/calc/issues/9",
        output,
        trust_host=True,
        client=FrozenClient(commit),
        materializer=copy_checkout,
    )
    task = load_fix_task(report.task_path)

    assert task.repository == report.checkout
    assert task.base_commit == commit
    assert task.issue.startswith("GitHub Issue #9: Correct addition")
    assert [command.argv for command in task.commands] == [
        ["pytest", "-q"],
        ["ruff", "check", "."],
    ]
    assert task.container is None
    manifest_path = output / "artifacts" / "preparation-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["resolved_base_commit"] == commit
    assert verify_manifest(manifest_path).case_id == task.case_id


def test_prepare_requires_explicit_execution_boundary(tmp_path: Path) -> None:
    with pytest.raises(OnboardingError, match="exactly one"):
        prepare_github_issue(
            "https://github.com/acme/calc/issues/9",
            tmp_path / "prepared",
            client=FrozenClient("a" * 40),
        )


def test_prepare_cleans_owned_output_when_discovery_fails(
    make_repo, tmp_path: Path
) -> None:
    source, commit = make_repo({"README.md": "no Python profile\n"})

    def copy_checkout(_snapshot: GitHubIssueSnapshot, root: Path) -> Path:
        destination = root / "acme-calc"
        root.mkdir(parents=True)
        shutil.copytree(source, destination)
        return destination

    output = tmp_path / "prepared"
    with pytest.raises(OnboardingError):
        prepare_github_issue(
            "https://github.com/acme/calc/issues/9",
            output,
            trust_host=True,
            client=FrozenClient(commit),
            materializer=copy_checkout,
        )

    assert not output.exists()
