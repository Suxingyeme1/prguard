# Selective Reviewer routing evidence

Frozen: 2026-08-23
PRGuard: 0.9.0
Policy: `review-routing-v1`

This is a two-case shadow check on accepted source changes from frozen public repositories. It is
not a routing-accuracy benchmark and does not justify making selective mode the default. Shadow
mode records what the selective policy would recommend while still keeping the effective route at
`review`.

| Case | Targeted deterministic gate | Static routing evidence | Recommendation | Wider check |
| --- | --- | --- | --- | --- |
| PrettyTable #474 source-only change | 21 HTML tests passed | exact symbol; 2 direct/3 transitive callers; the only reachable test file was explicitly selected | `skip`, score 0/5 | 338 passed |
| Humanize #366 source-only change | 76 filesize tests + Ruff passed | exact symbol; selected filesize tests covered one path, but `tests/test_i18n.py` remained statically reachable and benchmark tests remained related | `review`, score 9/5 | 700 passed, 74 optional benchmark skips; Ruff passed |

Both source changes are the source components of previously accepted, manually checked Patches.
They were replayed afresh at the exact Base Commits shown in `run-summary.json`. The source-only
PrettyTable Patch passed all 338 existing tests. The source-only Humanize Patch passed all 700
non-benchmark tests plus Ruff; the optional benchmark module was excluded because its plugin was
not installed.

This pair shows both sides of the conservative policy. PrettyTable supplies a real-repository
`skip` recommendation backed by an explicitly selected reachable test file. Humanize is an
evaluator-confirmed clean Patch that still receives `review` because its targeted gate omits a
statically reachable test. Under the evaluation vocabulary this Humanize recommendation is one
observed false route (avoidable Reviewer selection), not a false block. There are no labelled
defective cases in this pair, so it says nothing about a false-skip rate.

The routing JSON files are path-free copies of the versioned `ReviewRoutingResult`. They bind the
Patch SHA-256 to the frozen Base Commit plus the verified Fix and Harness Manifest payload hashes.
Raw recursive runs remain local because they contain machine paths; the public files are separately
hashed by `manifest.json`.

Verify the public bytes with:

```bash
uv run python scripts/verify_public_evidence.py
```
