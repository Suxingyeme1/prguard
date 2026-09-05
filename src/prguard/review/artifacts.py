"""Auditable Independent Reviewer artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from prguard.harness.artifacts import canonical_json, sha256_bytes
from prguard.schemas import ArtifactEntry, ReviewReport, ReviewTask, RunManifest


def render_review_markdown(report: ReviewReport) -> str:
    lines = [
        f"# PRGuard review run `{report.run_id}`",
        "",
        f"- Case: `{report.case_id}`",
        f"- Outcome: **{report.outcome.value}**",
        f"- Verdict: **{report.verdict.value}**",
        f"- Base commit: `{report.resolved_base_commit or 'unresolved'}`",
        f"- Base readiness: `{report.readiness.outcome.value if report.readiness else 'not_run'}`",
        f"- Duration: {report.duration_seconds:.3f}s",
        "",
        "## Findings",
        "",
    ]
    findings = report.review.submission.findings if report.review else []
    for finding in findings:
        anchor = f"{finding.file}:{finding.line}" if finding.line else finding.file
        lines.append(f"- **{finding.severity.value}** `{anchor}` — {finding.claim}")
        lines.append(f"  - Evidence: {finding.evidence}")
        lines.append(f"  - Verify: {finding.verification}")
    if not findings:
        lines.append("- None")
    if report.compatibility_signals:
        lines.extend(["", "## Deterministic compatibility signals", ""])
        lines.extend(f"- {signal}" for signal in report.compatibility_signals)
    if report.provider_failure:
        usage = report.provider_failure.token_usage
        lines.extend(
            [
                "",
                "## Partial provider evidence",
                "",
                f"- Provider: `{report.provider_failure.provider}`",
                f"- Tool calls: {len(report.provider_failure.tool_calls)}",
                f"- Tokens: {usage.input_tokens} input / {usage.output_tokens} output",
            ]
        )
    if report.error:
        lines.extend(["", "## Error", "", report.error])
    lines.append("")
    return "\n".join(lines)


def finalize_review_artifacts(
    run_directory: Path, task: ReviewTask, report: ReviewReport, patch_bytes: bytes
) -> RunManifest:
    (run_directory / "review-task.json").write_bytes(canonical_json(task.model_dump(mode="json")))
    (run_directory / "review-report.json").write_bytes(
        canonical_json(report.model_dump(mode="json"))
    )
    (run_directory / "review-report.md").write_text(
        render_review_markdown(report), encoding="utf-8"
    )
    (run_directory / "candidate.patch").write_bytes(patch_bytes)
    if report.review:
        (run_directory / "review-envelope.json").write_bytes(
            canonical_json(report.review.model_dump(mode="json"))
        )
    if report.provider_failure:
        (run_directory / "provider-failure.json").write_bytes(
            canonical_json(report.provider_failure.model_dump(mode="json"))
        )
    entries: list[ArtifactEntry] = []
    for path in sorted(run_directory.rglob("*")):
        if not path.is_file() or path.name == "review-manifest.json":
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
        policy_version="review-readonly-v1",
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
    (run_directory / "review-manifest.json").write_bytes(
        canonical_json(manifest.model_dump(mode="json"))
    )
    return manifest
