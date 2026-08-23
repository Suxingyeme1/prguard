"""Compose remote metadata, checkout, project policy, and a frozen FixTask."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from prguard.harness.artifacts import canonical_json, sha256_bytes
from prguard.onboarding.errors import OnboardingError
from prguard.onboarding.github import GitHubClient, parse_github_issue_url
from prguard.onboarding.materialize import materialize_public_checkout
from prguard.onboarding.profile import discover_project_policy, load_project_config
from prguard.schemas import (
    ArtifactEntry,
    ContainerExecutionSpec,
    FixTask,
    GitHubIssueSnapshot,
    RunManifest,
    TaskPreparationReport,
)

Materializer = Callable[[GitHubIssueSnapshot, Path], Path]


def _case_id(snapshot: GitHubIssueSnapshot) -> str:
    owner = snapshot.reference.owner.lower()
    repository = snapshot.reference.repository.lower()
    return f"github-{owner}-{repository}-issue-{snapshot.reference.number}"


def prepare_github_issue(
    issue_url: str,
    output_directory: Path,
    *,
    base_commit: str | None = None,
    trust_host: bool = False,
    container_image: str | None = None,
    client: GitHubClient | None = None,
    materializer: Materializer = materialize_public_checkout,
    source_repository: Path | None = None,
) -> TaskPreparationReport:
    if trust_host == bool(container_image):
        raise OnboardingError(
            "choose exactly one execution boundary: trust_host or container_image"
        )
    reference = parse_github_issue_url(issue_url)
    snapshot = (client or GitHubClient()).fetch_issue(reference, base_commit=base_commit)
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=False)
    try:
        if source_repository is None:
            checkout = materializer(snapshot, output_directory / "repositories")
        elif materializer is materialize_public_checkout:
            checkout = materialize_public_checkout(
                snapshot,
                output_directory / "repositories",
                source_repository=source_repository,
            )
        else:
            raise OnboardingError(
                "source_repository cannot be combined with a custom materializer"
            )
        policy = discover_project_policy(checkout, issue=snapshot.issue_text)
        container = (
            ContainerExecutionSpec(image=container_image)
            if container_image is not None
            else None
        )
        task = FixTask(
            case_id=_case_id(snapshot),
            repository=checkout,
            base_commit=snapshot.base_commit,
            issue=snapshot.issue_text[:50_000],
            commands=policy.commands,
            allowed_commands=[command.argv for command in policy.commands],
            writable_paths=policy.writable_paths,
            protected_paths=policy.protected_paths,
            command_timeout_seconds=policy.command_timeout_seconds,
            task_timeout_seconds=policy.task_timeout_seconds,
            max_repair_attempts=policy.max_repair_attempts,
            container=container,
            runtime_files=policy.runtime_files,
        )
        artifact_directory = output_directory / "artifacts"
        artifact_directory.mkdir()
        task_path = artifact_directory / "task.json"
        task_path.write_bytes(canonical_json(task.model_dump(mode="json")))
        _, config_path = load_project_config(checkout)
        warnings = list(policy.warnings)
        if snapshot.archived:
            warnings.append("The GitHub repository is archived.")
        if base_commit is None:
            warnings.append(
                "Base Commit was frozen from the repository default-branch tip at "
                "preparation time."
            )
        if source_repository is not None:
            warnings.append(
                "A same-origin local repository was used as the frozen Git object cache."
            )
        if trust_host:
            warnings.append(
                "Host execution was explicitly trusted; repository tests are not "
                "OS-sandboxed."
            )
        report = TaskPreparationReport(
            issue=snapshot,
            checkout=checkout,
            task_path=task_path,
            config_path=config_path,
            policy_source=policy.source,
            execution_backend="host" if trust_host else "container",
            container=container,
            commands=policy.commands,
            writable_paths=policy.writable_paths,
            protected_paths=policy.protected_paths,
            runtime_files=policy.runtime_files,
            warnings=warnings,
        )
        report_path = artifact_directory / "preparation-report.json"
        report_path.write_bytes(canonical_json(report.model_dump(mode="json")))
        entries: list[ArtifactEntry] = []
        for path in (task_path, report_path):
            payload = path.read_bytes()
            entries.append(
                ArtifactEntry(
                    path=path.name,
                    sha256=sha256_bytes(payload),
                    size_bytes=len(payload),
                )
            )
        manifest = RunManifest(
            harness_version="github-task-preparation-v1",
            policy_version="github-onboarding-v1",
            run_id=f"prepare-{task.case_id}-{task.base_commit[:12]}",
            case_id=task.case_id,
            resolved_base_commit=task.base_commit,
            created_at=datetime.now(UTC),
            artifacts=entries,
            manifest_sha256="0" * 64,
        )
        manifest_payload = manifest.model_dump(mode="json", exclude={"manifest_sha256"})
        manifest = manifest.model_copy(
            update={"manifest_sha256": sha256_bytes(canonical_json(manifest_payload))}
        )
        (artifact_directory / "preparation-manifest.json").write_bytes(
            canonical_json(manifest.model_dump(mode="json"))
        )
        return report
    except Exception:
        shutil.rmtree(output_directory, ignore_errors=True)
        raise
