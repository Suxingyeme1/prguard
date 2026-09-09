# attrs #1575 Python 3.14 holdout

Frozen and executed on 2026-09-09. Outcome: resolved in one live Implementer attempt.

This package records a fresh Issue-to-Patch holdout for
[python-attrs/attrs #1575](https://github.com/python-attrs/attrs/issues/1575). The Issue describes a
Python 3.14 change that turns an undefined `ClassVar` annotation into a forward-reference object.
At Base Commit `6851ab593cd25f3c14393e9355d57d22bec2a074`, attrs treated that annotation as an
instance field and generated an incorrect required constructor argument.

Before any Agent call, the operator froze the exact Commit, a 47-test public gate, and a root-owned
evaluator with SHA-256
`2aaaea188d5b9eafd25cdacf0e54b31f91a43aaf44ac315d3e40cfa8f7222e56`. The evaluator failed on
the unchanged Base under CPython 3.14.2. The unprivileged `prguard` account could not read the
evaluator, upstream repair, or Gold Patch.

## Live result

The DeepSeek Implementer used 24 bounded repository-tool calls and submitted one Patch. It unwrapped
the forward-reference argument before attrs' existing `ClassVar` prefix check and added two public
regression checks. PRGuard proved the new tests failed on Base (`2 failed, 47 passed`) and then
accepted the candidate after all 49 public tests passed. The run took 136.8 seconds.

A fresh Independent Reviewer received only the Issue, Base source, and frozen candidate. It used a
12-call read budget, returned `accept` with no findings, and did not trigger repair. Only after both
Manifests were frozen did the operator attach the evaluator; it passed. The wider candidate suite
had 1,388 passes and the same two packaging-environment failures present on Base, so the Patch added
no test regression. Its core implementation direction also matches the later inspected upstream
repair.

This is a Task Resolution result, but not evidence that Reviewer improved the Patch: the Reviewer
made the correct decision without finding or repairing a defect. Raw Fix, Review, JUnit, and sealed
evaluator archives remain private; their hashes are recorded in `case-summary.json`.

The exact delivered source-and-test diff is in `candidate.patch`. The evaluator body and Gold Patch
remain unpublished.
