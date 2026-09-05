# ADR 0027: compatibility signals inform but do not decide

Status: accepted 2026-09-05.

## Context

The FileLock #606 holdout exposed a breaking default that passed the declared public gate and was
false-accepted by Independent Review. Prompt text alone asked the Reviewer to compare defaults, but
the Reviewer still had to rediscover every relevant Base/Candidate difference through bounded read
tools. Reusing the revealed evaluator or its expected implementation would contaminate future
evidence.

## Decision

Before a model review, PRGuard creates separate detached worktrees at the frozen Base Commit and
the exact Candidate Patch. A deterministic, read-only Python AST pass compares only changed
non-test modules within the existing file-size boundary. It reports bounded signals for added or
removed public callables/classes, signatures and defaults, class bases, protocol-method behavior,
ordinary public implementation changes, and literal `__all__` changes.

The signals enter the Review provider's public evidence and are written to `review-report.json` and
`review-report.md`. They are prompts for investigation, not policy violations or findings. Only the
Reviewer may turn one into an evidence-backed finding; the deterministic Harness still owns test,
policy, timeout, and final gate results.

Implementer and Reviewer read budgets are configured separately. The defaults remain 24 reads for
repository localization/editing and 12 reads for independent review.

## Consequences

The Reviewer receives exact Base/Candidate compatibility deltas without seeing Implementer
reasoning, evaluator labels, hidden tests, or a Gold Patch. False positives can increase model
attention and cost but cannot automatically block delivery. Dynamic APIs, generated exports,
runtime monkey-patching, non-Python code, and behavior outside changed files remain beyond this
static pass and require tests or human/evaluator evidence.
