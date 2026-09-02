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

## Routing modes

Reviewer routing applies only after the Implementer Patch has passed its deterministic Harness
gate. A Patch that does not apply, times out, fails a command, or violates policy is already stopped
by the deterministic workflow; sending that Patch to a Reviewer does not count as incremental
defect prevention.

PRGuard distinguishes the routing recommendation from the route that is actually executed:

| Mode | Recommendation | Effective route | Intended use |
| --- | --- | --- | --- |
| `always` | Review every accepted Fix | Review | Compatibility baseline and the safest initial deployment |
| `shadow` | Compute `review` or `skip` | Review regardless | Collect paired Reviewer outcomes without allowing the heuristic to skip |
| `selective` | Compute `review` or `skip` | Follow the recommendation | Avoid Reviewer latency and spend after the policy has enough shadow evidence |

Shadow mode is the useful small-sample starting point. It preserves the exact decision that a
selective policy would have made while still running the independent Reviewer. This produces the
Reviewer verdict, findings, token use, latency, and optional repair outcome needed to assess the
recommendation. Selective mode intentionally gives up that counterfactual on skipped cases, so it
should not be the first source of routing evidence.

The routing score is a sum of versioned evidence weights for observable facts such as a repair
round, candidate-controlled tests, an uncovered statically reachable test, a sensitive path, broad
change size, bounded static caller impact, or incomplete analysis. It is an activation score, not
a calibrated defect probability. A score of 7 does not mean a 70% defect chance, and scores from
different policy versions are not comparable without replaying the same cases.

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

Use the following terms consistently on evaluator-labelled, Harness-accepted Fixes:

- **False route:** the policy recommends `review` for a Patch that the evaluator confirms is clean.
  This measures unnecessary selection cost. It is not a false block when the Reviewer correctly
  accepts the Patch.
- **False skip:** the policy recommends `skip` for a Patch with an evaluator-confirmed defect. In
  shadow mode the paired Reviewer run can additionally show whether the Reviewer would have found
  that defect. In selective production, a skipped Patch has no such counterfactual unless it is
  later audited; absence of a reported incident is not proof of zero false skips.
- **False block:** an effective Reviewer run returns `request_changes` on an evaluator-confirmed
  clean Patch. This is a Reviewer-verdict error, not a routing error. A clean Patch can therefore be
  both a false route and a false block, or a false route without being false-blocked.

Report counts and denominators, not only rates:

```text
false-route rate = false routes / evaluator-confirmed clean accepted Fixes
false-skip rate  = false skips / evaluator-confirmed defective accepted Fixes
false-block rate = false blocks / evaluator-confirmed clean effective reviews
```

A helpful route requires more than recommending review: the Reviewer must produce a manually
confirmed, evidence-backed finding that the deterministic gate did not already block. Repair and
final regression evidence are then charged to the same case when calculating net value.

Two labelled cases are not enough for a routing threshold. The next useful expansion is several
manually checked repository-level cases stratified by targeted/broad gate, direct/repair Fix,
ordinary/sensitive path, narrow/broad change, and complete/incomplete static analysis—not a large
generic benchmark or additional Agent role. Freeze the policy first, run those cases in shadow
mode, publish the raw counts and costs, and only then decide whether selective skipping is justified.

The v0.10.1 [executable scorecard](../evidence/shadow-scorecard/README.md) enforces this boundary in
code. Its three joined routes produce False Route 1/1 and False Skip 1/2. The skipped PrettyTable
Patch passed every declared existing test, but a same-Patch Reviewer identified a multi-table state
regression that Base/Candidate replay confirmed. This is direct incremental benefit from Review and
direct evidence that `review-routing-v1` is not ready to skip by default. Humanize still lacks an
exact-Patch paired Reviewer result, so the fractions remain observed case counts rather than
calibrated accuracy.
