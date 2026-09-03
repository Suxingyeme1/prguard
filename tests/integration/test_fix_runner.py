import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from prguard.cli import load_fix_task, load_issue_to_pr_task, main
from prguard.fix import FixRunner
from prguard.harness import verify_manifest
from prguard.implementer.errors import ProviderError
from prguard.implementer.providers import ProviderRequest, ScriptedProvider
from prguard.implementer.tools import RepositoryTools
from prguard.schemas import (
    AgentToolCall,
    CommandSpec,
    FixOutcome,
    FixTask,
    ImplementerProposal,
    ProviderFailureEvidence,
    RunOutcome,
    TokenUsage,
)
from tests.conftest import run_git


def load_provider(case_path: Path) -> ScriptedProvider:
    return ScriptedProvider.from_file(case_path.parent / "proposals.json")


class EvidenceFailureProvider:
    name = "evidence-failure"
    model = "deterministic-fixture"

    def propose(self, request: ProviderRequest, tools: RepositoryTools):
        raise ProviderError(
            "Implementer tool-call budget exhausted",
            evidence=ProviderFailureEvidence(
                provider=self.name,
                model=self.model,
                response_id="partial-response",
                token_usage=TokenUsage(input_tokens=101, output_tokens=17, cached_tokens=40),
                tool_calls=[
                    AgentToolCall(
                        sequence=0,
                        name="find_symbols",
                        arguments={"query": "normalize", "max_results": 20},
                        succeeded=True,
                        output_bytes=128,
                    )
                ],
            ),
        )


class NeverCalledProvider:
    name = "never-called"
    model = "deterministic-fixture"

    def __init__(self) -> None:
        self.calls = 0

    def propose(self, request: ProviderRequest, tools: RepositoryTools):
        self.calls += 1
        raise AssertionError("provider must not run when the Base Commit gate is unhealthy")


