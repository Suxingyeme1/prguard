from pathlib import Path

from prguard.evaluation import (
    build_shadow_scorecard,
    load_shadow_evaluation,
    render_shadow_scorecard_markdown,
)


def _evidence_root() -> Path:
    return Path(__file__).resolve().parents[2] / "evidence"


def test_frozen_shadow_scorecard_is_reproducible() -> None:
    root = _evidence_root()
    dataset, observations = load_shadow_evaluation(
        root,
        "shadow-scorecard/cases.json",
    )
    scorecard = build_shadow_scorecard(dataset, observations)

    expected_json = root / "shadow-scorecard" / "scorecard.json"
    expected_markdown = root / "shadow-scorecard" / "scorecard.md"
    assert scorecard.model_dump_json(indent=2) + "\n" == expected_json.read_text(
        encoding="utf-8"
    )
    assert render_shadow_scorecard_markdown(scorecard) == expected_markdown.read_text(
        encoding="utf-8"
    )


def test_scorecard_keeps_counts_and_denominators_explicit() -> None:
    dataset, observations = load_shadow_evaluation(
        _evidence_root(),
        "shadow-scorecard/cases.json",
    )
    scorecard = build_shadow_scorecard(dataset, observations)

    assert scorecard.case_count == 3
    assert scorecard.false_routes.model_dump() == {
        "numerator": 1,
        "denominator": 2,
        "rate": 0.5,
    }
    assert scorecard.false_skips.model_dump() == {
        "numerator": 0,
        "denominator": 1,
        "rate": 0.0,
    }
    assert scorecard.false_blocks.model_dump() == {
        "numerator": 0,
        "denominator": 0,
        "rate": None,
    }
    assert scorecard.defective_cases_caught_by_reviewer.numerator == 1
    assert scorecard.confirmed_incremental_findings == 1
    assert scorecard.selective_activation_ready is False
    assert scorecard.activation_blockers == [
        "paired Reviewer outcome coverage is 1/3",
        "no evaluator-confirmed defective real-repository case",
    ]
