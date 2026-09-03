from pathlib import Path

import pytest

from scripts.verify_public_evidence import verify_evidence


def test_public_real_repository_evidence_hashes() -> None:
    root = Path(__file__).resolve().parents[2] / "evidence" / "real-repositories"
    assert verify_evidence(root) == 3


def test_public_reviewer_value_evidence_hashes() -> None:
    root = Path(__file__).resolve().parents[2] / "evidence" / "reviewer-value"
    assert verify_evidence(root) == 7


def test_public_navigation_hardening_artifacts_hashes() -> None:
    root = Path(__file__).resolve().parents[2] / "evidence" / "navigation-hardening"
    assert verify_evidence(root) == 3


def test_public_call_graph_hardening_artifacts_hashes() -> None:
    root = Path(__file__).resolve().parents[2] / "evidence" / "call-graph-hardening"
    assert verify_evidence(root) == 2


def test_public_selective_routing_artifacts_hashes() -> None:
    root = Path(__file__).resolve().parents[2] / "evidence" / "selective-routing"
    assert verify_evidence(root) == 6


def test_public_shadow_scorecard_artifact_hashes() -> None:
    root = Path(__file__).resolve().parents[2] / "evidence" / "shadow-scorecard"
    assert verify_evidence(root) == 6


def test_public_review_routing_v2_artifact_hashes() -> None:
    root = Path(__file__).resolve().parents[2] / "evidence" / "review-routing-v2"
    assert verify_evidence(root) == 5


def test_public_review_routing_v3_holdout_artifact_hashes() -> None:
    root = (
        Path(__file__).resolve().parents[2]
        / "evidence"
        / "review-routing-v3-holdout"
    )
    assert verify_evidence(root) == 8


def test_public_review_routing_v4_validation_artifact_hashes() -> None:
    root = (
        Path(__file__).resolve().parents[2]
        / "evidence"
        / "review-routing-v4-validation"
    )
    assert verify_evidence(root) == 9


def test_public_click_controlled_repair_artifact_hashes() -> None:
    root = Path(__file__).resolve().parents[2] / "evidence" / "click-controlled-repair"
    assert verify_evidence(root) == 4


def test_public_evidence_rejects_hash_mismatch(tmp_path: Path) -> None:
    (tmp_path / "sample.patch").write_text("diff", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        '{"schema_version":"prguard-public-evidence-1","cases":'
        '[{"case_id":"case","patch":"sample.patch","patch_sha256":"bad"}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_evidence(tmp_path)
