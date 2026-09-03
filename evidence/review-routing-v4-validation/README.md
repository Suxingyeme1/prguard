# Reviewer routing v4 validation

Frozen: 2026-09-03

PRGuard: 0.10.5

This package records one evaluator-confirmed clean Issue-to-Patch run and the first genuinely
defective held-out Pull Request evaluated against `review-routing-v3`. It validates that the router
can avoid one observed unnecessary Review while still selecting Review for a defect that passed
the repository's entire declared test gate.

| Case | Evaluator label | Deterministic gate | v3 | Independent Reviewer | v4 |
| --- | --- | --- | --- | --- | --- |
| python-dotenv #600 | clean | 217 passed, 1 skipped | `skip` 0/5 | accept, 0 findings | `skip` 0/5 |
| Click #3199 for issue #3145 | defective | 1323 passed, 21 skipped, 1 xfailed; changed tests 9 passed | `review` 23/5 | request changes, one P2 | `review` 18/5 |

The Click candidate corrected the issue's direct `Context.lookup_default()` examples and added
tests, so the deterministic Harness accepted it. In an independent read-only context, the Reviewer
found that internal parameter resolution had been redirected to a new private helper. That bypassed
the existing public `Context.lookup_default()` override point. An evaluator-only custom Context
reproducer passed at Base and failed with the exact candidate Patch. The finding matches the
maintainer's reason for rejecting the candidate; a later upstream fix preserved the extension
point. Neither that maintainer feedback nor the evaluator was present in the Agent task.

The run also exposed a smaller deterministic accounting defect. The Harness first ran unfiltered
`pytest -q`, then automatically replayed the changed test file. v3 kept only the last targeted
scope. v4 makes any successful unfiltered full-suite execution dominate later targeted replays.
This removes the spurious five-point `no_explicit_unchanged_test_evidence` factor while preserving
the Click `review` recommendation through changed-test, incomplete-analysis, and Patch-size facts.
The python-dotenv decision is unchanged.

This is evidence of incremental Reviewer value, not a correctness or calibration claim. The sample
is still too small, one observation informed the v4 accounting correction, and model cost remains
material. Selective Review therefore remains opt-in; `always` stays the default and `shadow` remains
the recommended measurement mode.

`validation-summary.json` binds each public record to the original raw reports and Manifests by
SHA-256. The raw server archives were copied across hosts, their archive hashes matched, all nested
Manifests verified, and a credential-pattern scan found no API key.
