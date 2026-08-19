# ADR 0006: The model proposes; deterministic code executes

Status: Accepted (2026-08-19)

The Implementer may list, search, and read bounded repository content, then submit one complete
unified diff. It receives no shell and cannot write the source checkout. PRGuard validates the
Patch scope and runs it in a new Phase 1 Harness worktree. One failed verification may produce one
complete replacement patch against the same Base Commit. This keeps semantic code generation
replaceable while Git state, permissions, tests, loop bounds, outcomes, and artifacts remain
deterministic.

The live adapter uses the OpenAI Responses API with strict function schemas. An offline scripted
adapter is retained for deterministic workflow tests; its success is not reported as model quality.
