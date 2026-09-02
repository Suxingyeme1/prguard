# Shadow Reviewer routing scorecard

Frozen: 2026-09-02
PRGuard: 0.10.2
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

All three routes now have same-Base, same-Patch Reviewer observations. Humanize was accepted with
one confirmed nonblocking test-gap finding; PrettyTable was rejected and then repaired once. The
result remains deliberately conservative:

- false route: 1/1 clean accepted Fix;
- false skip: 1/2 defective accepted Fixes;
- paired Reviewer coverage: 3/3;
- three confirmed incremental findings and two repair rounds;
- false block: 0/1 clean effective Review;
- selective activation: **not ready** because one frozen `skip` is evaluator-confirmed defective.

The earlier Humanize Reviewer-value case remains valid evidence for a different source-and-test
Patch. The new paired run uses the exact source-only Patch selected by the frozen routing case, so
the scorecard can join it without weakening its hash checks. The observed fractions are case
counts, not calibrated population rates.

Regenerate the two derived views with:

```bash
uv run python scripts/build_shadow_scorecard.py --format json
uv run python scripts/build_shadow_scorecard.py --format markdown
```

Verify all frozen bytes with:

```bash
uv run python scripts/verify_public_evidence.py
```
