from pathlib import Path

import pytest

from scripts.verify_public_evidence import verify_evidence


def test_public_real_repository_evidence_hashes() -> None:
    root = Path(__file__).resolve().parents[2] / "evidence" / "real-repositories"
    assert verify_evidence(root) == 3


def test_public_reviewer_value_evidence_hashes() -> None:
    root = Path(__file__).resolve().parents[2] / "evidence" / "reviewer-value"
    assert verify_evidence(root) == 2


def test_public_evidence_rejects_hash_mismatch(tmp_path: Path) -> None:
    (tmp_path / "sample.patch").write_text("diff", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        '{"schema_version":"prguard-public-evidence-1","cases":'
        '[{"case_id":"case","patch":"sample.patch","patch_sha256":"bad"}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_evidence(tmp_path)
