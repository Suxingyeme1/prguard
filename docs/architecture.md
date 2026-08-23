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

With `fix --review`, an accepted Fix Patch continues into a fresh independent Reviewer context,
optional one-time controlled repair, and a top-level final delivery Manifest. A failed Fix never
spends Reviewer tokens.

### `review` (quality module)

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
- **Project profile discovery** accepts a strict reviewed `.prguard.toml` or conservatively detects
  pytest, Ruff, and Python source/test write scopes. It never installs dependencies or invents
  service setup, and repository configuration cannot weaken the built-in command grammar or fixed
  protected paths.
- **Repository tools** expose bounded file listing, case-insensitive text search, line-range reads,
  and a lazy Python AST index for symbols, imports/re-exports, lexical references, incoming/outgoing
  calls, and related-test ranking. Credential-like paths, traversal, escaping symlinks, binary
  files, file/index caps, and context-budget overruns fail closed. The call graph is explicitly a
  static approximation; runtime dispatch and reflection are unresolved.
- **Implementer provider** is a replaceable semantic component. DeepSeek uses bounded Chat
  Completions function calls, OpenAI uses direct Responses function calls, and the offline adapter
  makes workflow tests reproducible. None receives a shell or direct write primitive.
- **Structured edit engine** accepts exact single-match `replace_text` and bounded `create_file`
  operations. It validates paths and payloads, applies them in a separate detached worktree, and
  asks Git to generate the Base-Commit-relative Patch. Raw unified diffs remain a compatibility
  fallback.
- **Patch policy** validates every generated or fallback diff against writable/protected globs,
  patch bytes, changed-file count, and consistent file headers.
- **Fix runner** creates a read-only discovery worktree, requests a proposal, materializes
  structured edits in a second short-lived worktree, delegates execution to a fresh Verification
  Harness worktree, and permits at most one repair using structured failure evidence. Before any
  model call it runs declared pytest targets in `--collect-only` mode: failing assertions remain
  valid Fix inputs, while missing imports/plugins/generated modules fail as environment readiness
  instead of consuming a repair round.
- **Review runner** verifies the candidate first, creates a separate patched worktree, gives an
  independently scoped Reviewer only the Issue, candidate diff, deterministic evidence, and
  bounded read tools, then computes the verdict deterministically. P0-P2 findings block; P3 is
  non-blocking; failed verification blocks even when the Reviewer misses a finding. A model result
  returned after the logical stage deadline is retained as evidence but cannot produce an accepting
  verdict.
- **Review-repair runner** preserves the initial review and shows the Implementer only the original
  candidate plus structured public findings and verification evidence. Exact edits may be applied
  to an isolated patched worktree and folded by Git into one complete replacement Patch against the
  same Base Commit; a raw fallback must already be a complete replacement. A fresh Harness owns the
  final gate.
- **Issue-to-PR runner** assigns a bounded Fix-stage budget inside one outer deadline, then composes
  the accepted Fix artifact into review-repair. It copies only the final accepted Patch to the
  delivery root and recursively hashes both nested workflows.
- **Repository manager** resolves the exact commit, requires a clean source repository, and owns
  detached worktree lifecycle.
- **Patch manager** uses `git apply --check` then `git apply`; it never evaluates patch text.
- **Command policy** accepts argv arrays only and supports pytest/ruff directly or through
  `python -m`. The task allowlist must exactly contain every invoked argv.
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
- **Policy audit** compares Git-visible changes with protected globs and compares the run
  directory outside managed worktree/runtime paths before and after verification.
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

Reviewer context contains issue, final diff, necessary source, and summarized evidence, but not
Implementer reasoning. Reviewer is read-only. Gold patches, hidden tests, and defect labels belong
to an evaluator-only record that is deliberately absent from the `Task` schema.

When controlled repair is enabled, the Implementer reads the patched candidate in a separate
worktree. Structured edits are folded into a complete Base-Commit-relative replacement diff; a raw
fallback must already have that form. Feedback contains only the original candidate, validated
findings, review summary, Harness outcome, policy findings, and failed public command output. The
outer manifest recursively hashes the initial review, proposal, final verification, and delivered
patch.

## Terminal outcomes

The `fix` workflow reports `accepted`, `failed_verification`, `agent_failed`, `policy_blocked`, or
`preflight_failed`. Every attempt retains its proposal, tool-call record, and nested Harness report.

The integrated `review --repair` workflow reports `accepted_without_repair`,
`accepted_after_repair`, `repair_failed`, `review_failed`, `policy_blocked`, or
`preflight_failed`. Only the first two produce an accepting final verdict.

The composed `fix --review` workflow reports `accepted`, `fix_failed`, `review_failed`,
`policy_blocked`, or `preflight_failed`. `accepted` requires both nested workflows to accept.

The underlying Harness reports:

- `passed`: patch applied, commands passed, no policy violations;
- `failed_verification`: at least one verification command failed;
- `patch_failed`: candidate patch could not be checked/applied;
- `timed_out`: command or task deadline expired;
- `policy_blocked`: protected or out-of-worktree writes were detected;
- `preflight_failed`: repository/base/task validation failed.
