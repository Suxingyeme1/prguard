from __future__ import annotations

import hashlib
import json
from pathlib import Path

from prguard.schemas import ReviewRoutingResult


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_within(anchor: Path, boundary: Path, relative: str) -> Path:
    path = (anchor / relative).resolve()
    path.relative_to(boundary.resolve())
    return path


def test_routing_v2_replay_binds_same_patch_and_frozen_routes() -> None:
    evidence_root = Path(__file__).resolve().parents[2] / "evidence"
    replay_root = evidence_root / "review-routing-v2"
    summary = json.loads((replay_root / "replay-summary.json").read_text(encoding="utf-8"))

    assert summary["schema_version"] == "prguard-routing-policy-replay-1"
    assert summary["baseline_policy"] == "review-routing-v1"
    assert summary["candidate_policy"] == "review-routing-v2"
    assert summary["activation_decision"] == "not_ready"
    assert summary["activation_blockers"]

    for case in summary["cases"]:
        baseline_path = _resolve_within(
            replay_root,
            evidence_root,
            case["baseline_routing_artifact"],
        )
        candidate_path = _resolve_within(
            replay_root,
            replay_root,
            case["candidate_routing_artifact"],
        )

        assert _sha256(baseline_path) == case["baseline_routing_sha256"]
        assert _sha256(candidate_path) == case["candidate_routing_sha256"]

        baseline = ReviewRoutingResult.model_validate_json(baseline_path.read_text())
        candidate = ReviewRoutingResult.model_validate_json(candidate_path.read_text())

        assert baseline.policy_version == summary["baseline_policy"]
        assert candidate.policy_version == summary["candidate_policy"]
        assert baseline.resolved_base_commit == candidate.resolved_base_commit
        assert baseline.patch_sha256 == candidate.patch_sha256
        assert candidate.patch_sha256 == case["candidate_patch_sha256"]
        assert baseline.recommended_route.value == case["baseline_recommendation"]
        assert candidate.recommended_route.value == case["candidate_recommendation"]
        assert candidate.score == case["candidate_score"]

        baseline_factors = {factor.code for factor in baseline.factors}
        candidate_factors = {factor.code for factor in candidate.factors}
        assert sorted(candidate_factors - baseline_factors) == case["changed_factors"]
