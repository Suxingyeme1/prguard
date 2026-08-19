# PRGuard run `ee0820b9-f46b-47d8-a9f4-af79c7a5ab1a`

- Case: `real-humanize-366-fix-with-lint-attempt-1`
- Outcome: **passed**
- Base commit: `431dbbed77d867519447e02eebf1a14879b80603`
- Duration: 1.013s
- Patch applied: True

## Verification

| # | Kind | Command | Exit | Timeout | Passed | Duration |
|---:|---|---|---:|---|---|---:|
| 0 | pytest | `pytest -q tests/test_prguard_issue_366.py` | 0 | False | True | 0.294s |
| 1 | pytest | `pytest -q tests/test_filesize.py` | 0 | False | True | 0.237s |
| 2 | lint | `ruff check src/humanize/filesize.py` | 0 | False | True | 0.131s |

## Changed files

- `src/humanize/filesize.py`

## Policy violations

- None
