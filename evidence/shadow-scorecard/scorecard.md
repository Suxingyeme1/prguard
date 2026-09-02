# Shadow Reviewer scorecard

Frozen: 2026-09-02
Policy: `review-routing-v1`

| Case | Source | Label | Route | Reviewer | Confirmed incremental findings |
| --- | --- | --- | --- | --- | ---: |
| `prettytable-474-source-only-shadow` | real_repository | defective | skip (0/5) | request_changes | 1 |
| `humanize-366-source-only-shadow` | real_repository | clean | review (9/5) | accept | 1 |
| `normalization-regression-shadow` | deterministic_fixture | defective | review (7/5) | request_changes | 1 |

## Derived counts

- False route: 1/1
- False skip: 1/2
- False block: 0/1
- Paired Reviewer coverage: 3/3
- Defective cases caught by Reviewer: 2/2
- Confirmed incremental findings: 3
- Observed Reviewer cost: 462.707s, 232330 input / 23309 output tokens, 2 repair round(s)

## Selective activation decision

Selective Review remains opt-in; the frozen evidence does not authorize activation:

- 1 evaluator-confirmed false skip(s) under the frozen policy

These are observed case counts, not population accuracy estimates. Evaluator labels were applied after Agent execution and are not part of Fix or Review task schemas.
