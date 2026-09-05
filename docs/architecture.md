# Architecture

## Scope and invariant

PRGuard's product core accepts a real repository, immutable base commit, and Issue, then asks an
Implementer to understand the repository, form a plan, edit source and necessary tests, and
produce a minimal patch. The Phase 1 foundation starts one step later and accepts an already
produced candidate patch plus allowed verification argv:

```text
Task -> preflight -> detached worktree -> patch check/apply -> policy check
     -> bounded verification -> final diff/policy check -> JSON + Markdown + manifest
```

No probabilistic component owns Git state, command execution, timeouts, policy, or the verdict.
The same inputs can be replayed by checking out the same commit and applying the archived patch.

## Target product flows

### `fix` (primary)

The CLI accepts either a validated local JSON contract or a canonical public GitHub Issue URL. The
URL path runs the same onboarding stage and retains its intermediate Task and Manifest before
continuing, so one-command UX does not remove the replay boundary.

```text
Issue + repository + base commit
  -> Implementer: text/AST navigation -> internal plan -> structured edits
  -> isolated edit worktree -> Git-authored Patch
  -> deterministic verification
  -> at most one evidence-guided repair
  -> final gate -> Review-ready Patch + artifacts
```

With `fix --review`, an accepted Fix Patch reaches a deterministic routing boundary before any
Reviewer provider is constructed or called. `always` is the default, `shadow` records a selective
recommendation while still reviewing, and explicit `selective` mode may deliver a completely
analyzed low-risk Fix without a Reviewer call. Routed Patches otherwise continue into a fresh
independent Reviewer context, optional one-time controlled repair, and a top-level final delivery
Manifest. A failed Fix never enters routing or spends Reviewer tokens.

### `review` (quality module)

The CLI can consume a standalone ReviewTask, or reuse a frozen FixTask plus `--candidate-patch`.
The latter derives the review contract locally and, for controlled repair, inherits the original
writable paths and Patch limits instead of asking the user to duplicate them.

```text
Issue + repository + base commit + candidate patch
  -> deterministic verification
  -> read-only Independent Reviewer
  -> findings/verdict -> optional one controlled repair
  -> final gate -> review report + patch + artifacts
```

The Reviewer does not precede a usable Implementer. A separate Planner is deferred unless real
failure evidence shows that an internal planning step is inadequate. Verification always remains
a deterministic tool, never a Test Runner Agent.

## Components

- **Schemas** are Pydantic v2 contracts with `extra="forbid"` and a schema version.
- **GitHub onboarding** validates one canonical public Issue URL, fetches only Issue title/body plus
  repository/commit metadata, rejects Pull Requests and private repositories, freezes a full commit
  SHA, and materializes it without running hooks. A same-origin local clone may be an object cache.
- **Local onboarding** accepts a clean Git toplevel plus bounded natural-language Issue text,
  resolves `HEAD` or a requested revision, and materializes a separate detached checkout with hooks
  and user/system Git configuration disabled. Inline text and regular UTF-8 Issue files both become
  the same SHA-256-bound FixTask; the workspace must remain outside the source repository.
- **Project profile discovery** accepts a strict reviewed `.prguard.toml` or conservatively detects
  pytest and Python source/test write scopes. Tool configuration alone is not repository policy:
  Ruff is enabled only by reviewed configuration and only as `check --no-fix`. Discovery never
  installs dependencies or invents service setup, and repository configuration cannot weaken the
  built-in command grammar or fixed protected paths. A read-only inspection checkpoint exposes the
  resolved Base, discovery signals, exact argv, scopes, warnings, and a deterministic TOML
  candidate; it returns `needs_config` rather than inventing a missing test command.
- **Repository tools** expose bounded file listing, case-insensitive text search, line-range reads,
  and a lazy Python AST index for symbols, imports/re-exports, lexical references, incoming/outgoing
  calls, one-to-three-hop call-graph neighborhoods, and related/reachable-test ranking. Graph roots
  must resolve exactly or by one unique suffix; ambiguous names return candidates and no edges.
  Every edge retains its lexical expression, source anchor, and resolution method. Credential-like
  paths, traversal, escaping symlinks, binary files, file/index caps, graph depth/edge caps, and
  context-budget overruns fail closed. The graph is explicitly a static approximation; runtime
  dispatch and reflection are unresolved. `inspect-symbol` exposes the same query for deterministic
  debugging in a short-lived detached Base-Commit worktree; it does not call a provider or execute
  repository code.
- **Implementer provider** is a replaceable semantic component. DeepSeek uses bounded Chat
  Completions function calls, OpenAI uses direct Responses function calls, and the offline adapter
  makes workflow tests reproducible. None receives a shell or direct write primitive. Read-tool
  calls have an explicit remaining budget and one terminal-only submission slot. A failed provider
  call retains non-secret partial tool, response, and Token evidence without storing hidden model
  reasoning.
