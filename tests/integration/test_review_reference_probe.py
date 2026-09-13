import hashlib

import pytest

from prguard.harness import VerificationHarness, verify_manifest
from prguard.harness.artifacts import load_replay_task
from prguard.schemas import CommandSpec, RunOutcome, Task, TaskMode

_REGRESSED = (
    "diff --git a/src/calc.py b/src/calc.py\n--- a/src/calc.py\n+++ b/src/calc.py\n"
    "@@ -1,2 +1,2 @@\n def add(left, right):\n-    return left + right\n+    return left - right\n"
)


@pytest.fixture
def reference_task(make_repo, tmp_path):
    repo, commit = make_repo({
        "src/calc.py": "def add(left, right):\n    return left + right\n",
        "tests/test_existing.py": "def test_existing():\n    assert True\n",
    })
    reference = tmp_path / "reviewed.patch"
    reference.write_text(_REGRESSED)

    def make(assertion="add(2, 3) == 5"):
        patch = tmp_path / "repaired.patch"
        patch.write_text(
            "diff --git a/tests/test_regression.py b/tests/test_regression.py\n"
            "new file mode 100644\n--- /dev/null\n+++ b/tests/test_regression.py\n"
            "@@ -0,0 +1,4 @@\n+from calc import add\n+\n+def test_regression():\n"
            f"+    assert {assertion}\n"
        )
        command = ["pytest", "-q", "tests"]
        return Task(
            case_id="review-reference", mode=TaskMode.REVIEW_REPAIR,
            repository=repo, base_commit=commit, issue="Restore addition after a regression.",
            candidate_patch=patch, commands=[CommandSpec(argv=command)], allowed_commands=[command],
            writable_paths=["src/**", "tests/**"], protected_paths=[".env"],
            require_changed_tests_fail_on_base=True, changed_test_reference_patch=reference,
            changed_test_reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
        )
    return make


@pytest.mark.integration
def test_review_regression_test_can_pass_base_but_must_fail_candidate(reference_task, tmp_path):
    task = reference_task()
    report = VerificationHarness(tmp_path / "runs").run(task)
    assert report.outcome is RunOutcome.PASSED
    assert report.changed_test_reference == "review_candidate"
    assert report.changed_test_reference_sha256 == task.changed_test_reference_sha256
    probe = report.changed_test_base_results[0]
    assert probe.kind == "pytest_changed_tests_review_candidate"
    assert probe.exit_code == 1
    assert "1 failed" in probe.stdout
    assert "2 passed" in report.commands[0].stdout
    manifest = verify_manifest(report.artifact_directory / "manifest.json")
    assert any(item.path == "changed-test-reference.patch" for item in manifest.artifacts)
    task.changed_test_reference_patch.write_text("external reference was changed")
    replay = load_replay_task(report.artifact_directory / "manifest.json")
    assert replay.changed_test_reference_patch == (
        report.artifact_directory / "changed-test-reference.patch"
    )
    assert VerificationHarness(tmp_path / "replay").run(replay).outcome is RunOutcome.PASSED
    assert (task.repository / "src/calc.py").read_text().endswith("return left + right\n")
    assert "changed_test_reference_patch" not in task.public_context()


@pytest.mark.integration
def test_vacuous_tests_still_fail_the_review_reference_gate(reference_task, tmp_path):
    report = VerificationHarness(tmp_path / "runs").run(reference_task("True"))
    assert report.outcome is RunOutcome.POLICY_BLOCKED
    assert report.commands == []
    assert report.policy_violations[0].code == "changed_tests_pass_on_review_candidate"


@pytest.mark.security
@pytest.mark.parametrize("invalid", ["hash", "symlink"])
def test_reference_must_match_frozen_regular_patch(reference_task, tmp_path, invalid):
    task = reference_task()
    if invalid == "hash":
        task.changed_test_reference_sha256 = "0" * 64
    else:
        link = tmp_path / "link.patch"
        link.symlink_to(task.changed_test_reference_patch)
        task.changed_test_reference_patch = link
    report = VerificationHarness(tmp_path / "runs").run(task)
    assert report.outcome is RunOutcome.PREFLIGHT_FAILED
    assert not report.commands
    assert not report.changed_test_base_results


def test_reference_cannot_override_initial_fix_base_probe(reference_task):
    payload = reference_task().model_dump()
    payload["mode"] = TaskMode.REVIEW
    with pytest.raises(ValueError, match="only valid"):
        Task.model_validate(payload)
    payload["mode"] = TaskMode.REVIEW_REPAIR
    payload["changed_test_reference_sha256"] = None
    with pytest.raises(ValueError, match="both"):
        Task.model_validate(payload)


@pytest.mark.security
@pytest.mark.parametrize("invalid", ["protected", "malformed"])
def test_reference_cannot_bypass_patch_policy(reference_task, tmp_path, invalid):
    task = reference_task()
    payload = (
        "diff --git a/.env b/.env\nnew file mode 100644\n"
        "--- /dev/null\n+++ b/.env\n@@ -0,0 +1 @@\n+UNSAFE=1\n"
        if invalid == "protected" else "not a Git Patch\n"
    )
    task.changed_test_reference_patch.write_text(payload)
    task.changed_test_reference_sha256 = hashlib.sha256(payload.encode()).hexdigest()
    report = VerificationHarness(tmp_path / "runs").run(task)
    assert report.outcome is (
        RunOutcome.POLICY_BLOCKED if invalid == "protected" else RunOutcome.PREFLIGHT_FAILED
    )
    assert not report.commands
    assert not report.changed_test_base_results
    assert not (task.repository / ".env").exists()
