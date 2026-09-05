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

Before freezing commands, evaluators must run each proposed lint/type/test command on the unpatched
base and distinguish product failures from missing generated files or optional test dependencies.
PRGuard performs pytest collection plus declared non-pytest Base-gate readiness before a model
call; evaluators remain responsible for interpreting pre-existing pytest assertion failures. Any
repository check that passes on the base and fails only after the candidate belongs in the
deterministic gate. Broader post-run checks may be reported separately, but they cannot
retroactively turn an incomplete configured gate into evidence that the original run was
review-ready.

If a candidate adds or modifies a conventionally named Python test module, that exact file must be
executed even when the frozen base command targets a narrower existing file. Such a command is
Harness-derived from Git's changed-file set and retained in the report. A task without a declared
pytest capability cannot claim test-backed success after changing Python tests.

For Agent-generated or modified executable Python tests, execution on Candidate is not enough. The
Harness copies those test files and changed test support onto a fresh unchanged Base worktree,
withholds candidate source changes, and requires the tests to fail there before they may join the
Candidate gate. A test that already passes is policy-blocked as missing FAIL_TO_PASS evidence.
Python files whose parsed AST is unchanged—comments and formatting only—skip this requirement but
still run under the declared Candidate gate. This test is evidence of a reproduced behavior change,
not proof that the assertion expresses the correct product contract.

The initial scorecard is deliberately compact: task resolution, fail-to-pass/pass-to-pass,
regression-free rate, Review Finding precision/recall, false block, token use, elapsed time, and
repair rounds. Keep frozen manifests and raw artifacts. Add confidence intervals or paired tests
only when the case count and decision being made justify them; do not delay the `fix` product path
to build a large benchmark platform.

## Selective Reviewer routing

The routing evaluation unit is one Fix that the deterministic Harness has already accepted. Failed
Patch application, failed verification, timeout, infrastructure failure, and policy block remain
Harness outcomes and are excluded from routing confusion counts. The explicit `review` entry point
also remains user-directed; selective routing concerns the optional Reviewer following a successful
Issue-to-Patch run.

Three modes answer different questions:

1. `always` runs the Reviewer for every accepted Fix and provides the compatibility baseline.
2. `shadow` records the deterministic `review` or `skip` recommendation but executes Review in
   either case. This is the initial evaluation mode because every case retains a paired Reviewer
   outcome and full incremental cost.
3. `selective` follows the recommendation. It is a deployment mode, not the right mode for
   estimating performance from a first small sample.

For each shadow case, freeze the routing-policy version, score, threshold, individual factors,
Patch hash, Base Commit, Fix and verification Manifest hashes, recommended route, effective route,
Reviewer findings and verdict, repair outcome, tokens, and durations. The score is an ordinal sum
of versioned evidence weights. Do not describe it as confidence, probability, expected loss, or a
percentage, and do not compare raw scores produced by different policy versions.

Evaluator labels are applied after the run and remain outside Agent-visible context:

- **clean:** no candidate-caused defect is confirmed under the frozen evaluator checks;
- **defective:** at least one candidate-caused defect is confirmed, including a regression missed
  by the configured public gate;
- **finding disposition:** each Reviewer finding is independently marked confirmed, rejected, or
  unresolved using its reproduction condition or evaluator check.

The routing and Reviewer errors are intentionally separate:

```text
false route = recommended review AND evaluator label clean
false skip  = recommended skip   AND evaluator label defective
false block = effective review   AND evaluator label clean
              AND Reviewer verdict request_changes
```

Always publish the numerator and denominator. A clean Patch that is reviewed and accepted is a
false route but not a false block. A defective selective skip cannot establish whether the Reviewer
would have found the defect; that stronger counterfactual is available only from a shadow run or a
later paired audit. Conversely, a Reviewer finding on a Patch the Harness already rejected is not
incremental Reviewer benefit.

### Small-sample rollout

Before enabling selective skipping:

1. freeze the routing policy and thresholds without consulting holdout defect labels;
2. run a small manually checked set in shadow mode, stratified across targeted/broad pytest scope,
   first-attempt/repaired Fixes, ordinary/sensitive paths, narrow/broad Patches, and
   complete/incomplete static analysis;
3. retain raw routing, Review, repair, verification, and Manifest artifacts;
4. report false-route, false-skip, and false-block counts alongside confirmed incremental findings,
   token cost, elapsed time, and repair rounds;
5. enable selective mode only if the observed escape boundary and saved cost fit the repository's
   own tolerance, while keeping periodic shadow or manual audits for skipped cases.

Do not tune a threshold until two or three illustrative cases happen to pass. A small frozen table
is useful for finding broken rules and integration errors, but it cannot support a population defect
rate or a claim that the heuristic is calibrated.

The executable evaluator path is `scripts/build_shadow_scorecard.py`. Its input is a post-run
dataset under `evidence/`, not an Agent Task. It verifies every candidate Patch and routing Artifact
hash, requires `shadow` mode and the frozen policy version, and joins Reviewer evidence only when
the exact Base Commit and candidate Patch SHA-256 match. Generated JSON and Markdown retain
numerators, denominators, missing Reviewer coverage, observed Token/latency/repair cost, and
activation blockers. A missing denominator is reported as `0/0` with no rate, never as zero
percent.

Evaluator labels are revisable when new post-run evidence is bound to the same Base Commit and
candidate Patch. Passing the repository's entire existing suite is evidence, not an immutable
`clean` label: the PrettyTable case was reclassified after independent Review proposed a concrete
multi-table check that passed on Base and failed on Candidate. The original test results remain in
the record; the later check does not get retroactively exposed to the Reviewer context.

## Leakage control

Public cases contain issue, repository, base commit, candidate patch, commands, protected paths,
and limits. Evaluator-only records contain hidden tests, gold patches, validity labels, and defect
annotations. These records use separate storage and hashes and must never be serialized through
`Task.public_context()`.

Every run archives schema/policy versions, resolved commit, initial patch hash, command evidence,
final diff, policy violations, timings, terminal outcome, and a SHA-256 manifest. Holdout manifests
are frozen before prompt tuning.
