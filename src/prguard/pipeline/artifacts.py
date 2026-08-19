"""Auditable top-level Issue-to-PR artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from prguard.harness.artifacts import canonical_json, sha256_bytes
from prguard.schemas import (
    ISSUE_TO_PR_WORKFLOW_VERSION,
    PATCH_POLICY_VERSION,
    POLICY_VERSION,
    ArtifactEntry,
    IssueToPRReport,
    IssueToPRTask,
    RunManifest,
)


def render_issue_to_pr_markdown(report: IssueToPRReport) -> str:
    fix_outcome = report.fix.outcome.value if report.fix else "not_run"
    review_outcome = (
        report.review_repair.outcome.value if report.review_repair else "not_run"
    )
    lines = [
        f"# PRGuard Issue-to-PR run `{report.run_id}`",
        "",
        f"- Case: `{report.case_id}`",
        f"- Outcome: **{report.outcome.value}**",
        f"- Verdict: **{report.verdict.value}**",
        f"- Base commit: `{report.resolved_base_commit or 'unresolved'}`",
        f"- Fix stage: `{fix_outcome}`",
        f"- Review/repair stage: `{review_outcome}`",
        f"- Duration: {report.duration_seconds:.3f}s",
        "",
        "## Delivery",
        "",
    ]
    lines.append(
        f"- Final patch: `{report.final_patch.name}`"
        if report.final_patch
        else "- Final patch: None"
    )
    if report.error:
        lines.extend(["", "## Error", "", report.error])
    lines.append("")
    return "\n".join(lines)


def finalize_issue_to_pr_artifacts(
    run_directory: Path, task: IssueToPRTask, report: IssueToPRReport
) -> RunManifest:
    (run_directory / "issue-to-pr-task.json").write_bytes(
        canonical_json(task.model_dump(mode="json"))
    )
    (run_directory / "issue-to-pr-report.json").write_bytes(
        canonical_json(report.model_dump(mode="json"))
    )
    (run_directory / "issue-to-pr-report.md").write_text(
        render_issue_to_pr_markdown(report), encoding="utf-8"
    )
    entries: list[ArtifactEntry] = []
    for path in sorted(run_directory.rglob("*")):
        if not path.is_file() or path.name == "issue-to-pr-manifest.json":
            continue
        payload = path.read_bytes()
        entries.append(
            ArtifactEntry(
                path=path.relative_to(run_directory).as_posix(),
                sha256=sha256_bytes(payload),
                size_bytes=len(payload),
            )
        )
    manifest = RunManifest(
        policy_version=(
            f"{POLICY_VERSION}+{PATCH_POLICY_VERSION}+{ISSUE_TO_PR_WORKFLOW_VERSION}"
        ),
        run_id=report.run_id,
        case_id=report.case_id,
        resolved_base_commit=report.resolved_base_commit or task.base_commit,
        created_at=datetime.now(UTC),
        artifacts=entries,
        manifest_sha256="0" * 64,
    )
    payload = manifest.model_dump(mode="json", exclude={"manifest_sha256"})
    manifest = manifest.model_copy(
        update={"manifest_sha256": sha256_bytes(canonical_json(payload))}
    )
    (run_directory / "issue-to-pr-manifest.json").write_bytes(
        canonical_json(manifest.model_dump(mode="json"))
    )
    return manifest