- **Structured edit engine** accepts exact single-match `replace_text`, hash-guarded inclusive line
  ranges, hash-guarded unambiguous Python definitions, and bounded `create_file` operations. The
  hashes bind an edit to bytes returned by the read tool, so repeated text can be changed without
  silently selecting the wrong occurrence. It validates paths and payloads, applies them in a
  separate detached worktree, syntax-checks Python symbol replacements, and asks Git to generate
  the Base-Commit-relative Patch. Raw unified diffs remain a compatibility fallback.
- **Patch policy** validates every generated or fallback diff against writable/protected globs,
  patch bytes, changed-file count, and consistent file headers.
- **Fix runner** creates a read-only discovery worktree, requests a proposal, materializes
  structured edits in a second short-lived worktree, delegates execution to a fresh Verification
  Harness worktree, and permits at most one repair using structured failure evidence. Before any
  model call it runs declared pytest targets in `--collect-only` mode and executes declared
  non-pytest gates against the Base Commit: failing pytest assertions remain valid Fix inputs,
  while missing imports/plugins/generated modules or unhealthy quality gates fail as environment
  readiness instead of consuming a repair round.
- **Changed-test gate** recognizes added or modified conventionally named Python test modules from
  Git's changed-file set. If the Task declares pytest, uncovered changed tests receive one
  Harness-authored `pytest -q` argv; if no pytest capability exists, execution is policy-blocked.
  Candidate workflows additionally copy executable changed tests—not candidate source—onto a fresh
  Base worktree and require that probe to fail before final verification. Python AST equivalence
  skips comment/format-only changes. The derived argv and Base-probe result are reported and
  replayed, and still pass the fixed no-shell grammar.
- **Guided terminal entry** gathers ordinary Issue text, resolves and previews the immutable Base,
  shows discovered commands and edit/protected scopes, requires a human host/container decision,
  and invokes the same local preparation plus FixRunner path as the automation-oriented CLI. It is
  a presentation layer, not a second orchestration implementation.
- **Reviewer router** runs only after an accepted Fix and before Independent Review. It binds the
  resolved Base Commit and final Patch hash to the verified Fix and Verification Manifests, then
  derives versioned risk factors from Patch scope, prior repair, test/gate and sensitive-path
  changes, declared pytest scope, bounded Python symbol fingerprints, static caller impact, and
  reachable/related public tests. `always` routes every Fix; `shadow` artifacts the selective
  recommendation but still routes every Fix; only explicit `selective` mode can make `skip`
  effective. Artifact mismatch is a hard integrity failure, while incomplete or unsupported static
  analysis receives a blocking risk factor and routes to review. The score is an auditable policy
  value, not a defect probability. `review-routing-v2` additionally routes a changed factory that
  directly returns a nested class with instance state written across methods; this bounded signal
  addresses one observed lifecycle regression but is not a general state-machine detector.
  `review-routing-v3` corrects full-suite accounting: when the verified argv represents an
  unfiltered pytest run with no explicit target, every bounded reachable/related unchanged test is
  recorded as covered instead of generating a contradictory uncovered-test risk factor.
  `review-routing-v4` aggregates all successful pytest commands: once an unfiltered full-suite run
  is observed, an automatically derived changed-test replay cannot downgrade the overall scope to
  targeted. This is evidence accounting only; a green full suite is not treated as a correctness
  proof.
- **Review runner** proves Base collection/non-pytest readiness, verifies the candidate, creates
  separate unchanged-Base and exact-Candidate worktrees, and derives bounded Python AST
  compatibility signals for changed non-test modules. It gives an independently scoped Reviewer
  only the Issue, candidate diff, deterministic evidence/signals, and bounded read tools, then
  computes the verdict deterministically. Compatibility signals direct attention but never block
  by themselves. P0-P2 findings block; P3 is non-blocking; failed verification blocks even when
  the Reviewer misses a finding. A model result returned after the logical stage deadline is
  retained as evidence but cannot produce an accepting verdict.
- **Review-repair runner** preserves the initial review and shows the Implementer only the original
  candidate plus structured public findings and verification evidence. Exact edits may be applied
  to an isolated patched worktree and folded by Git into one complete replacement Patch against the
  same Base Commit; a raw fallback must already be a complete replacement. A fresh Harness owns the
  final gate.
- **Issue-to-PR runner** assigns separate bounded Implementer and Reviewer read budgets inside one
  outer deadline, routes only an
  accepted Fix, constructs the Reviewer only when the effective route is `review`, and constructs
  the repair Implementer only after a `request_changes` verdict. A selective `skip` copies the
  byte-identical verified Fix Patch to the delivery root;
  otherwise the runner composes it into review-repair. The top-level report records the routing
  result and recursively hashes the decision, delivered Patch, and nested workflow artifacts.
