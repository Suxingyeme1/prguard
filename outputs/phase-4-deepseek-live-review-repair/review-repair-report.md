# PRGuard review-repair run `87ee7361-4c18-4e21-a3e6-6ff7dd7e0309`

- Case: `deepseek-live-review-repair-regression`
- Outcome: **accepted_after_repair**
- Final verdict: **accept**
- Base commit: `6381e7b514f63bc12a562ef750e6595ca979d18c`
- Initial review: `request_changes`
- Final verification: `passed`
- Duration: 33.725s

## Initial findings

- **P2** `service.py:4` — `normalize` no longer lowercases non-None input, breaking the pre-existing normalization contract.
  - Evidence: Patched `service.py` line 4 returns `value.strip()` while the original returned `value.strip().lower()`. The regression test at `tests/test_regression.py:5` asserts `normalize(" HELLO ") == "hello"`, but the patched implementation returns `"HELLO"`.
  - Verify: Run `pytest -q tests/test_regression.py`; it fails with `AssertionError: assert 'HELLO' == 'hello'` at `tests/test_regression.py:5`. Restoring `.lower()` (e.g. `return value.strip().lower()`) makes the test pass while still satisfying `test_none_is_empty`.

## Controlled repair

- Provider: `deepseek`
- Summary: Fix normalize to accept None as empty while restoring the original .lower() normalization for non-None values.
- Final patch: `final.patch`
