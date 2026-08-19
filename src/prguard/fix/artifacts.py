"""Auditable Issue-to-Patch run artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from prguard.harness.artifacts import canonical_json, sha256_bytes
from prguard.schemas import (
    PATCH_POLICY_VERSION,
    POLICY_VERSION,
    ArtifactEntry,
    FixReport,
    FixTask,
    RunManifest,
)


def render_fix_markdown(report: FixReport) -> str:
    lines = [
        f"# PRGuard fix run `{report.run_id}`",
        "",
        f"- Case: `{report.case_id}`",
        f"- Outcome: **{report.outcome.value}**",
        f"- Base commit: `{report.resolved_base_commit or 'unresolved'}`",
        f"- Attempts: {len(report.attempts)}",
        f"- Duration: {report.duration_seconds:.3f}s",
        "",
        "## Attempts",
        "",
    ]
    for attempt in report.attempts:
        verification = attempt.verification
        outcome = verification.outcome.value if verification else "not_run"
        provider = attempt.proposal.provider if attempt.proposal else "none"
        lines.append(
            f"- Attempt {attempt.attempt}: provider `{provider}`, verification `{outcome}`"
        )
        if attempt.error:
            lines.append(f"  - Error: {attempt.error}")
    lines.extend(["", "## Final patch", ""])
    lines.append(f"- `{report.final_patch.name}`" if report.final_patch else "- None")
    lines.append("")
    return "\n".join(lines)


def finalize_fix_artifacts(run_directory: Path, task: FixTask, report: FixReport) -> RunManifest:
    (run_directory / "fix-task.json").write_bytes(canonical_json(task.model_dump(mode="json")))
    (run_directory / "fix-report.json").write_bytes(canonical_json(report.model_dump(mode="json")))
    (run_directory / "fix-report.md").write_text(render_fix_markdown(report), encoding="utf-8")
    entries: list[ArtifactEntry] = []
    for path in sorted(run_directory.rglob("*")):
        if not path.is_file() or path.name == "fix-manifest.json":
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
        policy_version=f"{POLICY_VERSION}+{PATCH_POLICY_VERSION}",
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
    (run_directory / "fix-manifest.json").write_bytes(
        canonical_json(manifest.model_dump(mode="json"))
    )
    return manifest
