# ADR 0021: Full pytest covers unchanged static test evidence

Status: Accepted (2026-09-03)

## Context

The first v2 holdout run used python-dotenv PR #638. Its verified command was
`pytest -q -o pythonpath=src`: no test path, node ID, selection filter, or non-execution flag was
present, so the deterministic parser correctly classified it as `pytest_scope=full`. All 217
collected tests passed.

The v2 coverage accounting handled only `targeted` pytest commands. It left all unchanged related
tests uncovered for a `full` command, then assigned `no_explicit_unchanged_test_evidence` (5) and
`related_tests_not_explicitly_covered` (2). The clean one-line Patch was therefore routed to Review
at 7/5. Independent Review accepted it with zero findings and 94.3 seconds of added latency.

This is an internal contradiction: the Artifact says the whole suite executed while simultaneously
claiming that named files in that suite were not explicitly covered.

## Decision

Create immutable policy version `review-routing-v3`; preserve all v1 and v2 Artifacts.

When the verified pytest scope is `full`, mark the bounded union of statically reachable and
related unchanged tests as `covered_unchanged_tests`. Consequently those paths cannot generate
the uncovered-test factors. `targeted`, `filtered`, and `none` retain their existing behavior.

The definition of `full` remains conservative and argv-derived. Node IDs, selection filters, and
collection-only/non-executing flags classify a command as `filtered`; explicit test files or
directories classify it as `targeted`. No model statement can upgrade the scope.

Separately, defer construction of the optional repair Implementer until the Independent Reviewer
returns `request_changes`. Provider configuration that is irrelevant to an accepting Review must
not fail the pipeline.

## Consequences

The exact python-dotenv Patch changes from `review` 7/5 under v2 to `skip` 0/5 under v3. Its Base
Commit, Patch SHA-256, Fix Manifest, and Verification Manifest are identical across the replay.
Inflect remains `review` 9/5, and the prior PrettyTable, Humanize, and normalization decisions are
unchanged.

This correction does not prove that a full repository suite covers a new requirement; that is a
property of the target repository's tests, not something static path accounting can establish.
Reviewer selection remains deterministic risk routing rather than a correctness proof. `always`
continues as the default, and v3 selective activation remains `not_ready` until held-out defective
cases measure False Skips.
