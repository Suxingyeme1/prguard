# Threat model

## Assets and trust zones

Assets are the developer checkout, credentials, host filesystem, benchmark secrets, evaluation
labels, and artifact integrity. Task text, patch text, repository contents, and tests are treated
as attacker-controlled. The source checkout is trusted only as a Git object source; execution
occurs in a detached worktree.

## Phase 1/2 controls

| Threat | Control | Residual risk |
|---|---|---|
| Shell injection | argv schemas, tool grammar, `shell=False` | allowed test code is still code |
| Wrong revision | `rev-parse <base>^{commit}` and exact recorded SHA | compromised Git binary/host |
| Source checkout mutation | clean preflight plus before/after snapshot | filesystem races |
| Protected-file tampering | Git changed/untracked paths matched against protected globs | ignored files need explicit audit |
| Path traversal in command args | absolute paths and `..` segments rejected | tools may discover paths internally |
| Credential inheritance | minimal environment, private HOME/TMPDIR | host APIs/files remain reachable |
| Hanging/forking process | new process group, deadline, group termination after timeout or parent exit | host process-group escape/races; no hard CPU/memory/pid quota |
| Hostile verification code | optional digest-pinned container with no network, non-root UID, read-only mounts, dropped capabilities, and hard resource limits | host-mode tasks remain unsandboxed; kernel/daemon/image stay trusted |
| Artifact tampering | SHA-256 per file and manifest payload hash | no signing/remote attestation |
| Secret benchmark leakage | public Task excludes gold/labels/hidden-test fields | authoring discipline still required |
| Repository secret disclosure | denied credential names/suffixes, symlink containment, byte-bounded reads | secrets in ordinary source files remain in scope |
| Malicious Issue/prompt injection | fixed instructions plus bounded text/AST tools and declarative edits | model can still propose a malicious semantic change |
| AST/call-graph overclaim | results label bounded static analysis and each resolution type; graph traversal is capped at three hops and ambiguous roots return no edges | dynamic dispatch, reflection, and generated code remain unresolved |
| Agent adds a test outside the selected pytest target | Harness derives an argv for changed Python test modules; absent pytest capability blocks | unconventional/non-Python test layouts need reviewed project configuration |
| Overbroad model edit | exact replacements are checked and Git-authored diffs are policy-gated in isolated worktrees | configured writable globs may be too broad |
| Ambiguous text replacement | `old_text` must occur exactly once; create targets must not exist | a unique match can still be semantically wrong |
| Patch parser smuggling | standard file headers must agree; rename/copy/binary patches rejected | Git parser differentials remain a review target |
| Unbounded repair loop | at most one replacement patch | one repair can still consume substantial tokens |
| Provider data exposure | only tool-returned repository bytes are sent | external provider receives those selected bytes |
| Provider credential disclosure | environment-only keys, no key CLI/task fields, error redaction | host process inspection and misconfigured logging |
| Endpoint credential smuggling | provider URLs reject userinfo/query/fragment and require HTTPS except loopback | a permitted endpoint still receives selected source |
| Reviewer anchoring on Implementer | fresh provider context excludes Implementer plan/reasoning | shared model family may have correlated blind spots |
| Reviewer anchoring on routing heuristics | routing score, factors, and recommendation remain Harness artifacts and are excluded from Reviewer context | Reviewer still sees the same Patch and verification evidence that informed deterministic factors |
| Reviewer false authority | findings require evidence; Harness and severity policy own verdict | plausible but false evidence still needs human review |
| Finding-to-repair prompt injection | only validated structured fields are serialized; Implementer retains fixed instructions and bounded tools | malicious repository text can still influence both models |
| Incremental-patch ambiguity | repair must be a complete diff against the immutable Base Commit and is applied in a fresh Harness worktree | semantic omission can still pass incomplete public tests |
| Reviewer-triggered token loop | exactly one repair proposal and one final gate | one live repair can still be expensive |
| Composed workflow budget exhaustion | one outer deadline plus smaller Fix and Reviewer budgets | up to three Implementer proposals remain possible across both stages |
| GitHub URL/metadata spoofing | canonical HTTPS Issue URLs, fixed API host, redirect denial, PR/private rejection, full commit SHA | GitHub/API availability and account compromise |
| Repository config command injection | `.prguard.toml` commands pass the built-in pytest/Ruff argv grammar | approved pytest/Ruff code still executes repository code |
| Environment failure misdiagnosed as Patch failure | Base pytest targets must collect before any model call | collection can pass while later runtime dependencies still fail |
| Unhealthy quality gate blamed on Candidate | declared non-pytest gates must pass at Base Commit before any model call | pytest assertion baselines still need evaluator interpretation |
| Linter/test mutates Candidate during verification | Ruff requires `check --no-fix`; before/after Candidate diffs must match | hostile code can still write outside a host worktree before audit detects it |
| Runtime scaffold leaking into delivery | declared path is protected, hash-checked, and excluded from Git final diff | the narrow scaffold may not emulate every build backend API |
| Provider failure hides prior work/cost | partial response metadata, tool calls, and Token usage are artifacted and hashed | provider accounting can be absent or inaccurate |
| Selective routing bypasses required review | `always` is the default; `shadow` always reviews; only explicit `selective` can make `skip` effective, and only after an accepted Fix | a poorly calibrated explicit selective policy can still skip a semantically risky Patch |
| Missing static evidence is mistaken for low risk | replay, deadline, AST/index, unsupported-language, ambiguity, and cleanup incompleteness force the route to review | bounded analysis can appear complete while dynamic dispatch or repository conventions hide impact |
| Routing inputs are substituted after verification | Base Commit, Patch SHA-256, Fix Manifest, Verification Manifest, and archived/in-memory report equality are bound before routing; the top Manifest hashes the decision and delivered Patch | SHA-256 artifacts are not signed or remotely attested |
| Implementer manipulates its own risk score | routing uses Git-visible Patch facts, frozen public policy, verified command evidence, and Harness-owned static analysis rather than model summaries or self-reported test coverage | an adversarial semantic change can deliberately remain small and use ordinary-looking paths |
| Evaluator labels leak into Agent context | evaluator schemas live outside `prguard.schemas`; Fix/Review tasks reject extra fields; labels are attached only after execution | a human can still accidentally paste evaluator knowledge into Issue text or source fixtures |
| Scorecard joins evidence from different Patches | evaluator inputs hash-bind candidate Patch, route, and Reviewer manifest, then require identical Base Commit and candidate Patch SHA-256 | SHA-256 records are not signed and evaluator dispositions still require human judgment |
| Existing test pass is treated as permanent clean evidence | evaluator labels may be revised only by a hash-bound post-run check replayed on Base and Candidate; raw prior gate evidence is retained | newly proposed checks still require independent human validation and can overfit one case |

