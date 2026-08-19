# Evaluation protocol

## Purpose

Evaluation proves that the coding product works; it is not the product itself. The first frozen
set should be a small, manually verified collection of Issue-to-Patch and PR-review cases. It
records raw artifacts and manifests before expanding sample size or statistical machinery.

The later A/B question remains: under the same tasks, model version, tools, time limits, and
comparable budgets, does an independent Reviewer improve task resolution and regression avoidance
over a single Implementer or self-review?

## Frozen groups

1. Implementer only.
2. Implementer with self-review.
3. Implementer with independently scoped, read-only Reviewer.
4. Implementer with Diagnostician and independent Reviewer.

Phase 1 evaluates only the shared deterministic harness. Agent experiments begin after its
contracts and fixture behavior are frozen.

## Resolution criteria

A case resolves only if all fail-to-pass tests pass, all pass-to-pass tests remain passing, the
patch applies to the recorded base commit, and no deterministic policy gate blocks it. Textual
similarity to a gold patch is never sufficient.

The initial scorecard is deliberately compact: task resolution, fail-to-pass/pass-to-pass,
regression-free rate, Review Finding precision/recall, false block, token use, elapsed time, and
repair rounds. Keep frozen manifests and raw artifacts. Add confidence intervals or paired tests
only when the case count and decision being made justify them; do not delay the `fix` product path
to build a large benchmark platform.

## Leakage control

Public cases contain issue, repository, base commit, candidate patch, commands, protected paths,
and limits. Evaluator-only records contain hidden tests, gold patches, validity labels, and defect
annotations. These records use separate storage and hashes and must never be serialized through
`Task.public_context()`.

Every run archives schema/policy versions, resolved commit, initial patch hash, command evidence,
final diff, policy violations, timings, terminal outcome, and a SHA-256 manifest. Holdout manifests
are frozen before prompt tuning.
