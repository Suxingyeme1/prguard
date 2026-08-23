"""Verify the path-free real-repository evidence package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def verify_evidence(evidence_root: Path) -> int:
    manifest_path = evidence_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest.get("cases")
    if manifest.get("schema_version") != "prguard-public-evidence-1" or not isinstance(cases, list):
        raise ValueError("unsupported or malformed public evidence manifest")

    verified = 0
    for case in cases:
        relative = Path(case["patch"])
        if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
            raise ValueError(f"unsafe evidence path: {relative}")
        payload = (evidence_root / relative).read_bytes()
        actual = hashlib.sha256(payload).hexdigest()
        if actual != case["patch_sha256"]:
            raise ValueError(f"hash mismatch: {relative}")
        verified += 1
        print(f"verified {case['case_id']}: {actual}")
    return verified


def main() -> int:
    evidence = Path(__file__).resolve().parents[1] / "evidence"
    roots = [evidence / "real-repositories", evidence / "reviewer-value"]
    count = sum(verify_evidence(root) for root in roots)
    print(f"public evidence verified: {count} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
