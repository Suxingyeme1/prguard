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
| Hanging/forking process | new process group, deadline, group termination | no hard CPU/memory/pid quota |
| Hostile verification code | optional digest-pinned container with no network, non-root UID, read-only mounts, dropped capabilities, and hard resource limits | host-mode tasks remain unsandboxed; kernel/daemon/image stay trusted |
| Artifact tampering | SHA-256 per file and manifest payload hash | no signing/remote attestation |
| Secret benchmark leakage | public Task excludes gold/labels/hidden-test fields | authoring discipline still required |
| Repository secret disclosure | denied credential names/suffixes, symlink containment, byte-bounded reads | secrets in ordinary source files remain in scope |
| Malicious Issue/prompt injection | fixed Implementer instructions and three read-only tools | model can still propose a malicious patch |
| Overbroad model edit | complete diff is policy-checked, then applied only in a fresh Harness worktree | configured writable globs may be too broad |
| Patch parser smuggling | standard file headers must agree; rename/copy/binary patches rejected | Git parser differentials remain a review target |
| Unbounded repair loop | at most one replacement patch | one repair can still consume substantial tokens |
| Provider data exposure | only tool-returned repository bytes are sent | external provider receives those selected bytes |
| Provider credential disclosure | environment-only keys, no key CLI/task fields, error redaction | host process inspection and misconfigured logging |
| Endpoint credential smuggling | provider URLs reject userinfo/query/fragment and require HTTPS except loopback | a permitted endpoint still receives selected source |
| Reviewer anchoring on Implementer | fresh provider context excludes Implementer plan/reasoning | shared model family may have correlated blind spots |
| Reviewer false authority | findings require evidence; Harness and severity policy own verdict | plausible but false evidence still needs human review |
| Finding-to-repair prompt injection | only validated structured fields are serialized; Implementer retains fixed instructions and bounded tools | malicious repository text can still influence both models |
| Incremental-patch ambiguity | repair must be a complete diff against the immutable Base Commit and is applied in a fresh Harness worktree | semantic omission can still pass incomplete public tests |
| Reviewer-triggered token loop | exactly one repair proposal and one final gate | one live repair can still be expensive |
| Composed workflow budget exhaustion | one outer deadline plus smaller Fix and Reviewer budgets | up to three Implementer proposals remain possible across both stages |

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
