# Phase 2.1 report: DeepSeek live validation

Date: 2026-08-19

## Result

The minimum live-provider gate passed. DeepSeek V4 Pro solved both manually checked public fixtures
with one-file patches, and the deterministic Harness accepted both. Every success and development
failure has a verified SHA-256 Manifest. Exact-key and credential-pattern scans found no credential
in any live Artifact, and both source repositories remained clean.

This is a two-case integration result, not a general benchmark. No live test-failure repair occurred:
the second task was named `repair-once` for its scripted sequence, but the live model produced the
correct complete Patch on its first attempt.

## Accepted runs

| Case | Outcome | Attempts | Tests | Input | Output | Cached | Duration |
|---|---:|---:|---:|---:|---:|---:|---:|
| `fix-direct-success` | accepted | 1 | 2 passed | 3,804 | 736 | 2,432 | 15.43s |
| `fix-repair-once` | accepted | 1 | 3 passed | 3,824 | 603 | 2,304 | 10.05s |
| **Total** | **2/2 accepted** | **2** | **5 passed** | **7,628** | **1,339** | **4,736** | **25.48s** |

Estimated cost remains unavailable in PRGuard 0.2.1; the schema's numeric default must not be
interpreted as a claim that the requests were free.

## Development evidence

1. The initial request used `tool_choice=required`; DeepSeek thinking mode rejected it with HTTP
   400. The adapter now omits that incompatible parameter and locally fails closed if no tool call
   arrives.
2. The first retry still loaded the old non-editable installed package. The run remained a 400 and
   exposed the need to reinstall the local wheel before live validation.
3. The next request reached the model, but its Patch lacked standard unified-diff headers. Patch
   policy blocked it before execution. This exposed that invalid proposals were not yet archived.
4. The Runner now persists Proposal, Patch, metadata, and Token usage before Patch validation, and
   a regression test enforces that audit boundary. The tool contract now states the exact Git diff
   header grammar.
5. After reinstalling the corrected package, both live tasks were accepted.

These failures were retained rather than removed. The pre-fix invalid-Patch run cannot recover the
discarded Proposal retrospectively; that limitation is explicit in its Artifact and fixed for all
future runs.

## Patch review

The slug task changed `value.strip().lower().replace(" ", "-")` to
`"-".join(value.lower().split())`, satisfying repeated-whitespace collapse while preserving
lowercase behavior. The clamp task changed `min(value, upper)` to
`max(lower, min(value, upper))`, enforcing both bounds. Neither Patch modified tests or protected
paths.

## Verification

- All five live Manifests independently verified.
- Exact configured Key absent from all live Artifact bytes.
- Generic API-key and Authorization patterns absent.
- Both source repositories clean after execution.
- Full project check after live fixes: Ruff passed; Pytest 66 passed in 11.51 seconds.

## Next priority

Phase 2 is ready to hand off to Phase 3 while real-repository evidence grows in parallel. Implement
the read-only Independent Reviewer and `review` CLI next. The Reviewer must receive Issue, candidate
diff, bounded source, and deterministic test evidence in an independent context; it must not receive
Implementer reasoning, evaluator labels, hidden tests, Gold Patch, shell access, or write access.
