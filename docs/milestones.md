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

The v0.8 follow-up makes `review` reuse a frozen FixTask plus a candidate Patch. In a new positive
case, the configured narrow pytest gate passed a defective Patch, while DeepSeek independently
found the omitted lowercase contract and cited the unexecuted public regression test. One exact
controlled repair then passed fail-to-pass and pass-to-pass. A clean Humanize #366 Patch was not
false-blocked but added 221.875 seconds of review latency. The
[net-benefit note](reviewer-net-benefit.md) records why this supports selective, not unconditional,
review.

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

The second increment adds a reproducible real-repository Demo A materializer plus `fix --progress`.
Stage updates and heartbeats go to stderr while the versioned JSON stdout contract stays stable. A
fresh Humanize #366 run exercised malformed-Patch rejection, one evidence-guided replacement, 77
passing pytest checks, and Ruff.

The third increment adds opt-in container-backed verification. Task contracts require an immutable
image ID and non-root identity; the Docker argv hard-codes no network, read-only root/worktree,
dropped capabilities, tmpfs runtime paths, and CPU/memory/PID limits. Host execution remains the
compatible default. The reference image has online and hash-locked offline build paths. Docker
Desktop passed the full boundary probe; a snap Docker incompatibility with `no-new-privileges`
failed closed and left no container rather than triggering a weaker retry.

The fourth increment removes most manual Task authoring for public Python repositories. A
`prepare-github` entry freezes the Issue and exact commit, materializes a safe checkout, accepts a
reviewed `.prguard.toml` or discovers a conservative pytest/Ruff profile, and emits a preparation
report plus verifiable Manifest. The Agent now has bounded Python AST symbol/import/re-export,
incoming/outgoing call, reference, and related-test tools. Live providers prefer exact structured
text edits; PRGuard applies them in an isolated worktree and Git produces the auditable Patch.
Issue symbols can narrow pytest to related public tests, declared Hatch VCS version files receive a
recorded runtime-only scaffold, and pytest collection readiness now fails before any provider call.
The post-adapter Humanize #366 live run was accepted in one Implementer attempt with two structured
edits, passed 78 targeted checks plus Ruff, and then passed a wider 702-test regression gate with 74
optional benchmark skips. Both recursive Manifests verified. The earlier environment failure is
retained and documented in the [v0.8 phase report](v0.8.0-phase-report.md).

The fifth increment removes the remaining normal-path handoff between preparation and execution:
`prguard fix` now accepts either a Task JSON or canonical public GitHub Issue URL. URL mode requires
an explicit new workspace and execution boundary, preserves the preparation Task/report/Manifest,
then writes Fix artifacts under the same owned workspace. The two-stage `prepare-github` path
remains available for human or CI approval. A key-free Humanize #366 composition replay verified
both Manifests and the clean source checkout; it is orchestration evidence, not a second live-model
success claim.

The sixth increment uses PrettyTable #474 to harden repository navigation and project adaptation.
Expected provider failures now retain partial tool/Token evidence; 250 KB Python modules remain
inside the bounded AST/text index; Issue-aware test ranking preserves qualified symbols; the model
receives a remaining read budget plus a terminal-only submission slot; and declared non-pytest
gates must prove Base-Commit readiness. Ruff is explicit `check --no-fix`, while any verification
command that changes the Candidate diff is policy-blocked. A fresh live run submitted structured
source/test edits in one attempt, passed 22 targeted tests, then passed all 339 tests in a separate
wider gate. The public Issue disclosed the root cause, so the
[v0.8.1 evidence](../evidence/navigation-hardening/README.md) supports navigation/orchestration
hardening rather than blind semantic-resolution accuracy.

The seventh increment deepens the Agent's internal code navigation without adding another Agent or
an execution privilege. `trace_call_graph` resolves one unambiguous Python symbol and walks callers,
callees, or both for at most three hops and a bounded number of edges. It reports repository versus
external nodes, source anchors, lexical resolution evidence, reachable test symbols, heuristic
related tests, and truncation. Re-export prefix resolution now maps public package aliases back to
defining methods. A deterministic run at the frozen PrettyTable #474 commit linked `from_html` to
`from_html_one`, its helper, and three tests across 7 nodes and 6 edges without executing source.
The [v0.8.2 phase report](v0.8.2-phase-report.md) keeps the claim at static navigation, not complete
runtime dispatch or new live-model accuracy.

The eighth increment turns that evidence into a deterministic post-Fix Reviewer router without
letting an Agent judge its own need for review. `always` remains the compatible default, `shadow`
records the selective recommendation while still reviewing, and only explicit `selective` can
skip. The policy binds Base Commit, exact Patch, Fix/Verification Manifests, pytest argv scope,
changed symbols, reachable tests, static fan-in, repair history, and analysis completeness; any
integrity mismatch stops the pipeline and any incomplete/static-unsupported case routes to review.
A frozen shadow pair produced one real-repository `skip` recommendation after 21 targeted and 338
wider PrettyTable tests, and one conservative Humanize `review` recommendation despite 76 targeted
plus 700 wider tests and Ruff because a reachable i18n test was outside the targeted gate. The
[v0.9.0 phase report](v0.9.0-phase-report.md) keeps selective opt-in until a broader labelled shadow
set can measure false skips and Reviewer net value.

