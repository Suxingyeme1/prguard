import json
from io import StringIO
from pathlib import Path

import pytest

from prguard.cli import main
from prguard.harness import verify_manifest
from prguard.interactive import run_interactive_fix
from prguard.onboarding.errors import OnboardingError

_FILES = {
    "src/calc.py": "def add(left, right):\n    return left - right\n",
    "tests/test_calc.py": ("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"),
    "pyproject.toml": "[tool.pytest.ini_options]\npythonpath = ['src']\n",
}


def _proposal(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "plan": ["Locate add and preserve the public signature."],
                    "summary": "Return the sum of both operands.",
                    "edits": [
                        {
                            "operation": "replace_text",
                            "path": "src/calc.py",
                            "old_text": "    return left - right\n",
                            "new_text": "    return left + right\n",
                        }
                    ],
                    "tests_changed": False,
                }
            ]
        ),
        encoding="utf-8",
    )


@pytest.mark.integration
def test_start_cli_previews_policy_and_runs_real_fix_pipeline(
    make_repo, tmp_path: Path, capsys
) -> None:
    repository, commit = make_repo(_FILES)
    proposals = tmp_path / "proposals.json"
    _proposal(proposals)
    workspace = tmp_path / "guided-session"

    exit_code = main(
        [
            "start",
            "--repository",
            str(repository),
            "--issue",
            "Fix add() so that two numbers are added.",
            "--base-commit",
            "HEAD",
            "--workspace",
            str(workspace),
            "--trust-host",
            "--provider",
            "scripted",
            "--proposal-sequence",
            str(proposals),
            "--yes",
            "--no-color",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "PRGuard · Repository Coding Session" in captured.out
    assert f"HEAD → {commit[:12]}" in captured.out
    assert "DETERMINISTIC POLICY" in captured.out
    assert "$ pytest" in captured.out
    assert "HOST · repository tests run with the current user" in captured.out
    assert "Implementer" in captured.out
    assert "ACCEPTED" in captured.out
    manifests = list((workspace / "fix-runs").glob("*/fix-manifest.json"))
    assert len(manifests) == 1
    verify_manifest(manifests[0])


@pytest.mark.integration
def test_start_yes_still_requires_explicit_execution_boundary(
    make_repo, tmp_path: Path, capsys
) -> None:
    repository, _ = make_repo(_FILES)
    proposals = tmp_path / "proposals.json"
    _proposal(proposals)

    exit_code = main(
        [
            "start",
            "--repository",
            str(repository),
            "--issue",
            "Fix add().",
            "--provider",
            "scripted",
            "--proposal-sequence",
            str(proposals),
            "--yes",
            "--no-color",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "requires an explicit --trust-host or --container-image" in captured.err
    assert "PIPELINE" not in captured.out


@pytest.mark.integration
def test_cancelled_start_does_not_construct_provider(make_repo) -> None:
    repository, _ = make_repo(_FILES)
    provider_calls = 0

    def provider_source():
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("cancelled session must not construct a provider")

    with pytest.raises(OnboardingError, match="cancelled"):
        run_interactive_fix(
            repository=repository,
            provider=provider_source,
            issue="Fix add().",
            trust_host=True,
            input_fn=lambda _: "cancel",
            stream=StringIO(),
            color=False,
        )

    assert provider_calls == 0
