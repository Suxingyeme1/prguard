# PRGuard run `6522537e-7990-49af-a36b-682693090633`

- Case: `deepseek-live-review-repair-regression-verification`
- Outcome: **failed_verification**
- Base commit: `6381e7b514f63bc12a562ef750e6595ca979d18c`
- Duration: 1.203s
- Patch applied: True

## Verification

| # | Kind | Command | Exit | Timeout | Passed | Duration |
|---:|---|---|---:|---|---|---:|
| 0 | fail_to_pass | `pytest -q tests/test_new_behavior.py` | 0 | False | True | 0.566s |
| 1 | pass_to_pass | `pytest -q tests/test_regression.py` | 1 | False | False | 0.565s |

## Changed files

- `service.py`

## Policy violations

- None
