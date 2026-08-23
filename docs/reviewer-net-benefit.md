# When does the Independent Reviewer pay for itself?

The Reviewer is worthwhile on a task only when the expected loss avoided by evidence-backed defect
findings exceeds its full incremental cost:

```text
net value
  = prevented defect loss
  - false-block and rework loss
  - model/token spend
  - review latency
  - repair-introduced regression risk
```

This is a deployment decision, not a claim that more Agents are intrinsically better. PRGuard
records findings, false blocks, tokens, duration, repair rounds, and final regression outcomes so a
team can estimate the terms using its own defect severity and delivery costs.

## Frozen v0.8 pair

The [public evidence pair](../evidence/reviewer-value/README.md) provides one positive and one cost
case under the same Reviewer model and reasoning setting:

- A defective normalization Patch passed its configured narrow pytest gate. The independent
  Reviewer found the omitted lowercase behavior, cited the exact source and existing public test,
  and requested changes. A controlled one-edit repair passed both fail-to-pass and pass-to-pass.
- The accepted Humanize #366 Patch passed targeted and wider regression gates. The Reviewer found
  no defect and did not false-block it, but added 221.875 seconds and substantial token use.

Therefore the current evidence supports “Reviewer can create net benefit on gate-incomplete risk,”
not “Reviewer should run on every Patch.” Sensible future activation signals include narrow test
selection, changes to central/high-fan-in symbols, security-sensitive paths, broad call/reference
impact, weak project adaptation, or an Implementer repair round. Low-risk, well-covered changes can
remain Implementer-plus-Harness unless the repository's cost of escape justifies the latency.

## Measurement rules

- Count only manually confirmed findings caused or exposed by the candidate Patch.
- A deterministic failure the Harness already blocks is not incremental Reviewer benefit.
- Count a clean `request_changes` as a false block even if a repair later happens to pass.
- Credit a finding only after its reproduction condition or evaluator check confirms it.
- Charge all Reviewer and repair tokens, elapsed time, failed calls, and repair rounds.
- Keep evaluator labels outside Agent-visible Task, provider context, and public prompt fixtures.

Two labelled cases are not enough for a routing threshold. The next useful expansion is several
manually checked repository-level cases stratified by narrow/full gate and symbol impact—not a large
generic benchmark or additional Agent role.
