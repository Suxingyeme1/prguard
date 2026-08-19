# ADR 0009: Controlled review repair is one full replacement Patch

- Status: accepted
- Date: 2026-08-19

## Decision

When independent review requests changes, PRGuard may invoke the Implementer exactly once. The
Implementer reads a separate worktree containing the original candidate but receives no write or
shell capability. It receives only the Issue, original candidate Patch, structured findings,
review summary, and public deterministic verification evidence.

The Implementer must return a complete unified diff against the same immutable Base Commit, not an
incremental diff against the candidate. Patch size, changed-file count, writable paths, and
protected paths are checked before a fresh Verification Harness applies or executes it. Acceptance
requires the final Harness to pass. A clean initial review never invokes the Implementer.

## Consequences

Every accepted final Patch has one unambiguous replay base. The original candidate, initial review,
repair proposal, final verification, and delivered Patch are preserved under one recursive
SHA-256 manifest. The workflow cannot repeatedly spend tokens or silently mutate an accepted
candidate, but one attempted repair may remain semantically incomplete when public tests are weak.