The ninth increment adds a small executable Shadow scorecard rather than a benchmark platform.
Evaluator labels stay outside Agent schemas and are attached only after execution. Each case binds
the exact candidate Patch and routing Artifact by SHA-256; Reviewer evidence joins only when Base
Commit and candidate Patch hashes agree. The initial v0.10.0 table exposed incomplete paired
coverage rather than authorizing selective deployment.

The tenth increment runs the exact PrettyTable source-only Patch through live Independent Review.
The Reviewer found a cross-table state regression after 21 targeted and 338 wider existing tests
had passed; a paired Base/Candidate evaluator check confirmed it. The frozen three-case set now
derived False Route 1/1 and False Skip 1/2. An observed False Skip is itself an activation blocker.
See the
[v0.10.1 phase report](v0.10.1-phase-report.md).

The eleventh increment completes the exact-Patch Humanize Review and closes the real-repository
Demo B loop. Humanize was accepted with one nonblocking missing-regression-test finding. PrettyTable
was independently reviewed again, then the Implementer received only the structured P2 finding and
submitted one replacement Patch that reset per-table state and added two tests. The final targeted
gate passed 23 tests; a separate Harness run passed all 340 tests and reran the changed tests. The
scorecard now has 3/3 paired Reviewer coverage, False Block 0/1, three confirmed incremental
findings, and still blocks selective activation because False Skip remains 1/2. See the
[v0.10.2 phase report](v0.10.2-phase-report.md).

The twelfth increment versions the first routing correction instead of silently tuning the frozen
policy. `review-routing-v2` adds one deterministic AST factor for a changed factory that directly
returns a nested class with instance state written across multiple methods. It moves the known
defective PrettyTable Patch from `skip` 0/5 to `review` 5/5 while leaving Humanize and the
normalization regression recommendations unchanged. The replay binds every v1/v2 pair to the same
Base Commit and candidate Patch hashes. Because PrettyTable was also used to design the rule, the
activation record remains `not_ready` until a small manually labelled holdout set tests both misses
and unnecessary Reviews. See the [v0.10.3 phase report](v0.10.3-phase-report.md).

The thirteenth increment runs the first two clean real-repository holdout cases. Both Independent
Reviews accepted with zero findings, exposing 303.6 seconds and 405,253 input/output tokens of
review cost on those observations. The python-dotenv run also exposed contradictory v2 accounting:
an unfiltered full pytest run passed 217 tests, but related tests were still marked uncovered.
`review-routing-v3` records those tests as covered and changes that exact route from `review` 7/5 to
`skip` 0/5 while Inflect and all three prior correction cases retain their decisions. The same run
found and regression-tested eager repair-provider construction. Selective activation remains
`not_ready` because the set is small and has no new held-out defective case. See the
[v0.10.4 phase report](v0.10.4-phase-report.md).

The fourteenth increment evaluates v3 against the first genuinely defective held-out real Pull
Request. Click #3199 passed 1323 repository tests and a 9-test changed-file replay, but Independent
Review found that a new private default lookup bypassed the public overridable Context method. A
Base/Candidate evaluator check confirmed the extension-point regression. The case routed to Review,
so v3 avoided a False Skip. It also exposed a command aggregation bug: the later changed-test replay
downgraded an earlier full-suite scope to targeted. `review-routing-v4` fixes that accounting while
preserving the route (`review` 18/5), and keeps a clean python-dotenv #600 Patch at `skip` 0/5.
Selective activation remains `not_ready` because these counts are illustrative, not calibrated.
See the [v0.10.5 phase report](v0.10.5-phase-report.md).

The fifteenth increment closes the real Click Demo B with one controlled repair. A fresh Implementer
received the Issue, exact defective candidate, green gate evidence, and frozen Reviewer finding—but
not the evaluator, maintainer outcome, later upstream fix, or a Gold Patch. It returned four
structured edits that restored the public Context override path and added a regression test. A fresh
Harness passed 1324 full-suite tests and 10 changed-test replays; the hidden evaluator changed from
Base pass to Candidate fail to Repaired pass. The evidence includes the delivered Patch and raw
Artifact hashes. See the [v0.10.6 phase report](v0.10.6-phase-report.md).

The sixteenth increment removes hand-authored JSON from the local product entry. `fix` now accepts a
clean local Git repository plus inline Issue text or a bounded Issue file, resolves the requested
Base to an exact commit, freezes a detached checkout, discovers a conservative project policy, and
continues through the existing FixRunner. `prepare-local` preserves a two-stage inspection path.
Dirty sources, workspaces inside the source, symlink/NUL Issue files, and repository hooks are
covered by fail-closed tests. See the [v0.11.0 phase report](v0.11.0-phase-report.md).

