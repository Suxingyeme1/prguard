# PRGuard run `954ac5eb-9548-4384-a7a5-509031a4a570`

- Case: `regression-verification`
- Outcome: **failed_verification**
- Base commit: `21badd894f8b5f4376d930cfa9aa012d71c870f6`
- Duration: 3.044s
- Patch applied: True

## Verification

| # | Kind | Command | Exit | Timeout | Passed | Duration |
|---:|---|---|---:|---|---|---:|
| 0 | fail_to_pass | `pytest -q tests/test_new_behavior.py` | 0 | False | True | 2.238s |
| 1 | pass_to_pass | `pytest -q tests/test_regression.py` | 1 | False | False | 0.646s |

## Changed files

- `service.py`

## Policy violations

- None
