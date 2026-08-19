# PRGuard review run `48eb4dce-c7df-4c21-8caf-f2e63b5f0336`

- Case: `deepseek-live-review-repair-regression`
- Outcome: **reviewed**
- Verdict: **request_changes**
- Base commit: `6381e7b514f63bc12a562ef750e6595ca979d18c`
- Duration: 16.857s

## Findings

- **P2** `service.py:4` — `normalize` no longer lowercases non-None input, breaking the pre-existing normalization contract.
  - Evidence: Patched `service.py` line 4 returns `value.strip()` while the original returned `value.strip().lower()`. The regression test at `tests/test_regression.py:5` asserts `normalize(" HELLO ") == "hello"`, but the patched implementation returns `"HELLO"`.
  - Verify: Run `pytest -q tests/test_regression.py`; it fails with `AssertionError: assert 'HELLO' == 'hello'` at `tests/test_regression.py:5`. Restoring `.lower()` (e.g. `return value.strip().lower()`) makes the test pass while still satisfying `test_none_is_empty`.
