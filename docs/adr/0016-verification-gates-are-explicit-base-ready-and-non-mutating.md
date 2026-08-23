# ADR 0016: Verification gates are explicit, Base-ready, and non-mutating

Status: Accepted (2026-08-23)

## Context

The presence of `[tool.ruff]` proves that a repository configures Ruff, not that PRGuard's installed
version and full-repository command are an approved clean gate. Ruff can also inherit `fix = true`
and mutate the Candidate worktree. A failing or mutating baseline gate can be misreported as a
Patch regression and waste the bounded repair round.

## Decision

Generic GitHub onboarding infers pytest but not lint policy. A reviewed `.prguard.toml` may declare
Ruff, subject to the fixed `check --no-fix` grammar. Before any provider call, pytest targets must
collect and every declared non-pytest gate must pass against the immutable Base Commit.

Immediately before verification commands, capture the Candidate diff excluding declared runtime
scaffolds. Capture it again afterward. Any byte difference is a policy violation even when command
exit codes pass. Runtime scaffolds remain separately protected and hash-checked.

## Consequences

The Harness stops blaming model Patches for known environment/history failures and cannot silently
accept formatter/linter/test rewrites. Repositories that require lint, type checking, or a wider
suite must express that policy explicitly. Base pytest assertions are not executed by readiness,
because a valid Issue task may intentionally begin with fail-to-pass tests; evaluators must still
separate those from environment failures.
