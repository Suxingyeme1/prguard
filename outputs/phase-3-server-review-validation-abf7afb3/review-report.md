# PRGuard review run `abf7afb3-ab14-44a4-b0b0-7c3391055d82`

- Case: `regression`
- Outcome: **reviewed**
- Verdict: **request_changes**
- Base commit: `21badd894f8b5f4376d930cfa9aa012d71c870f6`
- Duration: 19.257s

## Findings

- **P2** `service.py:4` — normalize no longer lowercases non-None input, so previously normalized output such as normalize(" HELLO ") changes from "hello" to "HELLO".
  - Evidence: Patched service.py line 4 is `return value.strip()`, whereas the base implementation was `return value.strip().lower()`. The pass_to_pass test `tests/test_regression.py::test_normalize_preserves_lowercase_contract` asserts `normalize(" HELLO ") == "hello"` and fails with `AssertionError: assert 'HELLO' == 'hello'`.
  - Verify: Run `pytest -q tests/test_regression.py`; it exits 1 and reports the assertion failure at tests/test_regression.py:5.
