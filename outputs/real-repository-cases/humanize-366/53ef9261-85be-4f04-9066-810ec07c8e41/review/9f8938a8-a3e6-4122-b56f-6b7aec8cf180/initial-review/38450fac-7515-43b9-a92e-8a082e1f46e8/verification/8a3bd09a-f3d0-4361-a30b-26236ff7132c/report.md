# PRGuard run `8a3bd09a-f3d0-4361-a30b-26236ff7132c`

- Case: `real-humanize-366-independent-review-verification`
- Outcome: **passed**
- Base commit: `431dbbed77d867519447e02eebf1a14879b80603`
- Duration: 0.679s
- Patch applied: True

## Verification

| # | Kind | Command | Exit | Timeout | Passed | Duration |
|---:|---|---|---:|---|---|---:|
| 0 | pytest | `pytest -q tests/test_prguard_issue_366.py` | 0 | False | True | 0.187s |
| 1 | pytest | `pytest -q tests/test_filesize.py` | 0 | False | True | 0.237s |

## Changed files

- `src/humanize/filesize.py`

## Policy violations

- None
