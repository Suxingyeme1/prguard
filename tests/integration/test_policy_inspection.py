import json
import tomllib
from pathlib import Path

from prguard.cli import main
from prguard.onboarding import inspect_project_policy


def test_policy_inspection_explains_inferred_gate_and_renders_valid_config(
    make_repo,
) -> None:
    repository, commit = make_repo(
        {
            "src/pkg/__init__.py": "def parse(value):\n    return value\n",
            "tests/test_parse.py": (
                "from pkg import parse\n\ndef test_parse():\n    assert parse('x') == 'x'\n"
            ),
            "pyproject.toml": "[tool.pytest.ini_options]\npythonpath = ['src']\n",
        }
    )

    report = inspect_project_policy(
        repository,
        issue="`parse()` should normalize input.",
    )

    assert report.status == "ready"
    assert report.base_commit == commit
    assert report.policy_source == "deterministic_discovery"
    assert report.commands[0].argv == ["pytest", "-q", "tests/test_parse.py"]
    assert report.suggested_config is not None
    candidate = tomllib.loads(report.suggested_config)
    assert candidate["verification_commands"] == [
        ["pytest", "-q", "tests/test_parse.py"]
    ]
    assert candidate["writable_paths"] == ["src/**", "tests/**"]
    assert any("commit it as .prguard.toml" in item for item in report.next_actions)


def test_policy_inspection_reports_missing_gate_without_inventing_one(
    make_repo, capsys
) -> None:
    repository, _ = make_repo(
        {
            "src/pkg/__init__.py": "VALUE = 1\n",
            "README.md": "No test gate is declared.\n",
        }
    )

    exit_code = main(["inspect-policy", "--repository", str(repository)])

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert exit_code == 1
    assert captured.err == ""
    assert report["status"] == "needs_config"
    assert report["commands"] == []
    assert report["suggested_config"] is None
    assert "no safe pytest/Ruff command" in report["blocking_reasons"][0]
    assert "will not invent a command" in report["next_actions"][0]


def test_policy_inspection_surfaces_invalid_repository_config(make_repo, capsys) -> None:
    repository, _ = make_repo(
        {
            ".prguard.toml": (
                "version = 1\n"
                "verification_commands = [['bash', '-lc', 'pytest']]\n"
                "writable_paths = ['src/**']\n"
            ),
            "src/pkg/__init__.py": "VALUE = 1\n",
            "tests/test_pkg.py": "def test_pkg():\n    assert True\n",
        }
    )

    exit_code = main(["inspect-policy", "--repository", str(repository)])

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert report["status"] == "needs_config"
    assert report["config_path"].endswith("/.prguard.toml")
    assert "unsafe verification command" in report["blocking_reasons"][0]
    assert any("Correct the existing" in item for item in report["next_actions"])


def test_policy_inspection_never_executes_test_code(make_repo, tmp_path: Path) -> None:
    marker = tmp_path / "test-code-ran"
    repository, _ = make_repo(
        {
            "src/pkg/__init__.py": "VALUE = 1\n",
            "tests/conftest.py": (
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('ran', encoding='utf-8')\n"
            ),
            "tests/test_pkg.py": "def test_pkg():\n    assert True\n",
            "pyproject.toml": "[tool.pytest.ini_options]\npythonpath = ['src']\n",
        }
    )

    report = inspect_project_policy(repository)

    assert report.status == "ready"
    assert not marker.exists()
