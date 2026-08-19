# PRGuard run `c1c9e375-8ec5-4de3-8e09-711d2ddf5c40`

- Case: `real-humanize-366-attempt-0`
- Outcome: **passed**
- Base commit: `431dbbed77d867519447e02eebf1a14879b80603`
- Duration: 0.881s
- Patch applied: True

## Verification

| # | Kind | Command | Exit | Timeout | Passed | Duration |
|---:|---|---|---:|---|---|---:|
| 0 | pytest | `pytest -q tests/test_prguard_issue_366.py` | 0 | False | True | 0.295s |
| 1 | pytest | `pytest -q tests/test_filesize.py` | 0 | False | True | 0.235s |

## Changed files

- `src/humanize/filesize.py`

## Policy violations

- None
