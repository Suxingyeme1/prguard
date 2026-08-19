# ADR 0010: Compose independent review only after an accepted Fix

- Status: accepted
- Date: 2026-08-19

## Decision

The primary Issue-to-PR entry runs the existing Fix workflow first. Only an accepted Fix with an
archived final Patch can enter independent review. Fix failure, timeout, or policy rejection never
invokes the Reviewer. The outer task defines one total deadline plus a smaller Fix-stage and
Reviewer-stage budget, leaving explicit time for controlled repair and final verification.

The Reviewer and optional repair retain the Phase 4A isolation rules. The top-level workflow copies
only the final accepted nested Patch to its delivery root and recursively hashes all Fix, review,
repair, verification, and report artifacts.

## Consequences

The primary CLI can demonstrate Issue-to-Patch-to-review without duplicating Harness or provider
logic. Failed implementation does not waste review tokens. Nested run IDs remain independently
auditable, while one outer Manifest supplies a single delivery boundary. In the worst permitted
case the Fix workflow may make two Implementer proposals and review may authorize one more, so
budgets and token reporting must remain visible.
