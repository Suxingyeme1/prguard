# ADR 0008: Reviewer context is independent and verdict is deterministic

- Status: accepted
- Date: 2026-08-19

## Decision

Run candidate verification before semantic review. Apply the same Patch to a separate detached
worktree and expose only bounded read tools. The Reviewer receives Issue, Patch, changed files,
policy results, and structured command evidence. It never receives Implementer plan/reasoning,
hidden tests, Gold Patch, defect labels, shell, or write tools.

The Reviewer submits a summary and zero or more evidence-backed `ReviewFinding` objects. P0, P1,
and P2 findings request changes; P3 is non-blocking. Any deterministic verification failure also
requests changes, even if the model returns no finding. Only passed verification with no blocking
finding accepts. Provider failure never silently accepts.

## Consequences

Semantic review can add source-linked evidence without owning the gate. Independent context reduces
self-review anchoring but does not guarantee independent errors when providers share a model family.
The Phase 4 repair loop may consume findings, but must rerun the final Harness and preserve both the
original review and repaired Patch.
