# Phase 4B Issue-to-PR MVP report

Date: 2026-08-19
Version: `0.5.0`

PRGuard now composes the primary Coding Agent and quality module under one command:

```text
Issue -> FixRunner -> accepted Patch -> Independent Reviewer
      -> optional one controlled replacement repair -> final Harness -> delivery Patch
```

The top-level `IssueToPRTask` enforces a total deadline, a smaller Fix-stage budget, and a Reviewer
budget that must leave time for repair verification. Fix failure short-circuits before Reviewer
invocation. The top-level Manifest recursively hashes the nested Fix, review, repair, verification,
and final delivery evidence.

Offline integration demonstrates Reviewer net value on a narrow controlled case: the initial Patch
passes the configured new-behavior test but removes lowercase normalization. The independent
Reviewer locates the uncovered regression and triggers one correct replacement Patch. Separate
cases cover a clean accepted Fix and a failed Fix with zero Reviewer calls.

After the version and documentation update, Ruff passed and the full suite reported
`86 passed in 24.09s`.

## DeepSeek live gate

- Outer run: `f5d55cab-f4fd-4fd3-affe-e392343ae7c2`.
- Model: `deepseek-v4-pro`, high reasoning effort, thinking enabled.
- Implementer Patch: one-file `slug.py` change using whitespace-aware `split()` and `join()`.
- Fix gate: two public tests passed on the first proposal.
- Independent review: zero findings and `accept`; no repair proposal was requested.
- Top-level outcome: `accepted`.
- Duration: `24.456s`.
- Tokens: 8,706 input, 1,408 output, 7,040 cached.
- Final Patch SHA-256: `eb19f431638d66f76f500968e0115a5e3cb33838d52917db2db324678432de52`.
- Manifest SHA-256 file hash:
  `5e097ad6de895420af46eb4c2f35f1fdf52e3e90600ba4bbf46999014a82400e`.
- The 36-file recursive Artifact was copied to
  `outputs/phase-4b-deepseek-live-issue-to-pr` and verified after copying.
- Exact API-key persistence scan: zero matches. The source fixture repository remained clean.

This is one small fixture and shows mechanism viability, not broad repository task resolution or
Reviewer precision. The next evidence increment is two or three manually checked real-repository
Issues, including at least one case where independent review changes the live final outcome.

## Server live gate

- Release: `0.5.0` in a new isolated virtual environment.
- Ruff: passed.
- Pytest: `86 passed in 34.32s` as unprivileged user `prguard`.
- Outer run: `638065fc-4d0f-4cb7-add6-a2d6bb80f7b2`.
- Fix gate: two public tests passed on the first proposal.
- Independent review: zero findings and `accept`; no repair proposal was requested.
- Top-level outcome: `accepted`.
- Duration: `32.437s`.
- Tokens: 9,538 input, 1,841 output, 7,936 cached.
- Final Patch SHA-256: `b71635557b54a812a27001ca22626dffc3a87bd984f72d954878ce67af6fa2ce`.
- Manifest SHA-256 file hash:
  `48cdf052065b36d6fb39bf22df168820fa98f2875e1c544e1b18bdac2b177eea`.
- The 36-file Artifact was copied to `outputs/phase-4b-server-deepseek-issue-to-pr` and verified.
- Exact server API-key persistence scan: zero matches; lingering `prguard` processes: zero; source
  fixture repository: clean.

The local and server models chose semantically equivalent but byte-different implementations. The
local Patch lowercases before splitting/joining; the server Patch lowercases after joining. Both
passed their archived gates and independent review. This reinforces the fact boundary: Harness
inputs and evidence are replayable, while model output itself is not promised to be deterministic.

## `0.5.0` deployment hashes

- Wheel: `93d18dbd246e58e834ce000e4d21e48ee84fa01b9c804cc66137144d090f67b3`.
- Source archive: `717b2dcc4a44a8cb8177fe2dbea1b931fa62eb1a27e8ea35e4eae8d00fd201e1`.
- Frozen Issue-to-PR case archive:
  `5d92788ef45504674ba980293624d7e14c54b27e15ec5639f7f4e3ce4c3b410d`.

All three hashes were checked on the server before offline installation and execution. The source
and case archives contained zero AppleDouble `._*` files.