## Explicit non-guarantees

Git worktrees are isolation from accidental source-checkout edits, not a sandbox. Host-mode
verification cannot reliably prevent arbitrary native code from reading the network, host
credentials, or writing an arbitrary absolute path; its audits are detection rather than
containment. The optional container backend adds network denial, read-only mounts, non-root UID,
dropped capabilities, and resource quotas. It still trusts the selected image, Docker daemon,
container runtime, and host kernel; high-risk public code should run on a dedicated disposable VM
under a rootless runtime.

Symlinks in the resulting change set are policy-blocked when they resolve outside the worktree.
Merge, push, release, and production deployment are outside this system and require humans.

Live adapters are optional and require an explicit API credential. Offline scripted fixtures prove
orchestration deterministically but do not claim live-model task success. Live provider runs must
be reported separately with provider, model, token, latency, and frozen artifacts. DeepSeek uses
the stable Chat Completions endpoint and locally validates every tool argument and submitted patch;
it does not depend on beta strict-function enforcement.

The Reviewer routing score is a versioned prioritization heuristic, not a probability of correctness
or a substitute for the deterministic gate. `shadow` mode is the safe way to measure its
recommendations against real Reviewer outcomes. Explicit `selective` mode accepts the residual risk
that a bounded, apparently complete static analysis may miss dynamic or repository-specific impact;
an accepted selective skip means the declared verification gate passed, not that the Patch was
proved defect-free.
