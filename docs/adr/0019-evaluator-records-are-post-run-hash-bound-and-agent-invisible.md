# ADR 0019: Keep evaluator records post-run, hash-bound, and Agent-invisible

Status: Accepted (2026-09-02)

## Context

Reviewer routing cannot be judged from routing scores alone. False Route, False Skip, False Block,
and incremental Reviewer findings require evaluator labels and dispositions that are unavailable to
the product at decision time. If those values enter Fix or Review tasks, they leak the answer to an
Agent. If reports join records only by a human-readable case name, results from different Base
Commits or candidate Patches can be accidentally combined.

The first evidence set is intentionally small. It should expose missing observations and invalid
denominators rather than grow into a benchmark platform or manufacture a favorable rate.

## Decision

Keep evaluator models in `prguard.evaluation`, outside the public `prguard.schemas` namespace used
by Agent tasks. Apply labels only after the Fix, routing, and optional Reviewer run have completed.
Fix and Review schemas retain `extra="forbid"`, so an evaluator field cannot be silently accepted.

The frozen dataset references candidate Patches, routing JSON, and optional Reviewer evidence by
evidence-root-relative path and SHA-256. Loading rejects absolute/traversing paths, symlinks, hash
mismatches, non-Shadow routes, policy-version mismatches, and routing/Patch mismatches. Reviewer
evidence may join only when its Base Commit and candidate Patch SHA-256 equal the routing record.

Derive all counts in code. Publish numerator and denominator for False Route, False Skip, False
Block, Reviewer coverage, and defective cases caught. A zero denominator produces no rate. Preserve
observed Reviewer Token use, latency, repair rounds, and confirmed incremental findings. The
scorecard also emits explicit blockers that keep selective activation opt-in when paired coverage
or real-repository defect evidence is missing.

Generated JSON and Markdown are frozen alongside their input records under a separately hashed
public evidence manifest. Tests regenerate both views byte-for-byte and reject tampered routes,
path traversal, and cross-Patch Reviewer joins.

## Consequences

The scorecard can be replayed without an API key and cannot silently combine unrelated model runs.
It makes incomplete and adverse evidence visible. The first same-Patch real-repository Reviewer run
reclassified a previously clean-labelled PrettyTable Patch as defective and converted its `skip`
recommendation into a confirmed False Skip. The scorecard therefore blocks selective-by-default
deployment even if all remaining paired observations are later collected.

Evaluator dispositions remain human judgments, and SHA-256 provides integrity rather than identity
or remote attestation. Expanding the case set still requires disciplined manual labelling and
same-Patch Reviewer runs; this ADR does not claim statistical calibration.
