# PRGuard run `16fd1da4-4387-4700-bcf4-3cb69531dc88`

- Case: `real-inflect-242-fix-attempt-0`
- Outcome: **passed**
- Base commit: `f612162c36f057fc18a97b0ddfec9c4bccaaa5af`
- Duration: 2.540s
- Patch applied: True

## Verification

| # | Kind | Command | Exit | Timeout | Passed | Duration |
|---:|---|---|---:|---|---|---:|
| 0 | pytest | `pytest -q tests/test_prguard_issue_242.py` | 0 | False | True | 1.159s |
| 1 | pytest | `pytest -q tests/test_numwords.py` | 0 | False | True | 1.099s |

## Changed files

- `inflect/__init__.py`

## Policy violations

- None
