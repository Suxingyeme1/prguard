# ADR 0017: Keep call-graph traversal bounded and evidence-carrying

Status: Accepted (2026-08-23)

## Context

Direct caller and callee lookups answer one local question at a time. A repository-level coding
task often needs a compact view of the entry points above a changed symbol, the dependencies below
it, and the public tests reachable from those callers. Repeated one-hop calls spend the Agent's
tool budget and can lose the path connecting those facts. A language server or runtime tracer would
add dependencies, repository execution, and a larger trust boundary.

## Decision

Add a lazy `trace_call_graph` query to the existing read-only Python AST index. The caller chooses
`callers`, `callees`, or `both`; depth is limited to one through three and the total edge count to
the existing bounded result limit. Traversal starts only from an exact qualified name or one unique
suffix. Ambiguous roots return candidates without edges.

Each edge is oriented caller to callee and retains file, line, lexical expression, resolution type,
distance, and traversal direction. Nodes state whether they have a repository definition. Public
test nodes reached through incoming edges are listed separately from heuristic related-test
ranking. Results share the existing context-byte budget, index caps, path denial, and symlink rules.
Implementer and Reviewer receive the same read capability, while only the Implementer retains a
terminal edit submission tool. A key-free `inspect-symbol` CLI runs the same query in a short-lived
detached worktree at the Task's resolved Base Commit for human inspection and evidence replay.

## Consequences

The Agent can inspect a bounded impact neighborhood in one auditable call and then read the cited
source ranges before changing code or reporting a finding. The tool executes no repository code and
adds no third-party runtime dependency.

This remains lexical static analysis. Dynamic dispatch, inferred instance types, reflection,
dependency injection, decorators that replace callables, monkey-patching, native extensions, and
generated code can create missing or misleading edges. An empty graph means no bounded static edge
was found, not that runtime impact is impossible.
