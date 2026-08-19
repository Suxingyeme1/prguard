# PRGuard run `b5d7c56e-152a-44d6-9484-17c0bb9c8de0`

- Case: `real-prettytable-474-fix-attempt-0`
- Outcome: **passed**
- Base commit: `f7871e3ecb1d51ee5320d567a4e3eb42cea7fe75`
- Duration: 1.030s
- Patch applied: True

## Verification

| # | Kind | Command | Exit | Timeout | Passed | Duration |
|---:|---|---|---:|---|---|---:|
| 0 | pytest | `pytest -q tests/test_prguard_issue_474.py` | 0 | False | True | 0.399s |
| 1 | pytest | `pytest -q tests/test_html.py` | 0 | False | True | 0.346s |

## Changed files

- `src/prettytable/prettytable.py`

## Policy violations

- None
