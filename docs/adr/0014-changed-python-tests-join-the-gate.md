# ADR 0014: changed Python tests join the deterministic gate

- Status: accepted
- Date: 2026-08-23

## Context

Project discovery may narrow pytest to one Issue-related public file. An Implementer can then add a
new regression-test module outside that target. Merely allowing the edit does not establish that
the new test collected or passed, and trusting the model's claim would break the Harness verdict
boundary.

## Decision

After applying the candidate Patch, the Harness identifies added or modified `.py` files under a
`test`/`tests` root (or a root-level test module) whose name follows `test_*.py` or `*_test.py`.

- If every changed test is an explicit target of a declared pytest command, no command is added.
- Otherwise, when the Task declares pytest capability, the Harness appends one
  `pytest -q <uncovered paths...>` command.
- If tests changed but no pytest command was declared, the candidate is policy-blocked before
  execution.

The derived argv is constructed from Git-reported repository-relative paths, passes the same fixed
command grammar, appears in VerificationResult/TraceEvent artifacts, and is regenerated during
replay. The model does not submit this command.

## Consequences

Agent-authored Python regression tests can no longer be accepted without being executed merely
because the base profile selected a narrower test file. Some repositories use unconventional test
names, non-Python runners, generated test suites, or collection plugins; those still require a
reviewed project profile and wider CI. This decision executes tests the Agent wrote, but does not
treat those tests as an independent oracle or replace pass-to-pass regression checks.
