"""Auditable artifacts for the review-to-controlled-repair workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from prguard.harness.artifacts import canonical_json, sha256_bytes
from prguard.schemas import (
    PATCH_POLICY_VERSION,
    POLICY_VERSION,
    REVIEW_REPAIR_WORKFLOW_VERSION,
    ArtifactEntry,
    ReviewRepairReport,
    ReviewRepairTask,
    RunManifest,
)


def render_review_repair_markdown(report: ReviewRepairReport) -> str:
    initial = report.initial_review
    findings = initial.review.submission.findings if initial and initial.review else []
    final_outcome = (
        report.final_verification.outcome.value if report.final_verification else "not_run"
    )
    lines = [
        f"# PRGuard review-repair run `{report.run_id}`",
        "",
        f"- Case: `{report.case_id}`",
        f"- Outcome: **{report.outcome.value}**",
        f"- Final verdict: **{report.verdict.value}**",
        f"- Base commit: `{report.resolved_base_commit or 'unresolved'}`",
        f"- Initial review: `{initial.verdict.value if initial else 'not_run'}`",
        f"- Final verification: `{final_outcome}`",
        f"- Duration: {report.duration_seconds:.3f}s",
        "",
        "## Initial findings",
        "",
    ]
    for finding in findings:
        anchor = f"{finding.file}:{finding.line}" if finding.line else finding.file
        lines.append(f"- **{finding.severity.value}** `{anchor}` — {finding.claim}")
        lines.append(f"  - Evidence: {finding.evidence}")
        lines.append(f"  - Verify: {finding.verification}")
    if not findings:
        lines.append("- None")
    lines.extend(["", "## Controlled repair", ""])
    if report.repair_proposal:
        lines.append(f"- Provider: `{report.repair_proposal.provider}`")
        lines.append(f"- Summary: {report.repair_proposal.proposal.summary}")
    elif report.repair_provider_failure:
        usage = report.repair_provider_failure.token_usage
        lines.append(f"- Provider failed: `{report.repair_provider_failure.provider}`")
        lines.append(f"- Partial tool calls: {len(report.repair_provider_failure.tool_calls)}")
        lines.append(f"- Partial tokens: {usage.input_tokens} input / {usage.output_tokens} output")
    else:
        lines.append("- Not attempted")
    lines.append(
        f"- Final patch: `{report.final_patch.name}`"
        if report.final_patch
        else "- Final patch: None"
    )
    if report.error:
        lines.extend(["", "## Error", "", report.error])
    lines.append("")
    return "\n".join(lines)


def finalize_review_repair_artifacts(
    run_directory: Path,
    task: ReviewRepairTask,
    report: ReviewRepairReport,
    candidate_patch: bytes,
) -> RunManifest:
    (run_directory / "review-repair-task.json").write_bytes(
        canonical_json(task.model_dump(mode="json"))
    )
    (run_directory / "review-repair-report.json").write_bytes(
        canonical_json(report.model_dump(mode="json"))
    )
    (run_directory / "review-repair-report.md").write_text(
        render_review_repair_markdown(report), encoding="utf-8"
    )
    (run_directory / "original-candidate.patch").write_bytes(candidate_patch)
    if report.repair_provider_failure:
        (run_directory / "repair-provider-failure.json").write_bytes(
            canonical_json(report.repair_provider_failure.model_dump(mode="json"))
        )
    entries: list[ArtifactEntry] = []
    for path in sorted(run_directory.rglob("*")):
        if not path.is_file() or path.name == "review-repair-manifest.json":
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
            f"{POLICY_VERSION}+{PATCH_POLICY_VERSION}+{REVIEW_REPAIR_WORKFLOW_VERSION}"
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
    (run_directory / "review-repair-manifest.json").write_bytes(
        canonical_json(manifest.model_dump(mode="json"))
    )
    return manifest
