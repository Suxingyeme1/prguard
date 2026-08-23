from pathlib import Path

import pytest

from prguard.harness import VerificationHarness, verify_manifest
from prguard.schemas import CommandSpec, RunOutcome, RuntimeFileSpec, Task


@pytest.mark.security
@pytest.mark.integration
def test_protected_patch_is_blocked_before_commands(make_repo, tmp_path: Path) -> None:
    repo, commit = make_repo(
        {
            "app.py": "VALUE = 1\n",
            "tests/test_app.py": (
                "from app import VALUE\n\ndef test_value():\n    assert VALUE == 1\n"
            ),
        }
    )
    patch = tmp_path / "protected.patch"
    patch.write_text(
        "diff --git a/tests/test_app.py b/tests/test_app.py\n"
        "--- a/tests/test_app.py\n"
        "+++ b/tests/test_app.py\n"
        "@@ -2,2 +2,2 @@\n"
        " def test_value():\n"
        "-    assert VALUE == 1\n"
        "+    assert VALUE == 2\n",
        encoding="utf-8",
    )
    command = ["pytest", "-q", "tests"]
    task = Task(
        case_id="protected-write",
        repository=repo,
        base_commit=commit,
        issue="Do not edit tests.",
        candidate_patch=patch,
        commands=[CommandSpec(argv=command)],
        allowed_commands=[command],
        protected_paths=["tests/**"],
    )
    report = VerificationHarness(tmp_path / "artifacts").run(task)
    assert report.outcome is RunOutcome.POLICY_BLOCKED
    assert report.commands == []
    assert report.policy_violations[0].code == "protected_path_modified"


@pytest.mark.security
@pytest.mark.integration
def test_write_beside_worktree_is_detected(make_repo, tmp_path: Path) -> None:
    repo, commit = make_repo(
        {
            "tests/test_escape.py": (
                "from pathlib import Path\n\n"
                "def test_escape():\n"
                "    (Path.cwd().parent / 'escape.txt').write_text('owned')\n"
            )
        }
    )
    command = ["pytest", "-q", "tests"]
    task = Task(
        case_id="outside-write",
        repository=repo,
        base_commit=commit,
        issue="Detect writes outside the worktree.",
        commands=[CommandSpec(argv=command)],
        allowed_commands=[command],
    )
    report = VerificationHarness(tmp_path / "artifacts").run(task)
    assert report.outcome is RunOutcome.POLICY_BLOCKED
    assert any(item.code == "outside_worktree_write" for item in report.policy_violations)
    verify_manifest(Path(report.artifact_directory) / "manifest.json")
    assert not (Path(report.artifact_directory) / "escape.txt").exists()


@pytest.mark.security
@pytest.mark.integration
def test_source_checkout_mutation_is_detected(make_repo, tmp_path: Path) -> None:
    # The test code is intentionally malicious and embeds its source repository path.
    repo_placeholder, _ = make_repo({"placeholder.py": "VALUE = 1\n"})
    target = repo_placeholder / "owned.txt"
    test_file = repo_placeholder / "tests" / "test_source.py"
    test_file.parent.mkdir()
    test_file.write_text(
        "from pathlib import Path\n\n"
        f"def test_write():\n    Path({str(target)!r}).write_text('owned')\n",
        encoding="utf-8",
    )
    from tests.conftest import run_git

    run_git(repo_placeholder, "add", ".")
    run_git(repo_placeholder, "commit", "-m", "add malicious test")
    commit = run_git(repo_placeholder, "rev-parse", "HEAD")
    command = ["pytest", "-q", "tests"]
    task = Task(
        case_id="source-mutation",
        repository=repo_placeholder,
        base_commit=commit,
        issue="Detect source checkout mutation.",
        commands=[CommandSpec(argv=command)],
        allowed_commands=[command],
    )
    report = VerificationHarness(tmp_path / "artifacts").run(task)
    try:
        assert report.outcome is RunOutcome.POLICY_BLOCKED
        assert any(item.code == "source_checkout_modified" for item in report.policy_violations)
    finally:
        target.unlink(missing_ok=True)


@pytest.mark.security
@pytest.mark.integration
def test_unallowlisted_command_fails_closed(make_repo, tmp_path: Path) -> None:
    repo, commit = make_repo({"value.py": "VALUE = 1\n"})
    task = Task(
        case_id="command-policy",
        repository=repo,
        base_commit=commit,
        issue="Reject command.",
        commands=[CommandSpec(argv=["pytest", "-q"])],
        allowed_commands=[],
    )
    report = VerificationHarness(tmp_path / "artifacts").run(task)
    assert report.outcome is RunOutcome.POLICY_BLOCKED
    assert report.policy_violations[0].code == "command_not_allowed"


@pytest.mark.security
@pytest.mark.integration
def test_verification_cannot_tamper_with_runtime_scaffold(make_repo, tmp_path: Path) -> None:
    repo, commit = make_repo(
        {
            "tests/test_tamper.py": (
                "from pathlib import Path\n\n"
                "def test_tamper():\n"
                "    Path('src/pkg/_version.py').write_text('owned')\n"
            ),
            "src/pkg/__init__.py": "",
        }
    )
    command = ["pytest", "-q", "tests/test_tamper.py"]
    task = Task(
        case_id="runtime-scaffold-tamper",
        repository=repo,
        base_commit=commit,
        issue="Detect runtime scaffold tampering.",
        commands=[CommandSpec(argv=command)],
        allowed_commands=[command],
        runtime_files=[
            RuntimeFileSpec(
                path="src/pkg/_version.py",
                content='__version__ = "0+prguard"\n',
                reason="hatch_vcs_version_file",
            )
        ],
    )

    report = VerificationHarness(tmp_path / "runtime-tamper-artifacts").run(task)

    assert report.outcome is RunOutcome.POLICY_BLOCKED
    assert any(
        violation.code == "runtime_scaffold_modified"
        for violation in report.policy_violations
    )


@pytest.mark.security
@pytest.mark.integration
def test_derived_changed_test_argv_still_rejects_shell_tokens(
    make_repo, tmp_path: Path
) -> None:
    repo, commit = make_repo(
        {"tests/test_existing.py": "def test_existing():\n    assert True\n"}
    )
    patch = tmp_path / "unsafe-test-name.patch"
    patch.write_text(
        "diff --git a/tests/test_bad;name.py b/tests/test_bad;name.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/tests/test_bad;name.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def test_bad_name():\n"
        "+    assert True\n",
        encoding="utf-8",
    )
    command = ["pytest", "-q", "tests/test_existing.py"]
    task = Task(
        case_id="unsafe-derived-test-argv",
        repository=repo,
        base_commit=commit,
        issue="Reject unsafe derived argv tokens.",
        candidate_patch=patch,
        commands=[CommandSpec(argv=command)],
        allowed_commands=[command],
    )

    report = VerificationHarness(tmp_path / "unsafe-derived-artifacts").run(task)

    assert report.outcome is RunOutcome.POLICY_BLOCKED
    assert report.commands == []
    assert any(
        violation.code == "command_not_allowed"
        for violation in report.policy_violations
    )
