# Phase 3 report: Independent Reviewer MVP

Date: 2026-08-19

## Outcome

PRGuard 0.3.0 now has a working `review` product entry. It verifies a candidate Patch, constructs a
separate patched worktree, launches a Reviewer in a fresh context with bounded read-only tools, and
emits structured findings plus a deterministic verdict. The Reviewer has no shell, write tool,
Implementer reasoning, evaluator labels, hidden tests, or Gold Patch.

The minimum live gate passed on one known regression and one correct Patch. This two-case result is
workflow evidence, not a general precision/recall claim.

## Deterministic verdict policy

- P0, P1, or P2 Finding: `request_changes`.
- P3-only Findings: non-blocking.
- Failed deterministic verification: `request_changes`, even if the model misses the defect.
- Passed verification with no blocking Finding: `accept`.
- Provider, preflight, Patch, policy, timeout, or cleanup failure: never silently accepts.

## Live evidence

| Case | Harness | Findings | Verdict | Input | Output | Cached | Duration |
|---|---|---:|---|---:|---:|---:|---:|
| Known normalization regression | FAIL_TO_PASS passed; PASS_TO_PASS failed | 1 P2 | request_changes | 4,063 | 1,039 | 2,176 | 18.00s |
| Correct divide Patch | 2 tests passed | 0 | accept | 4,684 | 994 | 2,816 | 18.34s |
| **Total** | — | **1 valid finding** | **2/2 expected** | **8,747** | **2,033** | **4,992** | **36.34s** |

For this deliberately tiny set, observed finding precision is 1/1, recall is 1/1, and False Block
is 0/1. These fractions must not be generalized beyond the frozen cases.

The regression Finding anchors `service.py:4`, identifies removal of `.lower()`, cites the exact
`'HELLO' != 'hello'` evidence, and supplies the targeted pytest reproduction. The clean review reads
the changed source and tests, returns an empty Findings list, and does not invent a concern.

## Implementation

- Added versioned `ReviewTask`, `ReviewerSubmission`, `ReviewEnvelope`, `ReviewReport`, and
  `ReviewOutcome` schemas.
- Added scripted and DeepSeek Reviewer providers behind a provider-neutral protocol.
- Reused the credential-denying, symlink-safe, byte-budgeted repository read tools.
- Added verification-first `ReviewRunner`, separate review worktree, severity gate, review artifacts,
  Markdown report, and recursive SHA-256 Manifest.
- Added `prguard review` with relative task-path resolution and explicit provider/model selection.
- Added ADR 0008 for independent context and deterministic verdict ownership.

## Verification

- Ruff: all checks passed.
- Pytest: 72 passed in 12.51 seconds.
- Both live Review Manifests independently verified.
- Exact configured DeepSeek Key absent from all Review Artifacts.
- Both source repositories remained clean.
- `prguard-0.3.0-py3-none-any.whl` built successfully from the locked environment.

## Boundaries

The Reviewer currently reports but does not trigger repair. Phase 4 must pass only structured
Findings and deterministic evidence to an Implementer, permit at most one complete replacement
Patch, and rerun the final Harness. The original candidate, review, repair proposal, final Patch,
and every verification result must remain in one auditable delivery.

The present Git worktree boundary is still not a hostile-code sandbox. Server execution should use
a dedicated unprivileged account and trusted repositories until container, network, and resource
isolation exist.

## Next priority

Implement the integrated Issue-to-PR / review-repair workflow for Demo B. In parallel, select two or
three small real-repository Issues for Demo A and repeat the live evidence process on the server.
