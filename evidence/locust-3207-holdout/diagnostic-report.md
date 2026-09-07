# Locust #3207 PRGuard false-accept diagnostic

> Generated: 2026-09-07T10:59:49
> Source root: `.` (repository root)

## Summary

- Tests: 3; passed: 0; failed: 3.
- Failed cases mapped: 3/3.
- Deduplicated issues: 1.
- All source anchors verified: `true`.

## Issues

| ID | Severity | Classification | Status | Failed cases | Primary source | Suggestion |
|---|---|---|---|---:|---|---|
| PRGUARD-LOCUST-001 | P1 | product_defect | confirmed | 3 | `src/prguard/reviewer/compatibility.py:181-265` | Combine explicit invariant/ownership reasoning with a deterministic required-to-fallback review signal. |

## Details

### PRGUARD-LOCUST-001 · Missing invariant tracing allowed a symptom-suppressing Patch and false accept

- Severity/classification/status/confidence: `P1` / `product_defect` / `confirmed` / `high`.
- Evidence: The one-line candidate passed 12 public tests but failed the precommitted CPython 3.13 evaluator. Independent Review accepted it with zero findings at both 12- and 24-call budgets. The upstream ownership/lifetime repair passed the same sealed evaluator after reveal.
- Root cause: PRGuard supplied general protocol-change evidence but did not explicitly require either Agent to distinguish required state from valid optional state or trace the missing mapping key to its producer and object lifetime. The Implementer therefore changed the exception consumer from a required lookup to a fallback, and both Reviewers treated the fallback as safe because normal construction populated the key.
- Source:

  - `src/prguard/reviewer/compatibility.py:181-265` — `analyze_python_compatibility` — `verified` — Deterministic Base/Candidate analysis now emits a bounded signal for the missed required-to-fallback access shape.
  - `src/prguard/implementer/providers.py:420-424` — `_INSTRUCTIONS` — `verified` — Implementer remediation requires tracing the state producer and lifecycle before editing the failure consumer.
  - `src/prguard/reviewer/providers.py:157-163` — `_INSTRUCTIONS` — `verified` — Reviewer remediation makes a consumer-side fallback blocking unless repository evidence establishes valid absence semantics.

- Recommendation: Combine explicit invariant/ownership reasoning with a deterministic required-to-fallback review signal.
  1. Require the Implementer to inspect state creation, aliasing, mutation, and release before proposing a downstream fallback.
  2. Provide the same root-cause criterion to the independent Reviewer and treat the signal as an inspection request rather than an automatic verdict.
  3. Regression-test the structural signal on the contaminated Patch, then evaluate quality only on a fresh precommitted holdout.
- Acceptance: The exact Locust candidate produces a required-to-fallback compatibility signal and both provider contracts contain the invariant-tracing criterion; all repository tests and Ruff pass. No improved held-out accuracy is claimed until a fresh case completes.
- Regression cases: `tests/unit/test_reviewer_compatibility.py::test_reports_required_mapping_lookup_replaced_by_fallback`, `tests/contracts/test_deepseek_provider_contract.py::test_deepseek_adapter_runs_bounded_chat_tool_loop`, `tests/contracts/test_deepseek_reviewer_contract.py::test_deepseek_reviewer_has_independent_bounded_context`.

## Failed-case mapping

| Case | Category | Symptom | Issues |
|---|---|---|---|
| `locust_3207_candidate_task_resolution` | implementer_resolution | {'expected': 'candidate passes the precommitted CPython 3.13 evaluator', 'actual': 'candidate still fails with missing … | `PRGUARD-LOCUST-001` |
| `locust_3207_reviewer_budget_12` | review_quality | {'expected': 'blocking finding for a symptom-suppressing candidate', 'actual': 'accept with zero findings', 'read_tool_… | `PRGUARD-LOCUST-001` |
| `locust_3207_reviewer_budget_24` | review_quality | {'expected': 'blocking finding for a symptom-suppressing candidate', 'actual': 'accept with zero findings', 'read_tool_… | `PRGUARD-LOCUST-001` |
