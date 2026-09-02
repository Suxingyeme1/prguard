# Selective Reviewer routing evidence

Frozen: 2026-08-23
PRGuard: 0.9.0
Policy: `review-routing-v1`

This is a two-case routing-only shadow check on accepted source changes from frozen public
repositories. It is not a routing-accuracy benchmark and does not justify making selective mode the
default. Shadow mode records what the selective policy would recommend while keeping the contract's
effective route at `review`; these two evidence runs did not retain same-Patch Reviewer outcomes.

| Case | Targeted deterministic gate | Static routing evidence | Recommendation | Wider check |
| --- | --- | --- | --- | --- |
| PrettyTable #474 source-only change | 21 HTML tests passed | exact symbol; 2 direct/3 transitive callers; the only reachable test file was explicitly selected | `skip`, score 0/5 | 338 passed |
| Humanize #366 source-only change | 76 filesize tests + Ruff passed | exact symbol; selected filesize tests covered one path, but `tests/test_i18n.py` remained statically reachable and benchmark tests remained related | `review`, score 9/5 | 700 passed, 74 optional benchmark skips; Ruff passed |

Both source changes are the source components of previously Harness-accepted Patches. They were
replayed afresh at the exact Base Commits shown in `run-summary.json`. The source-only PrettyTable
Patch passed all 338 existing tests, but a later same-Patch Reviewer and paired evaluator check
confirmed a multi-table regression; its post-run label is therefore defective. The source-only
Humanize Patch passed all 700
non-benchmark tests plus Ruff; the optional benchmark module was excluded because its plugin was
not installed.

This pair now exposes both routing errors. PrettyTable supplies a real-repository `skip`
recommendation backed by an explicitly selected reachable test file, but the missed multi-table
state interaction makes it one observed False Skip. Humanize is an evaluator-confirmed clean Patch
that still receives `review` because its targeted gate omits a statically reachable test, making it
one observed False Route (avoidable Reviewer selection), not a false block.

The routing JSON files are path-free copies of the versioned `ReviewRoutingResult`. They bind the
Patch SHA-256 to the frozen Base Commit plus the verified Fix and Harness Manifest payload hashes.
Raw recursive runs remain local because they contain machine paths; the public files are separately
hashed by `manifest.json`. The later
[v0.10 Shadow scorecard](../shadow-scorecard/README.md) now reports paired Reviewer coverage as 3/3.
It keeps the observed False Skip as an activation blocker instead of treating the original existing
test pass as a permanent clean label. The paired Humanize Review accepted the Patch and reported a
nonblocking missing-regression-test finding; the paired PrettyTable flow repaired its confirmed
defect and passed the full 340-test suite.

Verify the public bytes with:

```bash
uv run python scripts/verify_public_evidence.py
```
