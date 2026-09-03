from __future__ import annotations

import hashlib
import json
from pathlib import Path

from prguard.schemas import ReviewRoutingResult


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_routing_v3_holdout_is_hash_bound_and_not_activated() -> None:
    root = (
        Path(__file__).resolve().parents[2]
        / "evidence"
        / "review-routing-v3-holdout"
    )
    summary = json.loads((root / "holdout-summary.json").read_text(encoding="utf-8"))
    evaluator = json.loads(
        (root / "dotenv-evaluator-check.json").read_text(encoding="utf-8")
    )
    regression = json.loads(
        (root / "orchestration-regression.json").read_text(encoding="utf-8")
    )

    assert summary["baseline_policy"] == "review-routing-v2"
    assert summary["candidate_policy"] == "review-routing-v3"
    assert summary["activation_decision"] == "not_ready"
    assert summary["activation_blockers"]

    routes: dict[str, tuple[ReviewRoutingResult, ReviewRoutingResult]] = {}
    for case in summary["cases"]:
        baseline_path = (root / case["baseline_routing_artifact"]).resolve()
        candidate_path = (root / case["candidate_routing_artifact"]).resolve()
        baseline_path.relative_to(root.resolve())
        candidate_path.relative_to(root.resolve())
        baseline = ReviewRoutingResult.model_validate_json(baseline_path.read_bytes())
        candidate = ReviewRoutingResult.model_validate_json(candidate_path.read_bytes())

        assert baseline.policy_version == summary["baseline_policy"]
        assert candidate.policy_version == summary["candidate_policy"]
        assert baseline.resolved_base_commit == candidate.resolved_base_commit
        assert baseline.resolved_base_commit == case["resolved_base_commit"]
        assert baseline.patch_sha256 == candidate.patch_sha256
        assert candidate.patch_sha256 == case["candidate_patch_sha256"]
        assert baseline.fix_manifest_sha256 == candidate.fix_manifest_sha256
        assert (
            baseline.verification_manifest_sha256
            == candidate.verification_manifest_sha256
        )
        assert baseline.recommended_route.value == case["baseline_recommendation"]
        assert candidate.recommended_route.value == case["candidate_recommendation"]
        assert baseline.score == case["baseline_score"]
        assert candidate.score == case["candidate_score"]
        assert case["evaluator_label"] == "clean"
        assert len(case["reviewer"]["review_report_sha256"]) == 64
        assert len(case["reviewer"]["review_manifest_file_sha256"]) == 64
        routes[case["case_id"]] = baseline, candidate

    inflect_v2, inflect_v3 = routes["inflect-242-source-only"]
    assert [factor.code for factor in inflect_v2.factors] == [
        factor.code for factor in inflect_v3.factors
    ]

    dotenv_v2, dotenv_v3 = routes["python-dotenv-638-source-only"]
    assert dotenv_v2.pytest_scope == dotenv_v3.pytest_scope == "full"
    assert dotenv_v2.covered_unchanged_tests == []
    assert dotenv_v3.covered_unchanged_tests == [
        "tests/test_cli.py",
        "tests/test_ipython.py",
        "tests/test_lib.py",
        "tests/test_main.py",
    ]
    assert {factor.code for factor in dotenv_v2.factors} == {
        "no_explicit_unchanged_test_evidence",
        "related_tests_not_explicitly_covered",
    }
    assert dotenv_v3.factors == []

    assert evaluator["resolved_base_commit"] == dotenv_v3.resolved_base_commit
    assert evaluator["candidate_patch_sha256"] == dotenv_v3.patch_sha256
    assert evaluator["hidden_from_agents"] is True
    assert evaluator["base_observation"] == {
        "parse_call_count": 2,
        "issue_reproduced": True,
    }
    assert evaluator["candidate_observation"] == {
        "parse_call_count": 1,
        "issue_resolved": True,
    }
    assert regression["provider_tokens"] == 0
    assert regression["model_call_started"] is False
    assert regression["correction"].startswith("Version 0.10.4")

    observed = summary["observed_clean_case_counts"]
    assert observed["cases"] == len(summary["cases"])
    assert observed["v2_review_recommendations"] == sum(
        case["baseline_recommendation"] == "review" for case in summary["cases"]
    )
    assert observed["v3_review_recommendations"] == sum(
        case["candidate_recommendation"] == "review" for case in summary["cases"]
    )
    assert _sha256(root / "dotenv-routing-v3.json") == (
        "af1f3735224da0c921339574ecdbef8deacdeef7f7f7f44770887d642e2974ac"
    )
