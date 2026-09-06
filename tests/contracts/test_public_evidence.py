import json
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


def test_public_filelock_holdout_artifact_hashes() -> None:
    root = Path(__file__).resolve().parents[2] / "evidence" / "filelock-606-holdout"
    assert verify_evidence(root) == 2


def test_public_locust_holdout_is_hash_bound_and_still_pending() -> None:
    root = Path(__file__).resolve().parents[2] / "evidence" / "locust-3207-holdout"
    assert verify_evidence(root) == 2
    summary = json.loads((root / "case-summary.json").read_text(encoding="utf-8"))
    assert summary["live_implementer"]["status"] == "pending"
    assert summary["independent_reviewer"]["status"] == "pending"
    assert summary["sealed_evaluator_commitment"] == {
        "sha256": "763d7082e4cc35990ad03ddc8efbcb7a1673c006e40bc537d6c5fa03669960c1",
        "body_published": False,
        "network_required": False,
        "external_service_required": False,
        "base_python_3_12": "passed",
        "base_python_3_13": "failed",
    }
    assert [lane["runtime"] for lane in summary["public_base_gates"]] == [
        "CPython 3.12.13",
        "CPython 3.13.12",
    ]
    assert all(lane["manifest_verified"] for lane in summary["public_base_gates"])


def test_public_evidence_rejects_hash_mismatch(tmp_path: Path) -> None:
    (tmp_path / "sample.patch").write_text("diff", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        '{"schema_version":"prguard-public-evidence-1","cases":'
        '[{"case_id":"case","patch":"sample.patch","patch_sha256":"bad"}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_evidence(tmp_path)
