import json
from pathlib import Path

from prguard.schemas import ReviewRoutingResult
from scripts.verify_public_evidence import verify_evidence

EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / "evidence"
    / "review-routing-v4-validation"
)


def _json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def _routing(name: str) -> ReviewRoutingResult:
    return ReviewRoutingResult.model_validate_json(
        (EVIDENCE / name).read_text(encoding="utf-8")
    )


def test_routing_v4_validation_artifacts_are_hash_bound() -> None:
    assert verify_evidence(EVIDENCE) == 9


def test_v4_preserves_clean_skip_and_defective_review() -> None:
    dotenv_v3 = _routing("dotenv-routing-v3.json")
    dotenv_v4 = _routing("dotenv-routing-v4.json")
    click_v3 = _routing("click-routing-v3.json")
    click_v4 = _routing("click-routing-v4.json")

    assert dotenv_v3.patch_sha256 == dotenv_v4.patch_sha256
    assert dotenv_v3.recommended_route.value == "skip"
    assert dotenv_v4.recommended_route.value == "skip"
    assert dotenv_v4.score == 0

    assert click_v3.patch_sha256 == click_v4.patch_sha256
    assert click_v3.recommended_route.value == "review"
    assert click_v4.recommended_route.value == "review"
    assert click_v4.score == 18
    assert {factor.code for factor in click_v4.factors} == {
        "analysis_incomplete",
        "tests_or_gate_changed",
        "medium_patch",
    }


def test_unfiltered_full_suite_dominates_changed_test_replay() -> None:
    click_v3 = _routing("click-routing-v3.json")
    click_v4 = _routing("click-routing-v4.json")

    assert click_v3.pytest_scope == "targeted"
    assert click_v3.pytest_targets == ["tests/test_defaults.py"]
    assert click_v4.pytest_scope == "full"
    assert click_v4.pytest_targets == []
    assert "no_explicit_unchanged_test_evidence" in {
        factor.code for factor in click_v3.factors
    }
    assert "no_explicit_unchanged_test_evidence" not in {
        factor.code for factor in click_v4.factors
    }


def test_evaluator_and_independent_review_agree_on_click_defect() -> None:
    evaluator = _json("click-evaluator-check.json")
    finding = _json("click-review-finding.json")
    summary = _json("validation-summary.json")

    assert evaluator["agent_visible"] is False
    assert evaluator["classification"] == "defective"
    assert evaluator["base"]["extension_point_honored"] is True  # type: ignore[index]
    assert evaluator["candidate"]["extension_point_honored"] is False  # type: ignore[index]
    assert finding["verdict"] == "request_changes"
    assert finding["finding_count"] == 1
    assert finding["finding"]["file"] == "src/click/core.py"  # type: ignore[index]
    assert finding["finding"]["symbol"] == "click.core.Parameter.get_default"  # type: ignore[index]
    assert summary["activation_decision"] == "not_ready"
    assert summary["observed_counts"]["false_skips"] == 0  # type: ignore[index]
