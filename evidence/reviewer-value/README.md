# Independent Reviewer value evidence

Frozen: 2026-09-02<br>
PRGuard: 0.10.2<br>
Provider: DeepSeek `deepseek-v4-pro`, high reasoning

This is a deliberately small decision-oriented set, not a benchmark score. It asks whether an
independently scoped Reviewer can add defect signal beyond the configured deterministic gate, and
what it costs on a Patch already supported by wider evidence.

| Case | Base gate | Reviewer | Final evidence | Duration / tokens |
| --- | --- | --- | --- | --- |
| Known normalization regression | passed its narrow new-behavior test | 1 manually confirmed P2; `request_changes` | one exact repair; fail-to-pass 1/1 and pass-to-pass 1/1 | review 26.150 s; 6,902 input / 1,644 output |
| Humanize #366 accepted Patch | 78 passed + Ruff; wider 702 passed, 74 skipped | 0 findings; `accept`; no false block | Patch unchanged | review 221.875 s; 113,796 input / 14,780 output |
| Humanize #366 source-only Patch | 76 passed + Ruff; wider 700 passed, 74 skipped | 1 confirmed nonblocking P3 test gap; `accept`; no false block | Patch unchanged | review 268.938 s; 128,665 input / 13,633 output |
| PrettyTable #474 source-only Patch | 21 targeted and 338 wider existing tests passed | 1 manually confirmed P2; `request_changes` | one controlled repair; 23 targeted and 340 full-suite tests passed | review 167.619 s; repair flow 301.252 s total |

The regression label and finding disposition were evaluator-only and were never serialized into
the Reviewer Task or provider context. The positive Reviewer cited `service.py:4` and the public
`tests/test_regression.py`; the configured base gate had run only `tests/test_new_behavior.py` and
passed. A separate controlled-repair run restored lowercase normalization with one exact edit, and
an evaluator gate then passed both tests.

On the clean Humanize case, the Reviewer correctly avoided a false block and exercised AST symbol
and reference navigation. It still added 221.875 seconds—159.2% of the preceding 139.357-second Fix
duration—and made the sequential Fix-plus-Review path 2.59x as long. That case has zero observed
defect benefit and positive cost.

On PrettyTable, the Reviewer found evidence missing from both the targeted and wider existing test
suites. The source-only Patch correctly pads a ragged row but leaves `max_row_width` shared across
multiple `<table>` elements, so a later two-column table following a three-column table gains an
empty field and cell. The paired evaluator check passes at the frozen Base Commit and fails after
the exact candidate Patch. The frozen router had recommended `skip` at 0/5, making this both an
incremental Reviewer finding and an observed False Skip for `review-routing-v1`. A fresh composed
run reproduced the same P2 finding, gave only that structured evidence to the Implementer, and
accepted one replacement Patch that resets per-table width state and adds short-row plus
multi-table regression tests. Its final Harness gate passed 23 targeted tests; a separate wider
Harness run passed all 340 tests and reran the 23 changed tests, with no policy violations.

The exact source-only Humanize Review completed the previously missing scorecard pair. It accepted
the functional fix and did not false-block it, while correctly noting that the Issue's prefix/suffix
format reproduction was absent from the existing tests. Because P3 is nonblocking, no repair was
triggered. This is useful signal with positive latency and Token cost, not a prevented defect.

Both blocking findings on the two labelled defective cases were manually confirmed, and false
block is 0/1 on the exact clean Humanize shadow Patch. Those fractions are case checks, not
population estimates. The manifest also retains the earlier Humanize and PrettyTable observations
rather than overwriting their historical costs.
They justify preserving an optional independent Reviewer and measuring selective activation; they
do not justify enabling it unconditionally or claiming general accuracy.

The selected final Patches and the defective pre-repair candidate are authenticated by
[manifest.json](manifest.json). Raw recursive run artifacts remain frozen locally because they
contain machine paths; the manifest records their self-authenticating payload hashes. Verify the
public Patch bytes with:

```bash
uv run python scripts/verify_public_evidence.py
```
