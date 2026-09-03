# ADR 0023: Local Issues freeze before Agent execution

Status: Accepted (2026-09-03)

## Context

PRGuard could prepare a public GitHub Issue automatically, but a local repository still required a
person to assemble every FixTask JSON field. That made private, unpublished, and interview-demo
repositories unnecessarily awkward even though deterministic project-policy discovery existed.

Running directly against the caller's working tree would reduce typing but weaken replay identity
and could mix Agent output with unrelated local changes.

## Decision

Accept a clean local Git repository plus natural-language Issue text (inline or from a bounded UTF-8
regular file). Resolve `HEAD` or the requested revision to an exact commit, then materialize that
commit into a separate detached checkout before policy discovery or any provider call.

The source repository must identify its Git toplevel and have no tracked or untracked changes. The
output workspace must be outside it. Materialization uses fixed argv Git commands, disables hooks
and user/system Git configuration, performs no shell evaluation, and verifies the resulting HEAD
and clean status. Preparation still requires an explicit host-trust or container decision.

Write a versioned local preparation report, FixTask, and recursive SHA-256 Manifest. Preserve the
natural-language Issue verbatim after whitespace trimming and record its digest; do not ask a model
to invent commands, permissions, or evaluator fields.

## Consequences

Users can run `prguard fix "issue" --repository ...` without authoring JSON, while CI and cautious
operators can retain the two-stage `prepare-local` then `fix task.json` workflow. Both paths use the
same frozen Task and existing FixRunner.

The feature deliberately excludes dirty-working-tree snapshots. Supporting them would require an
explicit, hash-bound patch/input model and a clear decision about whether untracked files are part
of Base; silently copying them would undermine the current Base Commit contract.
