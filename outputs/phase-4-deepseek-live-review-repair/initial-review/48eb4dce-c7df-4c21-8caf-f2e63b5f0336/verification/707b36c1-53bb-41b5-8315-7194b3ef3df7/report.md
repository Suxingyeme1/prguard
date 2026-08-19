# PRGuard run `707b36c1-53bb-41b5-8315-7194b3ef3df7`

- Case: `deepseek-live-review-repair-regression-verification`
- Outcome: **failed_verification**
- Base commit: `6381e7b514f63bc12a562ef750e6595ca979d18c`
- Duration: 0.644s
- Patch applied: True

## Verification

| # | Kind | Command | Exit | Timeout | Passed | Duration |
|---:|---|---|---:|---|---|---:|
| 0 | fail_to_pass | `pytest -q tests/test_new_behavior.py` | 0 | False | True | 0.235s |
| 1 | pass_to_pass | `pytest -q tests/test_regression.py` | 1 | False | False | 0.183s |

## Changed files

- `service.py`

## Policy violations

- None
