# Independent Reviewer value evidence

Frozen: 2026-08-23<br>
PRGuard: 0.8.0<br>
Provider: DeepSeek `deepseek-v4-pro`, high reasoning

This is a deliberately small decision-oriented pair, not a benchmark score. It asks whether an
independently scoped Reviewer can add defect signal beyond the configured deterministic gate, and
what it costs on a Patch already supported by wider evidence.

| Case | Base gate | Reviewer | Final evidence | Duration / tokens |
| --- | --- | --- | --- | --- |
| Known normalization regression | passed its narrow new-behavior test | 1 manually confirmed P2; `request_changes` | one exact repair; fail-to-pass 1/1 and pass-to-pass 1/1 | review 26.150 s; 6,902 input / 1,644 output |
| Humanize #366 accepted Patch | 78 passed + Ruff; wider 702 passed, 74 skipped | 0 findings; `accept`; no false block | Patch unchanged | review 221.875 s; 113,796 input / 14,780 output |

The regression label and finding disposition were evaluator-only and were never serialized into
the Reviewer Task or provider context. The positive Reviewer cited `service.py:4` and the public
`tests/test_regression.py`; the configured base gate had run only `tests/test_new_behavior.py` and
passed. A separate controlled-repair run restored lowercase normalization with one exact edit, and
an evaluator gate then passed both tests.

On the clean Humanize case, the Reviewer correctly avoided a false block and exercised AST symbol
and reference navigation. It still added 221.875 seconds—159.2% of the preceding 139.357-second Fix
duration—and made the sequential Fix-plus-Review path 2.59x as long. That case has zero observed
defect benefit and positive cost.

Observed finding precision and recall are both 1/1 on the single labelled defect, and false block is
0/1 on the single labelled clean Patch. Those fractions are case checks, not population estimates.
They justify preserving an optional independent Reviewer and measuring selective activation; they
do not justify enabling it unconditionally or claiming general accuracy.

The selected final Patches are authenticated by [manifest.json](manifest.json). Raw recursive run
artifacts remain frozen locally because they contain machine paths; the manifest records their
self-authenticating payload hashes. Verify the public Patch bytes with:

```bash
uv run python scripts/verify_public_evidence.py
```
