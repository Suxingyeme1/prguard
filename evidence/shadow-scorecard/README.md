# Shadow Reviewer routing scorecard

Frozen: 2026-09-02
PRGuard: 0.10.1
Policy: `review-routing-v1`

This package turns the existing routing and Reviewer-value evidence into one hash-bound,
evaluator-only scorecard. It is intentionally a three-case engineering check, not a benchmark or a
population-accuracy claim.

The two real-repository source Patches initially passed their targeted and wider existing test
suites. Humanize remains evaluator-confirmed clean. PrettyTable did not: an exact-Patch live Review
identified that stale parser width state adds an empty column to a later, narrower table. A paired
Base/Candidate evaluator check confirmed the regression. The deterministic normalization fixture
is the second defective case; its Reviewer finding led to one accepted repair.

`cases.json` contains only post-run evaluator labels and concise check summaries. It references
candidate Patches, routing JSON, evaluator checks, and Reviewer evidence by SHA-256. The loader
verifies those hashes, the Patch/Base-Commit joins, `shadow` mode, and routing-policy version before
computing counts.
Evaluator records live in `prguard.evaluation`, outside Agent-visible `prguard.schemas` task
contracts.

The result is deliberately conservative:

- false route: 1/1 clean accepted Fix;
- false skip: 1/2 defective accepted Fixes;
- paired Reviewer coverage: 2/3;
- two confirmed incremental findings and one repair round;
- selective activation: **not ready** because one frozen `skip` is now evaluator-confirmed
  defective and Humanize still lacks a same-Patch Reviewer observation.

`false block` is 0/0 in this joined set, not zero percent. The separate Humanize Reviewer-value
case remains valid evidence of one clean acceptance, but its Patch hash differs from the source-only
Humanize routing case, so the scorecard correctly refuses to join them. The observed fractions are
case counts, not calibrated population rates.

Regenerate the two derived views with:

```bash
uv run python scripts/build_shadow_scorecard.py --format json
uv run python scripts/build_shadow_scorecard.py --format markdown
```

Verify all frozen bytes with:

```bash
uv run python scripts/verify_public_evidence.py
```
