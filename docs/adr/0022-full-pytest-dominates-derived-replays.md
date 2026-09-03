# ADR 0022: Full pytest dominates derived targeted replays

Status: Accepted (2026-09-03)

## Context

The Click #3199 candidate ran `pytest -q` successfully, after which the Harness automatically ran
`pytest -q tests/test_defaults.py` because the candidate changed that test module. Both commands
passed. `review-routing-v3` accumulated pytest scope by replacing the previous classification with
each later command, so the final Artifact incorrectly recorded `pytest_scope=targeted` and only the
derived test path.

That bookkeeping added `no_explicit_unchanged_test_evidence` even though every collected test had
already run. It did not cause a False Skip—the candidate still routed to Review—but the Artifact's
stated scope and five risk points were wrong.

## Decision

Create immutable policy version `review-routing-v4`; preserve v1-v3 Artifacts.

Route analysis aggregates all successful pytest commands in the accepted Fix verification. Once an
unfiltered command without explicit test targets establishes `full`, later targeted commands cannot
downgrade that scope. A full result has no `pytest_targets` because the whole collected suite is the
stronger statement. If no full command exists, the existing filtered/targeted/none precedence and
bounded target collection remain unchanged.

The decision remains argv-derived and deterministic. Neither model assertions nor test counts can
promote a command to full scope.

## Consequences

The exact Click Patch changes from `review` 23/5 under v3 to `review` 18/5 under v4. The meaningful
triggers remain: candidate-controlled tests changed, static impact analysis was incomplete, and the
Patch crossed the medium-size boundary. The evaluator-confirmed clean python-dotenv #600 Patch
remains `skip` 0/5.

This correction does not imply that a full existing suite proves a Patch correct. Click #3199 is
the counterexample: all 1323 tests passed, but an independent Reviewer found a public extension-point
regression that an evaluator-only Base/Candidate reproducer confirmed. `always` remains the default,
`shadow` remains the recommended evidence-collection mode, and selective activation remains
`not_ready` because the labelled sample is too small.
