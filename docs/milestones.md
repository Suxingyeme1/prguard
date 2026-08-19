# Product milestones

## Phase 0: facts and contracts — complete

Freeze product/non-goal language, Pydantic contracts, security boundary, artifact rules, review
severity policy, and the compact evaluation protocol.

## Phase 1: deterministic harness — complete

Load a local Git repository and base commit, create an isolated worktree, apply a candidate patch,
execute pytest/ruff through an argv allowlist, enforce deadlines, audit protected/outside writes,
and emit JSON/Markdown/diff artifacts with a SHA-256 manifest.

## Phase 2: single Implementer Issue-to-Patch MVP — real-repository gate complete

Implement repository search, bounded source reads, an internal plan, restricted source/test edits,
candidate diff production, deterministic verification, and at most one repair from failure
evidence. Deliver a demonstrable `prguard fix` CLI. No separate Planner Agent.

Acceptance: given a real local repository, base commit, and Issue, the system produces a minimal,
tested Review-ready Patch or an evidence-backed failure without modifying the source checkout.

Implemented evidence includes a working `fix` CLI, provider contract, bounded repository tools,
Patch policy, direct success and one-repair fixtures, nested artifacts, security tests, and three
accepted real-repository Issue outcomes at frozen Humanize, PrettyTable, and Inflect commits. The
Humanize final run used one bounded replacement attempt and passed pytest plus ruff; all three
received wider functional regression checks. This remains a three-case engineering gate, not a
general task-resolution benchmark.

### Phase 2.1: DeepSeek live-provider gate — minimum gate complete

The provider-neutral boundary now includes a DeepSeek Chat Completions adapter with bounded
function calls, thinking-context preservation, token/cache accounting, backend fingerprint
metadata, environment-only credentials, and unsafe endpoint rejection. Its offline API contract is
tested. Two explicitly authorized fixture runs and three real-repository Issue outcomes were
accepted by deterministic gates; one real-repository case also completed independent review.
Frozen failures expose provider latency, malformed diffs, and tool-budget exhaustion. Scripted
results remain orchestration evidence; only online runs are model task-resolution evidence.

## Phase 3: Independent Reviewer and `review` CLI — MVP complete

Add a read-only, independently scoped Reviewer that receives Issue, final diff, necessary source,
and test evidence—but not Implementer reasoning or evaluator secrets. Produce validated findings,
source anchors, evidence, reproduction steps, and deterministic verdict policy.

Implemented evidence includes scripted defect/clean integration tests, a DeepSeek Reviewer contract,
recursive review artifacts, and two live cases: one known regression produced a source-linked P2
finding and `request_changes`; one correct patch produced no findings and `accept`. This is a
minimal two-case gate, not a precision/recall benchmark.

## Phase 4A: controlled review repair — minimum live gate complete

Allow one controlled repair after an independently scoped review requests changes. Re-run the final
gate and produce a review-ready Patch plus report.

Implemented evidence includes a versioned review-repair contract, the `review --repair` CLI,
one Base-Commit-relative replacement attempt, structured public feedback, a fresh final Harness
worktree, recursive SHA-256 artifacts, and offline success/failure/no-op/policy cases. The seeded
DeepSeek Demo B passed locally and on the unprivileged server environment with identical final
Patch hashes.

## Phase 4B: composed Issue-to-PR — local MVP complete

Attach the Reviewer after a successful `fix` result so one command owns Issue localization,
initial Patch generation, independent review, optional replacement repair, final gate, and a single
top-level manifest. Then run the compact single/self/independent comparison to measure net Reviewer
value rather than treating A/B as the product.

Implemented evidence includes `IssueToPRTask` stage budgets, `fix --review`, short-circuiting after
Fix failure, independent semantic review of a regression not covered by the configured command,
one controlled replacement repair, and a recursive top-level Manifest. A live DeepSeek run produced
an accepted Fix Patch locally and on the unprivileged server, passed independent review without
unnecessary repair, and verified both recursive Manifests. A Humanize Issue has also completed the
full live Issue-to-PR path on a real repository, while revealing that a 300-second Reviewer result
could return after the logical budget. The runner now fails closed on any post-deadline Reviewer
result. Reviewer net-benefit evidence across the three-case set remains future work.

## Phase 5: evidence-driven hardening

Add a Diagnostician only if observed failures show that deterministic logs plus Implementer repair
are insufficient. Add container/network/resource isolation before running hostile repositories,
and service/GitHub integrations only after local CLI contracts stabilize.

The first Phase 5 increment is public-product hardening: a concise GitHub landing page, a key-free
offline Demo A, continuous integration, contribution/security policies, and a sanitized public
evidence subset. This work must not rewrite frozen raw Manifests; public summaries are derived and
separately hashed.

## Priority demos

1. **Demo A:** Issue -> repository localization -> minimal code/test edits -> verification -> one
   repair -> Review-ready Patch.
2. **Demo B:** defective candidate PR -> source-linked Reviewer finding -> controlled repair ->
   final deterministic gate.