- **Repository manager** resolves the exact commit, requires a clean source repository, and owns
  detached worktree lifecycle.
- **Patch manager** uses `git apply --check` then `git apply`; it never evaluates patch text.
- **Command policy** accepts argv arrays only and supports pytest plus non-mutating
  `ruff check --no-fix`, directly or through `python -m`. User-declared commands require exact Task
  allowlisting. The sole derived form is a Harness-authored pytest command whose paths come from
  Git's bounded changed-test set; it is grammar-validated and retained in command/trace artifacts.
- **Executor** uses `shell=False`, process groups, sanitized environment, output files, and two
  deadlines (command and task). Its default host backend keeps the deterministic Python import path
  limited to the detached worktree's `src/` directory and repository root. Its explicit container
  backend uses a digest-pinned image, no network, a non-root user, read-only root/worktree mounts,
  dropped capabilities, tmpfs HOME/TMP, and CPU/memory/PID limits. Both retain the original
  allowlisted argv in the report.
- **Deadline enforcement** checks remaining time before provider calls and again after each provider
  returns. The latter prevents a late SDK response from being accepted. Network-client cancellation
  is best-effort, so a stalled SDK may still delay process return even though the run ultimately
  fails closed.
- **Policy audit** compares Git-visible changes with protected globs, rejects any verification
  command that changes the Candidate diff, and compares the run directory outside managed
  worktree/runtime paths before and after verification.
- **Artifact store** emits canonical JSON, Markdown, patch/diff evidence, individual hashes, and
  a self-authenticating manifest payload hash.

## Agent boundary

Implementer context contains `FixTask` fields and only source bytes or static anchors explicitly
returned by bounded tools. It submits declarative edits or a fallback Patch; Harness-owned code is
the only component that writes edit/verification worktrees. On repair it receives its prior Patch,
terminal outcome, policy findings, and failed command output—not evaluator labels or hidden tests.

Provider credentials are process-environment inputs, never task or CLI fields. Live envelopes
retain provider/model, response ID, token counts, endpoint class, reasoning effort, and available
backend fingerprint, while excluding credentials and private reasoning content.

Reviewer context contains issue, final diff, necessary source, and summarized verification
evidence, but not Implementer reasoning. Reviewer is read-only. The routing score, factors, and
recommended route also remain Harness-owned artifact metadata and are not passed into the Reviewer
context, preventing a heuristic pre-assessment from anchoring the independent semantic review. Gold
patches, hidden tests, and defect labels belong to an evaluator-only record that is deliberately
absent from the `Task` schema.

Post-run evaluator records use a separate `prguard.evaluation` package, not the Agent-facing schema
namespace. The Shadow scorecard verifies candidate Patch, route, and optional Reviewer evidence
hashes and requires identical Base Commit/Patch bindings before joining observations. This makes
evaluation replayable without making labels or Reviewer dispositions available during generation
or review.

When controlled repair is enabled, the Implementer reads the patched candidate in a separate
worktree. Structured edits are folded into a complete Base-Commit-relative replacement diff; a raw
fallback must already have that form. Feedback contains only the original candidate, validated
findings, review summary, Harness outcome, policy findings, and failed public command output. The
outer manifest recursively hashes the initial review, proposal, final verification, and delivered
patch.

## Terminal outcomes

The `fix` workflow reports `accepted`, `failed_verification`, `agent_failed`, `policy_blocked`, or
`preflight_failed`. Every attempt retains its proposal/tool record and nested Harness report, or a
structured partial-provider record when no proposal was returned.

The integrated `review --repair` workflow reports `accepted_without_repair`,
`accepted_after_repair`, `repair_failed`, `review_failed`, `policy_blocked`, or
`preflight_failed`. Only the first two produce an accepting final verdict.

The composed `fix --review` workflow reports `accepted`, `fix_failed`, `review_failed`,
`policy_blocked`, or `preflight_failed`. In default `always` and non-skipping `shadow` flows,
`accepted` requires both nested workflows to accept. In explicit `selective` mode it may instead
mean that the Fix passed its deterministic gate and a complete low-risk routing decision selected
`skip`; `review_routing.effective_route` distinguishes that case from an executed review.

The underlying Harness reports:

- `passed`: patch applied, commands passed, no policy violations;
- `failed_verification`: at least one verification command failed;
- `patch_failed`: candidate patch could not be checked/applied;
- `timed_out`: command or task deadline expired;
- `policy_blocked`: protected or out-of-worktree writes were detected;
- `preflight_failed`: repository/base/task validation failed.
