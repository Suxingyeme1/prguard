"""Freeze a local repository and natural-language Issue into a verified FixTask."""

from __future__ import annotations

import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from prguard.harness.artifacts import canonical_json, sha256_bytes
from prguard.onboarding.errors import OnboardingError
from prguard.onboarding.materialize import materialize_local_checkout
from prguard.onboarding.profile import (
    discover_project_policy,
    load_operator_project_config,
    load_project_config,
)
from prguard.schemas import (
    ArtifactEntry,
    ContainerExecutionSpec,
    FixTask,
    LocalIssueSnapshot,
    LocalTaskPreparationReport,
    RunManifest,
)

_SAFE_CASE = re.compile(r"[^A-Za-z0-9._-]+")


def read_issue_file(path: Path) -> str:
    supplied = path.expanduser()
    if supplied.is_symlink():
        raise OnboardingError("issue file must be a regular non-symlink file")
    source = supplied.resolve(strict=False)
    if not source.is_file():
        raise OnboardingError("issue file must be a regular non-symlink file")
    if source.stat().st_size > 50_000:
        raise OnboardingError("issue file exceeds the 50000-byte input limit")
    try:
        return _validate_issue(source.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise OnboardingError("issue file must be UTF-8 text") from exc


def _validate_issue(issue: str) -> str:
    if "\x00" in issue:
        raise OnboardingError("issue text contains a NUL byte")
    value = issue.strip()
    if not value:
        raise OnboardingError("issue text must not be empty")
    if len(value.encode("utf-8")) > 50_000:
        raise OnboardingError("issue text exceeds the 50000-byte input limit")
    return value


def _case_id(repository: Path, commit: str) -> str:
    name = _SAFE_CASE.sub("-", repository.name.lower()).strip("-") or "repository"
    return f"local-{name}-{commit[:12]}"


def prepare_local_issue(
    repository: Path,
    issue: str,
    output_directory: Path,
    *,
    base_commit: str = "HEAD",
    trust_host: bool = False,
    container_image: str | None = None,
    policy_file: Path | None = None,
) -> LocalTaskPreparationReport:
    if trust_host == bool(container_image):
        raise OnboardingError(
            "choose exactly one execution boundary: trust_host or container_image"
        )
    issue = _validate_issue(issue)
    operator_config = (
        load_operator_project_config(policy_file) if policy_file is not None else None
    )
    source = repository.expanduser().resolve()
    output_directory = output_directory.expanduser().resolve()
    if output_directory == source or output_directory.is_relative_to(source):
        raise OnboardingError(
            "local preparation output must be outside the source repository"
        )
    output_directory.mkdir(parents=True, exist_ok=False)
    try:
        checkout, resolved = materialize_local_checkout(
            source, base_commit, output_directory / "repositories"
        )
        policy = discover_project_policy(
            checkout,
            issue=issue,
            operator_config=operator_config,
        )
        container = (
            ContainerExecutionSpec(image=container_image)
            if container_image is not None
            else None
        )
        snapshot = LocalIssueSnapshot(
            source_repository=source,
            requested_base_commit=base_commit,
            base_commit=resolved,
            issue_text=issue,
            issue_sha256=sha256_bytes(issue.encode("utf-8")),
        )
        task = FixTask(
            case_id=_case_id(source, resolved),
            repository=checkout,
            base_commit=resolved,
            issue=issue,
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
        _, repository_config_path = load_project_config(checkout)
        config_path = (
            policy_file.expanduser().resolve()
            if policy_file is not None
            else repository_config_path
        )
        policy_artifact = None
        if operator_config is not None:
            policy_artifact = artifact_directory / "operator-policy.json"
            policy_artifact.write_bytes(
                canonical_json(operator_config.model_dump(mode="json"))
            )
        warnings = [
            *policy.warnings,
            "The local source repository was copied into a detached frozen checkout; "
            "the source working tree will not be edited.",
        ]
        if base_commit == "HEAD":
            warnings.append("Base Commit was frozen from local HEAD at preparation time.")
        if trust_host:
            warnings.append(
                "Host execution was explicitly trusted; repository tests are not OS-sandboxed."
            )
        if operator_config is not None:
            warnings.append(
                "An operator-supplied policy was validated and frozen in preparation artifacts."
            )
        report = LocalTaskPreparationReport(
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
        entries = []
        for path in (task_path, report_path, policy_artifact):
            if path is None:
                continue
            payload = path.read_bytes()
            entries.append(
                ArtifactEntry(
                    path=path.name,
                    sha256=sha256_bytes(payload),
                    size_bytes=len(payload),
                )
            )
        manifest = RunManifest(
            harness_version="local-task-preparation-v1",
            policy_version="local-onboarding-v1",
            run_id=f"prepare-{task.case_id}",
            case_id=task.case_id,
            resolved_base_commit=resolved,
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