The seventeenth increment adds `inspect-policy`, a read-only checkpoint for unfamiliar local
repositories. It resolves the clean Base Commit and explains discovery signals, exact verification
argv, edit scopes, protected paths, and blocking reasons without executing repository code. A ready
inferred policy includes a valid TOML candidate for human review; an unknown gate remains
`needs_config` and is never guessed. See the [v0.11.1 phase report](v0.11.1-phase-report.md).

The eighteenth increment adds a visual, dependency-light terminal demo over the real FixRunner and
Harness. A generated repository makes the first structured edit fail one pytest assertion, feeds
that evidence into the permitted repair, and renders the passing retry, final Patch, and Manifest
as one readable timeline. See the [v0.12.0 phase report](v0.12.0-phase-report.md).

The nineteenth increment adds a guided terminal entry for real local repositories while preserving
the frozen Task boundary. It also adds hash-guarded line-range and Python-symbol edits for repeated
source text, plus a fresh-Base probe that requires executable Agent-authored tests to demonstrate
FAIL_TO_PASS behavior. FileLock #606 is frozen as a new holdout shape; its 539-test Base gate is
ready, while the live provider outcome remains honestly pending. See the
[v0.13.0 phase report](v0.13.0-phase-report.md).

The twentieth increment executes the frozen FileLock #606 holdout with a live DeepSeek Implementer
and independent Reviewer. It hardens terminal submission, distinguishes pytest assertion failures
from collection/import errors in Base probes, and adds an explicit compatibility-default review
check. The candidate passed 563 public tests and the Reviewer accepted it, but the sealed evaluator
rejected its breaking default behavior. That false accept is preserved as unresolved-task evidence
rather than converted into a success claim. See the
[v0.13.1 phase report](v0.13.1-phase-report.md) and
[FileLock evidence](../evidence/filelock-606-holdout/README.md).

The twenty-first increment converts that false accept into a general, deterministic review input
without tuning on the contaminated case again. Independent Review now receives a read-only,
size-bounded Base/Candidate AST comparison for changed public Python callables, default-bearing
signatures, protocol methods, class bases, and exports. Signals are archived but do not themselves
block a Patch. Implementer and Reviewer read budgets are now independently configured, defaulting
to 24 and 12 calls respectively. See the [v0.13.2 phase report](v0.13.2-phase-report.md) and
[ADR 0027](adr/0027-compatibility-signals-inform-but-do-not-decide.md).

The twenty-second increment freezes Locust #3207 as a fresh compatibility holdout and makes its
setup reproducible. Project discovery now recognizes one bounded nested Python test root and avoids
traceback-call intent pollution. A reviewed external `--policy-file` can adapt an immutable upstream
checkout, is hash-frozen, and cannot override repository-owned policy. The new model-free `gate`
entry records actual Python runtime identity; the same public catch-response gate passed 12 tests
under CPython 3.12 and 3.13. A network-free evaluator was SHA-256 committed before the live run and
distinguishes the failing 3.13 Base, but its contents and expected repair remain Agent-invisible.
Live resolution remains pending. See the [v0.13.3 phase report](v0.13.3-phase-report.md),
[Locust evidence](../evidence/locust-3207-holdout/README.md),
[ADR 0028](adr/0028-operator-policy-is-explicit-frozen-and-non-overriding.md), and
[ADR 0029](adr/0029-verification-artifacts-record-runtime-identity.md).

The twenty-third increment improves the product-facing terminal delivery without changing Agent
authority. Guided `start` now renders each attempt's deterministic verification and runtime, a
bounded colorized Patch preview, Artifact/Manifest locations, and a copyable Git apply-check
command. Untrusted repository/model control characters are neutralized before terminal rendering;
the full Patch remains the hash-bound file rather than terminal text.

The twenty-fourth increment executes the frozen Locust #3207 holdout on a low-privilege Linux host.
The Implementer candidate passed 12 public tests but failed the precommitted CPython 3.13 evaluator;
Independent Review accepted it with zero findings at both 12- and 24-call budgets. The false accept
is preserved as unresolved evidence. Post-reveal hardening adds explicit state producer/ownership
reasoning to both Agents and a bounded AST signal for required string-key lookups changed into
fallbacks. Because the case is now contaminated, this validates the regression signal only; the
next accuracy claim requires a fresh holdout. See the [v0.13.5 phase report](v0.13.5-phase-report.md),
[Locust evidence](../evidence/locust-3207-holdout/README.md), and
[ADR 0030](adr/0030-required-state-fallbacks-trigger-root-cause-review.md).

## Priority demos

1. **Demo A:** Issue -> repository localization -> minimal code/test edits -> verification -> one
   repair -> Review-ready Patch.
2. **Demo B:** defective candidate PR -> source-linked Reviewer finding -> controlled repair ->
   final deterministic gate.
