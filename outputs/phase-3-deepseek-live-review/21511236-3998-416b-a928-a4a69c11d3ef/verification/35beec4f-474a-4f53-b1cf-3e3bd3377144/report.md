# PRGuard run `35beec4f-474a-4f53-b1cf-3e3bd3377144`

- Case: `regression-verification`
- Outcome: **failed_verification**
- Base commit: `6381e7b514f63bc12a562ef750e6595ca979d18c`
- Duration: 0.615s
- Patch applied: True

## Verification

| # | Kind | Command | Exit | Timeout | Passed | Duration |
|---:|---|---|---:|---|---|---:|
| 0 | fail_to_pass | `pytest -q tests/test_new_behavior.py` | 0 | False | True | 0.237s |
| 1 | pass_to_pass | `pytest -q tests/test_regression.py` | 1 | False | False | 0.186s |

## Changed files

- `service.py`

## Policy violations

- None
