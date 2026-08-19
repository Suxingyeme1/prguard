"""Canonical run artifacts and SHA-256 manifest verification."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prguard.harness.errors import ArtifactIntegrityError
from prguard.schemas import (
    HARNESS_VERSION,
    POLICY_VERSION,
    ArtifactEntry,
    HarnessReport,
    RunManifest,
    Task,
)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_markdown(report: HarnessReport) -> str:
    lines = [
        f"# PRGuard run `{report.run_id}`",
        "",
        f"- Case: `{report.case_id}`",
        f"- Outcome: **{report.outcome.value}**",
        f"- Base commit: `{report.resolved_base_commit or 'unresolved'}`",
        f"- Duration: {report.duration_seconds:.3f}s",
        f"- Patch applied: {report.patch.applied}",
        "",
        "## Verification",
        "",
        "| # | Kind | Command | Exit | Timeout | Passed | Duration |",
        "|---:|---|---|---:|---|---|---:|",
    ]
    for result in report.commands:
        command = " ".join(result.argv).replace("|", "\\|")
        lines.append(
            f"| {result.command_index} | {result.kind} | `{command}` | "
            f"{result.exit_code if result.exit_code is not None else '-'} | "
            f"{result.timed_out} | {result.passed} | {result.duration_seconds:.3f}s |"
        )
    lines.extend(["", "## Changed files", ""])
    lines.extend(f"- `{path}`" for path in report.changed_files)
    if not report.changed_files:
        lines.append("- None")
    lines.extend(["", "## Policy violations", ""])
    for violation in report.policy_violations:
        paths = ", ".join(f"`{path}`" for path in violation.paths) or "None"
        lines.append(f"- **{violation.code}**: {violation.message} ({paths})")
    if not report.policy_violations:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def create_run_directory(self, run_id: str) -> Path:
        run_directory = self.root / run_id
        run_directory.mkdir(parents=True, exist_ok=False)
        return run_directory

    def finalize(
        self,
        *,
        run_directory: Path,
        task: Task,
        report: HarnessReport,
        final_diff: str,
        patch_bytes: bytes | None,
    ) -> RunManifest:
        payloads: dict[str, bytes] = {
            "task.json": canonical_json(task.model_dump(mode="json")),
            "report.json": canonical_json(report.model_dump(mode="json")),
            "report.md": render_markdown(report).encode("utf-8"),
            "final.diff": final_diff.encode("utf-8"),
        }
        if patch_bytes is not None:
            payloads["candidate.patch"] = patch_bytes
        entries: list[ArtifactEntry] = []
        for name, payload in sorted(payloads.items()):
            path = run_directory / name
            path.write_bytes(payload)
            entries.append(
                ArtifactEntry(path=name, sha256=sha256_bytes(payload), size_bytes=len(payload))
            )
        manifest = RunManifest(
            schema_version=report.schema_version,
            harness_version=HARNESS_VERSION,
            policy_version=POLICY_VERSION,
            run_id=report.run_id,
            case_id=report.case_id,
            resolved_base_commit=report.resolved_base_commit or task.base_commit,
            created_at=datetime.now(UTC),
            artifacts=entries,
            manifest_sha256="0" * 64,
        )
        manifest_payload = manifest.model_dump(mode="json", exclude={"manifest_sha256"})
        manifest = manifest.model_copy(
            update={"manifest_sha256": sha256_bytes(canonical_json(manifest_payload))}
        )
        (run_directory / "manifest.json").write_bytes(
            canonical_json(manifest.model_dump(mode="json"))
        )
        return manifest


def verify_manifest(manifest_path: Path, *, reject_extra_files: bool = True) -> RunManifest:
    manifest_path = manifest_path.expanduser().resolve()
    try:
        manifest = RunManifest.model_validate_json(manifest_path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ArtifactIntegrityError(f"invalid manifest: {exc}") from exc
    payload = manifest.model_dump(mode="json", exclude={"manifest_sha256"})
    if sha256_bytes(canonical_json(payload)) != manifest.manifest_sha256:
        raise ArtifactIntegrityError("manifest payload hash mismatch")
    root = manifest_path.parent
    expected = {manifest_path.name}
    for entry in manifest.artifacts:
        relative = Path(entry.path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ArtifactIntegrityError(f"unsafe artifact path: {entry.path}")
        path = root / relative
        expected.add(relative.as_posix())
        if not path.is_file():
            raise ArtifactIntegrityError(f"missing artifact: {entry.path}")
        if path.stat().st_size != entry.size_bytes or sha256_file(path) != entry.sha256:
            raise ArtifactIntegrityError(f"artifact hash mismatch: {entry.path}")
    if reject_extra_files:
        actual = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        extras = sorted(actual - expected)
        if extras:
            raise ArtifactIntegrityError(f"unlisted artifact files: {extras}")
    return manifest


def load_replay_task(manifest_path: Path, *, repository: Path | None = None) -> Task:
    """Reconstruct a Task from verified artifacts without trusting external patch bytes."""
    manifest_path = manifest_path.expanduser().resolve()
    manifest = verify_manifest(manifest_path)
    root = manifest_path.parent
    try:
        payload = json.loads((root / "task.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactIntegrityError(f"unable to load replay task: {exc}") from exc
    if repository is not None:
        payload["repository"] = repository.expanduser().resolve()
    archived_patch = root / "candidate.patch"
    payload["candidate_patch"] = archived_patch if archived_patch.exists() else None
    task = Task.model_validate(payload)
    if task.base_commit != manifest.resolved_base_commit:
        raise ArtifactIntegrityError("task base commit does not match manifest")
    return task
