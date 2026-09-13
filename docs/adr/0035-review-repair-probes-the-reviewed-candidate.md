# ADR 0035: Review repair probes the reviewed candidate

Status: Accepted

## Context

The second Studio demonstration exposed a false block in the changed-test gate. Base already
lowercased strings correctly. A candidate added None handling but removed lowercase conversion.
Its existing test passed. A repair restored the behavior and added an appropriate regression test,
but the gate rejected that test because it also passed the original Base.

## Decision

Keep the original Base reference for initial Fix. For controlled review repair, freeze the exact
reviewed candidate before review and use it as the changed-test reference. Bind its SHA-256 in the
verification Task; require paired path/hash fields, review-repair mode and the reproduction gate.
The model-facing Task context excludes these internal reference fields.

The Harness accepts only a bounded regular reference file with a matching hash, snapshots its bytes
into the artifact directory, and applies it in an isolated probe worktree. Protected and writable
path policies apply before executing new tests. A passing group, collection error, timeout or
infrastructure error does not establish the required test-failure evidence. The repaired candidate
must still pass the normal final gate. Reference Patch bytes enter the SHA-256 manifest and replay
uses that archived copy even if the external input changes.

Reports state the reference kind and hash explicitly. Existing `changed_test_base_results` and
`require_changed_tests_fail_on_base` names remain for compatibility; their names alone must not be
used to label the reference. Versions advance to schema 1.4.0, Harness 0.4.0 and review-repair-v8.

## Consequences and limits

Correct regression tests are no longer rejected for passing an originally correct Base. This
does not relax edit scope, command authorization, isolation or final acceptance. It adds one
archived input to a repair run and preserves reproducibility without an extra model call.

The probe checks group-level failure and later group-level success; it does not prove every new
test is substantive, establish full coverage, or replace independent review. Host mode remains
for trusted repositories. Passing repair verification is not a second Reviewer approval. The
offline Studio case scripts model output and is not counted as a model benchmark result.
