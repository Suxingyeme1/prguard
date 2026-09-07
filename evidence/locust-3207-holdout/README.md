# Locust #3207 compatibility holdout

Frozen: 2026-09-06 · Live Agent run: 2026-09-07 · Outcome: unresolved false accept

This package records a compatibility-focused Issue-to-Patch holdout for
[locustio/locust #3207](https://github.com/locustio/locust/issues/3207). The public Issue and exact
upstream Base Commit were Agent-visible. Later upstream changes, solution material, the evaluator
body, and its expected repair were excluded until the live Agent artifacts were frozen.

The source is fixed at `5df19da06a0f8418d44094f3014ddee3b307bb55` (Locust 2.40.1). Initial
deterministic discovery found the non-standard `locust/test` tree, but its full-suite Base run was
not accepted as a task gate because the checkout lacked separately built web assets and
console-script installation behavior and included a host-sensitive timing assertion. A reviewed
operator policy therefore froze `pytest -q locust/test/test_http.py -k catch_response` as the public
regression gate.

## Live result

On the Linux server, the unchanged Base passed the 12-test public gate under CPython 3.12.4 and
3.13.5. The DeepSeek Implementer used 24 bounded tool calls and produced a one-line Patch that
changed `request_meta["name"]` to `request_meta.get("name", self.url)`. That candidate also passed
the public gate.

The Independent Reviewer accepted it with zero findings at the default 12-call read budget. A
second independent run with 24 calls also accepted it with zero findings. The second run used more
than three times the tokens and time, so this observation does not support “more read budget” as a
fix.

After both Reviews were archived, the precommitted evaluator was attached. It failed on the exact
candidate under CPython 3.13: the Patch hid the missing key at the consumer but did not repair the
earlier request-object ownership/lifetime failure. The upstream repair passed the evaluator and 28
relevant public tests. Under CPython 3.12 the unchanged Base already passed the evaluator, and
PRGuard correctly rejected it as a FAIL_TO_PASS test for that runtime.

This is not a resolution claim. It is a verified **False Accept** for both Reviewer budgets and a
failed Task Resolution for the Implementer. The candidate, raw public Agent reports, normalized
diagnostic mapping, and recursive hashes are retained so the failure can be replayed and audited.
The generated [source-linked diagnostic report](diagnostic-report.md) maps all three failed
observations to one confirmed issue and verifies three repository-relative source anchors.

## Leakage and Artifact boundary

- `candidate.patch`, `implementer-report.json`, and the two Reviewer reports are public.
- The evaluator source and Gold Patch remain unpublished.
- Evaluator outcomes and hashes are public, but their raw artifacts stay in root-only server
  storage.
- All Agent/Reviewer processes ran as the unprivileged `prguard` account and could not read the
  sealed evaluator directory.
- The pre-run evaluator source commitment is
  `763d7082e4cc35990ad03ddc8efbcb7a1673c006e40bc537d6c5fa03669960c1`.

## Post-failure hardening

After reveal, PRGuard added a bounded AST signal for required string-key lookups changed into
fallback lookups. Implementer and Reviewer guidance now requires tracing missing state to its
producer, ownership, aliasing, mutation, and release boundary. This contaminated replay proves only
that the new signal is emitted; it does not establish improved held-out accuracy.

See the [v0.13.5 phase report](../../docs/v0.13.5-phase-report.md) and
[ADR 0030](../../docs/adr/0030-required-state-fallbacks-trigger-root-cause-review.md).
