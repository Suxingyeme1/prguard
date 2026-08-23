# ADR 0015: Provider failures retain partial evidence and a terminal slot

Status: Accepted (2026-08-23)

## Context

A live provider can search source, consume Tokens, and receive responses before timing out or
exhausting its tool budget. Reporting only the terminal exception erases the facts needed to
distinguish model, navigation, budget, and provider failures. Counting the final submission against
the same limit as read tools can also reject a model immediately after it finishes navigation.

## Decision

Expected provider failures attach a validated non-secret record containing provider/model,
response ID, safe metadata, accumulated Token usage, and bounded tool-call summaries. Fix, Review,
and controlled-repair reports archive that record in canonical JSON and include it in the recursive
Manifest. Credentials and hidden reasoning are never included.

Treat `max_tool_calls` as the read-tool budget. Each result reports used and remaining reads, with a
deterministic convergence message in the final three. Permit one additional terminal-only
`submit_edits`, `submit_patch`, or `submit_review` call. A further read fails closed and preserves
the partial record.

## Consequences

Failed live runs become cost- and behavior-auditable without granting more repository access. The
terminal slot removes an orchestration-induced false failure but does not guarantee model
convergence; a model that ignores the remaining budget still fails. Provider Token accounting is
retained as reported and is not treated as an independent correctness oracle.