@pytest.mark.integration
@pytest.mark.parametrize("case_name", ["direct-success", "repair-once"])
def test_issue_to_patch_fixture(
    case_name: str, materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case_path = materialized_fix_cases[case_name]
    task = load_fix_task(case_path)
    expected = json.loads((case_path.parent / "expected.json").read_text(encoding="utf-8"))
    report = FixRunner(tmp_path / "fix-artifacts", load_provider(case_path)).run(task)
    assert report.outcome.value == expected["outcome"]
    assert len(report.attempts) == expected["attempts"]
    assert report.final_patch and report.final_patch.is_file()
    assert run_git(task.repository, "status", "--porcelain") == ""
    manifest = verify_manifest(Path(report.artifact_directory) / "fix-manifest.json")
    assert manifest.run_id == report.run_id
    assert all(attempt.proposal.tool_calls for attempt in report.attempts if attempt.proposal)
    if case_name == "repair-once":
        assert report.attempts[0].verification.outcome is RunOutcome.FAILED_VERIFICATION
        assert report.attempts[1].verification.outcome is RunOutcome.PASSED
        assert "max(lower, min(value, upper))" in report.final_patch.read_text(encoding="utf-8")


@pytest.mark.integration
def test_fix_without_repair_budget_preserves_failure(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case_path = materialized_fix_cases["repair-once"]
    task = load_fix_task(case_path).model_copy(update={"max_repair_attempts": 0})
    report = FixRunner(tmp_path / "fix-artifacts", load_provider(case_path)).run(task)
    assert report.outcome is FixOutcome.FAILED_VERIFICATION
    assert len(report.attempts) == 1
    assert report.final_patch is None


@pytest.mark.integration
def test_fix_provider_failure_artifact_preserves_partial_evidence(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case_path = materialized_fix_cases["direct-success"]
    report = FixRunner(tmp_path / "fix-artifacts", EvidenceFailureProvider()).run(
        load_fix_task(case_path)
    )

    assert report.outcome is FixOutcome.AGENT_FAILED
    assert report.token_usage.input_tokens == 101
    failure = report.attempts[0].provider_failure
    assert failure is not None
    assert failure.tool_calls[0].name == "find_symbols"
    artifact_root = Path(report.artifact_directory)
    artifact = artifact_root / "attempt-0-provider-failure.json"
    assert json.loads(artifact.read_text())["response_id"] == "partial-response"
    manifest = verify_manifest(artifact_root / "fix-manifest.json")
    assert artifact.name in {entry.path for entry in manifest.artifacts}


@pytest.mark.integration
def test_fix_blocks_before_provider_when_base_non_pytest_gate_fails(
    make_repo, tmp_path: Path
) -> None:
    repo, commit = make_repo({"bad.py": "import os\n"})
    command = ["ruff", "check", "--no-fix", "."]
    task = FixTask(
        case_id="unhealthy-base-lint",
        repository=repo,
        base_commit=commit,
        issue="Change the module.",
        commands=[CommandSpec(argv=command, kind="ruff")],
        allowed_commands=[command],
        writable_paths=["*.py"],
    )
    provider = NeverCalledProvider()

    report = FixRunner(tmp_path / "fix-artifacts", provider).run(task)

    assert report.outcome is FixOutcome.PREFLIGHT_FAILED
    assert provider.calls == 0
    assert "non-pytest gate is not ready" in report.attempts[0].error
    readiness_reports = list(
        Path(report.artifact_directory).glob("readiness/*/report.json")
    )
    assert len(readiness_reports) == 1


@pytest.mark.integration
def test_protected_proposal_is_blocked_before_verification(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case_path = materialized_fix_cases["direct-success"]
    task = load_fix_task(case_path)
    proposal = ImplementerProposal(
        plan=["Tamper with protected configuration"],
        summary="Invalid proposal.",
        patch=(
            "diff --git a/pyproject.toml b/pyproject.toml\n"
            "--- a/pyproject.toml\n+++ b/pyproject.toml\n"
            "@@ -1 +1 @@\n-a\n+b\n"
        ),
        tests_changed=False,
    )
    report = FixRunner(tmp_path / "fix-artifacts", ScriptedProvider([proposal])).run(task)
    assert report.outcome is FixOutcome.POLICY_BLOCKED
    assert report.attempts[0].proposal is not None
    assert report.attempts[0].verification is None
    artifact_directory = Path(report.artifact_directory)
    assert (artifact_directory / "attempt-0.patch").read_text(encoding="utf-8") == proposal.patch
    assert (artifact_directory / "attempt-0-proposal.json").is_file()
    assert not (artifact_directory / "verification").exists()


@pytest.mark.integration
def test_fix_runner_materializes_structured_edits_as_git_patch(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case_path = materialized_fix_cases["direct-success"]
    task = load_fix_task(case_path)
    proposal = ImplementerProposal.model_validate(
        {
            "plan": ["Replace only the whitespace normalization expression"],
            "summary": "Collapse arbitrary whitespace with split and join.",
            "edits": [
                {
                    "operation": "replace_text",
                    "path": "slug.py",
                    "old_text": '    return value.strip().lower().replace(" ", "-")\n',
                    "new_text": '    return "-".join(value.strip().lower().split())\n',
                }
            ],
            "tests_changed": False,
        }
    )

    report = FixRunner(
        tmp_path / "structured-artifacts", ScriptedProvider([proposal])
    ).run(task)

    assert report.outcome is FixOutcome.ACCEPTED
    assert report.final_patch is not None
    patch = report.final_patch.read_text()
    assert patch.startswith("diff --git a/slug.py b/slug.py")
    assert 'return "-".join(value.strip().lower().split())' in patch
    assert run_git(task.repository, "status", "--porcelain") == ""
    proposal_artifact = json.loads(
        (Path(report.artifact_directory) / "attempt-0-proposal.json").read_text()
    )
    assert proposal_artifact["proposal"]["patch"] is None
    assert proposal_artifact["proposal"]["edits"][0]["operation"] == "replace_text"


class RecordingProvider:
    name = "recording-scripted"
    model = "deterministic-fixture"

    def __init__(self, inner: ScriptedProvider) -> None:
        self.inner = inner
        self.requests: list[ProviderRequest] = []

    def propose(self, request: ProviderRequest, tools: RepositoryTools):
        self.requests.append(request)
        return self.inner.propose(request, tools)


@pytest.mark.integration
def test_repair_receives_only_structured_failure_evidence(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case = materialized_fix_cases["repair-once"]
    provider = RecordingProvider(load_provider(case))
    report = FixRunner(tmp_path / "artifacts", provider).run(load_fix_task(case))
    assert report.outcome is FixOutcome.ACCEPTED
    feedback = json.loads(provider.requests[1].feedback)
    assert feedback["outcome"] == "failed_verification"
    assert feedback["commands"][0]["exit_code"] == 1
    assert "previous_patch" in feedback
    assert "gold_patch" not in provider.requests[1].feedback


@pytest.mark.integration
def test_fix_cli_runs_scripted_issue_to_patch(
    materialized_fix_cases: dict[str, Path], tmp_path: Path, capsys
) -> None:
    case = materialized_fix_cases["direct-success"]
    exit_code = main(
        [
            "fix",
            str(case),
            "--provider",
            "scripted",
            "--proposal-sequence",
            str(case.parent / "proposals.json"),
            "--artifacts",
            str(tmp_path / "cli-artifacts"),
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["outcome"] == "accepted"


@pytest.mark.integration
def test_fix_cli_accepts_github_issue_url_and_preserves_preparation_workspace(
    materialized_fix_cases: dict[str, Path], tmp_path: Path, capsys, monkeypatch
) -> None:
    case = materialized_fix_cases["direct-success"]
    source_task = load_fix_task(case)
    workspace = tmp_path / "github-workspace"
    calls: list[dict[str, object]] = []

    def fake_prepare(issue_url: str, output: Path, **kwargs):
        calls.append({"issue_url": issue_url, "output": output, **kwargs})
        return SimpleNamespace(
            task_path=case,
            issue=SimpleNamespace(
                reference=SimpleNamespace(number=42),
                base_commit=source_task.base_commit,
            ),
        )

    monkeypatch.setattr("prguard.onboarding.prepare_github_issue", fake_prepare)
    exit_code = main(
        [
            "fix",
            "https://github.com/acme/slug/issues/42",
            "--workspace",
            str(workspace),
            "--trust-host",
            "--provider",
            "scripted",
            "--proposal-sequence",
            str(case.parent / "proposals.json"),
            "--progress",
        ]
    )

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["outcome"] == "accepted"
    assert calls == [
        {
            "issue_url": "https://github.com/acme/slug/issues/42",
            "output": workspace,
            "base_commit": None,
            "trust_host": True,
            "container_image": None,
            "source_repository": None,
        }
    ]
    assert Path(output["artifact_directory"]).is_relative_to(workspace / "fix-runs")
    assert "[prguard] freezing GitHub Issue and repository" in captured.err
    assert "[prguard] GitHub task prepared" in captured.err


def test_fix_cli_rejects_github_only_options_for_local_task(
    materialized_fix_cases: dict[str, Path], tmp_path: Path, capsys
) -> None:
    case = materialized_fix_cases["direct-success"]
    exit_code = main(["fix", str(case), "--workspace", str(tmp_path / "unused")])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "preparation options require a GitHub Issue URL or local Issue input" in captured.err


def test_issue_to_pr_loader_derives_stage_budgets_for_prepared_fix_task(
    materialized_fix_cases: dict[str, Path],
) -> None:
    task = load_issue_to_pr_task(materialized_fix_cases["direct-success"])

    assert task.fix_timeout_seconds + task.review_timeout_seconds < task.task_timeout_seconds


def test_fix_cli_progress_uses_stderr_without_breaking_json_stdout(
    materialized_fix_cases: dict[str, Path], tmp_path: Path, capsys
) -> None:
    case = materialized_fix_cases["direct-success"]

    exit_code = main(
        [
            "fix",
            str(case),
            "--provider",
            "scripted",
            "--proposal-sequence",
            str(case.parent / "proposals.json"),
            "--artifacts",
            str(tmp_path / "cli-progress-artifacts"),
            "--progress",
        ]
    )

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["outcome"] == "accepted"
    assert "[prguard] Implementer working — attempt 0" in captured.err
    assert "[prguard] verification completed — passed" in captured.err
    assert "[prguard] run completed — accepted" in captured.err


def test_progress_observer_failure_cannot_change_fix_outcome(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case = materialized_fix_cases["direct-success"]

    def broken_observer(_event: str, _data: dict[str, object]) -> None:
        raise RuntimeError("presentation failure")

    report = FixRunner(
        tmp_path / "observer-artifacts",
        load_provider(case),
        progress=broken_observer,
    ).run(load_fix_task(case))

    assert report.outcome is FixOutcome.ACCEPTED
    assert report.final_patch is not None


def test_fix_runner_structures_repository_preflight_failure(
    materialized_fix_cases: dict[str, Path], tmp_path: Path
) -> None:
    case = materialized_fix_cases["direct-success"]
    task = load_fix_task(case).model_copy(update={"repository": tmp_path / "missing-repository"})

    report = FixRunner(tmp_path / "preflight-artifacts", load_provider(case)).run(task)

    assert report.outcome is FixOutcome.PREFLIGHT_FAILED
    assert report.attempts[0].error is not None
    assert "repository does not exist" in report.attempts[0].error


@pytest.mark.integration
def test_fix_runner_blocks_uncollectable_base_before_provider_call(
    make_repo, tmp_path: Path
) -> None:
    repository, commit = make_repo(
        {
            "app.py": "VALUE = 1\n",
            "tests/test_app.py": "import missing_build_generated_module\n",
        }
    )
    task = FixTask(
        case_id="uncollectable-base",
        repository=repository,
        base_commit=commit,
        issue="Set VALUE to two.",
        commands=[CommandSpec(argv=["pytest", "-q"], kind="pytest")],
        allowed_commands=[["pytest", "-q"]],
        writable_paths=["*.py", "tests/**"],
    )
    proposal = ImplementerProposal(
        plan=["Change the value"],
        summary="Set VALUE to two.",
        patch=(
            "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
            "@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
        ),
        tests_changed=False,
    )

    report = FixRunner(
        tmp_path / "readiness-artifacts", ScriptedProvider([proposal])
    ).run(task)

    assert report.outcome is FixOutcome.PREFLIGHT_FAILED
    assert report.attempts[0].proposal is None
    assert "base pytest collection is not ready" in report.attempts[0].error
    readiness_manifests = list(
        Path(report.artifact_directory).glob("readiness/*/manifest.json")
    )
    assert len(readiness_manifests) == 1
    assert verify_manifest(readiness_manifests[0]).case_id.endswith("-readiness")
