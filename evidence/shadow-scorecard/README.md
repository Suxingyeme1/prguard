# Shadow Reviewer routing scorecard

Frozen: 2026-09-02  
PRGuard: 0.10.0  
Policy: `review-routing-v1`

This package turns the existing routing and Reviewer-value evidence into one hash-bound,
evaluator-only scorecard. It is intentionally a three-case engineering check, not a benchmark or a
population-accuracy claim.

The two real-repository source Patches are evaluator-confirmed clean. The deterministic regression
fixture is defective: its candidate passed the configured narrow gate, the router selected Review
because an unchanged reachable regression test was uncovered, and the previously frozen live
Reviewer produced one confirmed incremental finding followed by one accepted repair.

`cases.json` contains only post-run evaluator labels and concise check summaries. It references
candidate Patches, routing JSON, and Reviewer evidence by SHA-256. The loader verifies those hashes,
the Patch/Base-Commit joins, `shadow` mode, and routing-policy version before computing counts.
Evaluator records live in `prguard.evaluation`, outside Agent-visible `prguard.schemas` task
contracts.

The result is deliberately conservative:

- false route: 1/2 clean accepted Fixes;
- false skip: 0/1 defective accepted Fix;
- paired Reviewer coverage: 1/3;
- one confirmed incremental finding and one repair round;
- selective activation: **not ready** because the two real-repository routing cases do not have
  same-Patch Reviewer observations and there is no labelled defective real-repository case.

`false block` is 0/0 in this joined set, not zero percent. The separate Humanize Reviewer-value
case remains valid evidence of one clean acceptance, but its Patch hash differs from the source-only
Humanize routing case, so the scorecard correctly refuses to join them.

Regenerate the two derived views with:

```bash
uv run python scripts/build_shadow_scorecard.py --format json
uv run python scripts/build_shadow_scorecard.py --format markdown
```

Verify all frozen bytes with:

```bash
uv run python scripts/verify_public_evidence.py
```
