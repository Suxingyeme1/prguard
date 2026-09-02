# Reviewer routing v2 candidate replay

Frozen: 2026-09-02
PRGuard: 0.10.3

`review-routing-v2` is a narrowly scoped correction to the frozen v1 policy. v1 treated the
PrettyTable source-only Patch as low risk because it changed one Python file, its statically
reachable test file was selected, and bounded caller counts were small. Independent Review later
showed that the changed factory encloses a parser class whose instance state survives across table
boundaries.

v2 adds one deterministic AST factor with weight 5, equal to the Review threshold:

```text
stateful_nested_factory_changed
```

It fires only when a changed function directly returns a nested class and at least one `self.*`
attribute is written from multiple methods. On the frozen replay:

| Case | Evaluator label | v1 | v2 | Explanation |
| --- | --- | --- | --- | --- |
| PrettyTable #474 source-only | defective | `skip` 0/5 | `review` 5/5 | returned parser class has cross-method state |
| Humanize #366 source-only | clean | `review` 9/5 | `review` 9/5 | unchanged uncovered-test factors |
| Normalization fixture | defective | `review` 7/5 | `review` 7/5 | unchanged uncovered-test factor |

This replay removes the observed v1 False Skip on the three known cases. It does **not** authorize
selective-by-default deployment: PrettyTable was used to design the signal, so this is corrective
replay rather than held-out evidence. The next gate is several manually checked real-repository
Patches that were not used to define v2, including ordinary stateful classes and truly low-risk
changes, to measure both missed defects and unnecessary Reviews.

The three route JSON files were recomputed from the original recursively verified Fix artifacts.
Each binds the same Base Commit, candidate Patch SHA-256, Fix Manifest, and Verification Manifest as
v1. `replay-summary.json` records the before/after decision without changing the original v1
artifacts.
