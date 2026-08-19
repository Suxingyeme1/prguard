# PRGuard review run `21511236-3998-416b-a928-a4a69c11d3ef`

- Case: `regression`
- Outcome: **reviewed**
- Verdict: **request_changes**
- Base commit: `6381e7b514f63bc12a562ef750e6595ca979d18c`
- Duration: 18.004s

## Findings

- **P2** `service.py:4` — The patch removes the .lower() call that was part of normalize's existing contract, so inputs with uppercase characters are returned with original case instead of lowercased.
  - Evidence: service.py line 4 now returns value.strip() instead of value.strip().lower(). Verification run of tests/test_regression.py fails: assert normalize(" HELLO ") == "hello" produces AssertionError: assert 'HELLO' == 'hello'.
  - Verify: Run `pytest -q tests/test_regression.py`; test_normalize_preserves_lowercase_contract fails because normalize(" HELLO ") returns "HELLO" rather than "hello".
