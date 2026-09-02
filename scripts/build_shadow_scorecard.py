"""Print the frozen evaluator-only Shadow Reviewer scorecard."""

from __future__ import annotations

import argparse
from pathlib import Path

from prguard.evaluation import (
    build_shadow_scorecard,
    load_shadow_evaluation,
    render_shadow_scorecard_markdown,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evidence",
    )
    parser.add_argument(
        "--dataset",
        default="shadow-scorecard/cases.json",
        help="evidence-root-relative evaluator dataset",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)

    dataset, observations = load_shadow_evaluation(args.evidence_root, args.dataset)
    scorecard = build_shadow_scorecard(dataset, observations)
    if args.format == "json":
        print(scorecard.model_dump_json(indent=2))
    else:
        print(render_shadow_scorecard_markdown(scorecard), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
