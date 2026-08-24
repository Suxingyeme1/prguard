# ADR 0018: Make Reviewer routing deterministic, shadowable, and fail-closed

Status: Accepted (2026-08-23)

## Context

An Independent Reviewer can find a regression that passes an incomplete verification gate, but a
clean review also adds provider cost and latency. Running it for every accepted Fix preserves the
strongest current quality posture; skipping it unconditionally discards the independent context
that the system was built to provide. A selective policy therefore needs a measurable deployment
path, exact evidence binding, and a conservative response when its static analysis is uncertain.

Routing is an orchestration decision, not another Agent role. Letting the Implementer or Reviewer
decide whether review is necessary would make the decision probabilistic, expose it to
self-assessment bias, and weaken replayability.

## Decision

Evaluate Reviewer routing only after the Fix stage has produced an accepted, deterministically
verified Patch and before constructing or calling the Independent Reviewer. A failed or
policy-blocked Fix never reaches routing. The router executes no repository code: it replays the
Patch in short-lived detached worktrees and uses bounded Git, Patch statistics, declared pytest
scope, Python AST fingerprints, and bounded static caller/test evidence.

The public policy has three modes:

- `always` is the default and the backwards-compatible production posture. Every accepted Fix is
  reviewed; detailed risk analysis may be omitted because it cannot change the route.
- `shadow` computes and artifacts the same recommendation as selective routing, but its effective
  route is always `review`. This mode measures false skips, Reviewer yield, latency, and Token cost
  before a repository enables skipping.
- `selective` makes the deterministic recommendation effective. Only a low-risk, completely
  analyzed Fix may skip the Reviewer; the already verified Fix Patch then becomes the top-level
  delivered Patch.

The versioned policy records explicit factors rather than presenting its score as a defect
probability. Examples include an Implementer repair round, changed tests or gate configuration,
security-sensitive paths, unsupported source languages, uncovered reachable tests, Patch breadth,
and bounded static fan-in. Thresholds and weights are policy inputs whose behavior must be checked
in shadow evidence; they are not a proof of correctness.

Routing is hard fail-closed in two distinct ways. First, the router binds the resolved Base Commit,
Patch SHA-256, Fix Manifest hash, and accepted Verification Manifest hash, and rejects any mismatch
between archived and in-memory reports. An integrity failure cannot produce an accepting selective
skip. Second, incomplete replay or analysis—including deadline expiry, AST parse/index limits,
ambiguous impact, unsupported code, or worktree cleanup failure—forces the recommendation to
`review` rather than treating missing evidence as low risk.

The routing result is Harness-owned orchestration evidence. It is not added to the Independent
Reviewer prompt or read-tool context. The Reviewer continues to receive the Issue, candidate diff,
deterministic verification evidence, and a fresh read-only repository view, but not the routing
score, risk factors, Implementer plan, or Implementer reasoning. This preserves context
independence and avoids anchoring the semantic review on a heuristic score.

Write the complete decision to `review-routing.json` and embed it in the top-level report. The
Issue-to-PR Manifest recursively hashes that decision, the exact delivered Patch, and both nested
Fix and Verification artifacts under a routing-policy version. In a selective skip, the top-level
outcome remains `accepted`, `review_repair` is absent, and the decision's effective route explains
why no Review artifact exists. `accepted_without_repair` remains reserved for a Reviewer that
actually ran and accepted the candidate.

## Consequences

Existing `fix --review` users retain unconditional review unless they explicitly select another
mode. Shadow mode provides deployment evidence without changing acceptance behavior, and selective
mode can avoid provider initialization, Token spend, and latency for a low-risk Fix.

The decision is replayable and auditable, but its static inputs remain approximations. Dynamic
dispatch, reflection, generated code, unusual test selection, and repository-specific sensitive
areas can escape a seemingly complete analysis. Fail-closed handling covers known incompleteness;
it cannot make bounded static analysis runtime-complete. Teams should begin with `always`, collect
shadow outcomes on representative repositories, and enable `selective` only when the observed
Reviewer benefit and false-skip risk justify it.
