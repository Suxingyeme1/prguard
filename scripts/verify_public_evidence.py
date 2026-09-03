"""Verify the path-free real-repository evidence package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def verify_evidence(evidence_root: Path) -> int:
    manifest_path = evidence_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = manifest.get("schema_version")
    if version == "prguard-public-evidence-1":
        cases = manifest.get("cases")
        if not isinstance(cases, list):
            raise ValueError("unsupported or malformed public evidence manifest")
        artifacts = []
        for case in cases:
            artifacts.append(
                {
                    "label": case["case_id"],
                    "path": case["patch"],
                    "sha256": case["patch_sha256"],
                }
            )
            candidate = case.get("candidate_patch")
            if candidate is not None and candidate != case["patch"]:
                artifacts.append(
                    {
                        "label": f"{case['case_id']}-candidate",
                        "path": candidate,
                        "sha256": case["candidate_patch_sha256"],
                    }
                )
    elif version == "prguard-public-artifacts-1":
        values = manifest.get("artifacts")
        if not isinstance(values, list):
            raise ValueError("unsupported or malformed public evidence manifest")
        artifacts = [
            {
                "label": artifact["path"],
                "path": artifact["path"],
                "sha256": artifact["sha256"],
                "size_bytes": artifact["size_bytes"],
            }
            for artifact in values
        ]
    else:
        raise ValueError("unsupported or malformed public evidence manifest")

    verified = 0
    for artifact in artifacts:
        relative = Path(artifact["path"])
        if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
            raise ValueError(f"unsafe evidence path: {relative}")
        payload = (evidence_root / relative).read_bytes()
        actual = hashlib.sha256(payload).hexdigest()
        if actual != artifact["sha256"]:
            raise ValueError(f"hash mismatch: {relative}")
        expected_size = artifact.get("size_bytes")
        if expected_size is not None and len(payload) != expected_size:
            raise ValueError(f"size mismatch: {relative}")
        verified += 1
        print(f"verified {artifact['label']}: {actual}")
    return verified


def main() -> int:
    evidence = Path(__file__).resolve().parents[1] / "evidence"
    roots = [
        evidence / "real-repositories",
        evidence / "reviewer-value",
        evidence / "navigation-hardening",
        evidence / "call-graph-hardening",
        evidence / "selective-routing",
        evidence / "shadow-scorecard",
        evidence / "review-routing-v2",
        evidence / "review-routing-v3-holdout",
        evidence / "review-routing-v4-validation",
    ]
    count = sum(verify_evidence(root) for root in roots)
    print(f"public evidence verified: {count} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
