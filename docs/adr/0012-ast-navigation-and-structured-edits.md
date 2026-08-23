# ADR 0012: Use bounded static navigation and Harness-owned structured edits

Status: Accepted (2026-08-23)

## Context

Plain text search is portable but gives an Implementer weak information about symbol boundaries,
imports, callers, and likely tests. Asking a model to manually construct every unified-diff header
also spends tokens on Patch syntax and creates avoidable malformed-Patch failures. Giving the model
a language server, arbitrary shell, or direct filesystem writes would enlarge the trusted surface
and make replay harder.

## Decision

Add a lazy, local Python AST index behind the same read capability and context budget as existing
repository tools. It exposes symbol definitions, imports and package re-exports, lexical references,
incoming/outgoing calls, and deterministic source-to-test ranking. Every response states that the
result is bounded static analysis; no runtime-complete call graph is claimed.

Prefer declarative `replace_text` and `create_file` proposal operations. A replacement is accepted
only when its old text appears exactly once. PRGuard validates paths and byte/file limits, applies
operations in a Harness-owned detached worktree, asks Git to produce the Base-Commit-relative diff,
and runs the existing Patch policy and deterministic verification. Raw unified diffs remain a
compatibility fallback.

## Consequences

Python repositories gain higher-signal navigation without executing their code or requiring a new
runtime dependency. Dynamic dispatch, reflection, generated code, and non-Python call relationships
remain outside the index and must be investigated with source reads and tests.

Exact text edits are intentionally less expressive than unrestricted writes. Ambiguous replacements,
renames, deletions, binary changes, and oversized files fail closed or use the reviewed Patch
fallback. The model never writes the developer checkout or verification worktree directly.
