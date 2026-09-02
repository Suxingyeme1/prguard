# Shadow Reviewer scorecard

Frozen: 2026-09-02  
Policy: `review-routing-v1`

| Case | Source | Label | Route | Reviewer | Confirmed incremental findings |
| --- | --- | --- | --- | --- | ---: |
| `prettytable-474-source-only-shadow` | real_repository | clean | skip (0/5) | not observed | 0 |
| `humanize-366-source-only-shadow` | real_repository | clean | review (9/5) | not observed | 0 |
| `normalization-regression-shadow` | deterministic_fixture | defective | review (7/5) | request_changes | 1 |

## Derived counts

- False route: 1/2
- False skip: 0/1
- False block: 0/0
- Paired Reviewer coverage: 1/3
- Defective cases caught by Reviewer: 1/1
- Confirmed incremental findings: 1
- Observed Reviewer cost: 26.150s, 6902 input / 1644 output tokens, 1 repair round(s)

## Selective activation decision

Selective Review remains opt-in; the frozen evidence is incomplete:

- paired Reviewer outcome coverage is 1/3
- no evaluator-confirmed defective real-repository case

These are observed case counts, not population accuracy estimates. Evaluator labels were applied after Agent execution and are not part of Fix or Review task schemas.
