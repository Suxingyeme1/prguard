# ADR 0026: make provider termination and Base-test evidence explicit

- Status: accepted
- Date: 2026-09-05

## Context

A FileLock holdout run exposed three different ways a plausible run could end without trustworthy
evidence. First, a model could spend its final read-tool call and receive no subsequent turn in
which to submit edits or a review. Second, a changed pytest module could fail on Base because it
imported a candidate-only symbol; treating every non-zero pytest exit as FAIL_TO_PASS incorrectly
promoted a collection failure to regression evidence. Third, DeepSeek thinking mode could ignore a
terminal-only tool list, while the API rejected forced `tool_choice` during thinking.

## Decision

Provider loops treat `max_tool_calls` as a read budget, not a response-turn budget. After the final
read, the Implementer receives a terminal-only edit/Patch turn. The Reviewer receives a terminal
message and only `submit_review`; its terminal call disables thinking and requests that function
explicitly. If the provider still asks to read, PRGuard records the rejected tool call and grants
one final terminal recovery turn. No additional repository bytes are returned.

Structured-edit conflicts are repairable once because stale hashes, ambiguous text, and invalid
candidate syntax are proposal failures rather than authorization failures. Protected-path, scope,
size, and other hard policy violations still stop immediately.

For Agent-authored pytest tests, only exit code 1 is valid Base FAIL_TO_PASS evidence. Exit code 2
or any other non-zero status is policy-blocked as collection, usage, interrupt, or infrastructure
failure. That structured Base output may drive the single permitted repair.

The Reviewer rubric must compare changed public signatures and defaults with Base. A request for a
new capability does not implicitly authorize breaking existing callers, even if both the existing
suite and newly authored tests pass.

## Consequences

Tool budgets terminate predictably, malformed Base tests cannot satisfy the regression gate, and
one ordinary edit/test mistake can be corrected without weakening hard policy. DeepSeek's
thinking/tool-choice incompatibility is handled explicitly and remains visible in provider
metadata.

These controls do not prove that an Agent-authored test expresses the intended API contract. The
FileLock candidate still passed the public gate and was accepted by the independent Reviewer, but
failed the sealed evaluator because it changed a legacy default instead of adding an opt-in policy.
That false accept remains evidence and the contaminated case is not rerun as a holdout.
