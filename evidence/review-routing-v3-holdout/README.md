# Reviewer routing v3 holdout and correction record

Frozen: 2026-09-03

PRGuard: 0.10.4

This package records the first two evaluator-confirmed clean real-repository cases run after the
v2 policy was frozen. It is deliberately small and does not authorize selective Review by default.

| Case | Gate | v2 | Independent Reviewer | v3 |
| --- | --- | --- | --- | --- |
| Inflect #242 source-only | 5 targeted; 215 passed + 16 xfailed wider | `review` 9/5 | accept, 0 findings, 209.3 s | `review` 9/5 |
| python-dotenv #638 source-only | 217 passed + 1 skipped full suite | `review` 7/5 | accept, 0 findings, 94.3 s | `skip` 0/5 |

The python-dotenv run exposed a deterministic accounting bug rather than a model-quality problem.
`review-routing-v2` classified `pytest -q -o pythonpath=src` as a full-suite command, but only marked
unchanged static test evidence as covered for targeted commands. It therefore assigned both “no
explicit unchanged test evidence” and “related tests not explicitly covered” even though the full
suite had executed. `review-routing-v3` treats every statically reachable or related test as covered
when the verified pytest scope is `full`. The exact Patch moves from `review` 7/5 to `skip` 0/5.

The same live run also found a pipeline defect: an optional scripted repair provider was validated
before Review began, so an accepting Review could fail for a repair fixture that would never be
used. The failure is retained in `orchestration-regression.json`; v0.10.4 constructs that provider
only after a `request_changes` verdict.

The python-dotenv label is not inferred from green existing tests. An evaluator-only check, kept out
of Agent inputs, reproduces two parser calls at Base and one parser call with the Candidate. The
source-only change also matches upstream merge commit `3f0e3e0b461cf7127e2753efbdf896bdff31db2e`.
Inflect's targeted reproduction and wider gate both pass, and the Independent Reviewer found no
evidence-backed defect.

The cost observation matters: both v2 reviews accepted with zero findings while consuming 303.6
seconds and 405,253 input/output tokens in total. This is not evidence that Reviewer is generally
useless; it is evidence that routing it onto known-clean work has measurable cost. v3 removes one
of these two observed unnecessary Review recommendations without changing the Inflect route or the
three frozen v2 correction cases.

Selective activation remains `not_ready`: there are only two clean observations, python-dotenv
informed the v3 correction, and no new held-out defective case has tested v3's False Skip behavior.
`always` therefore remains the default mode.
