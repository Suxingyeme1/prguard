# ADR 0026: Studio replays frozen evidence before controlling live runs

## Status

Accepted.

## Context

PRGuard needs an understandable browser demonstration. Directly wiring an unauthenticated page to
repository execution would blur the host trust decision, command policy, and artifact boundary.
A fake progress animation presented as a live Agent run would also violate the project's evidence
claims.

## Decision

The first PRGuard Studio release is a static, read-only evidence cockpit. It replays two checked
public cases and links back to their evidence packages. Repository, Commit, Issue, execution
boundary, verification command, counts, verdicts, and abbreviated hashes come from those frozen
records. The interface explicitly labels itself as an evidence replay and performs no provider call
or source write.

A future live adapter is a separate boundary. It must authenticate local access, reuse existing
Task preparation and explicit host/container approval, stream structured Trace Events, and expose
only run-scoped artifacts. The browser must not gain a free-form Shell or choose trust policy.

## Consequences

The current Studio can be deployed as a static site and used in interviews without credentials or
repository execution. It demonstrates the product flow truthfully, but it is not yet the production
control plane for starting new work.
