# PRGuard 0.3.0 server validation report

Date: 2026-08-19

## Outcome

PRGuard 0.3.0 was deployed and validated on a user-provided Ubuntu x86_64 server. Root was used only
for the bootstrap and privilege drop. All project installation, tests, Git worktrees, model calls,
and Artifacts ran as the dedicated unprivileged `prguard` account (UID/GID 997) under
`/srv/prguard`.

Both product entries passed a live server gate:

- `fix`: DeepSeek generated a minimal slug Patch; deterministic verification reported 2 passed and
  accepted the Patch.
- `review`: deterministic verification exposed a PASS_TO_PASS normalization regression; the
  independent Reviewer anchored one P2 Finding at `service.py:4` and requested changes.

## Frozen environment

- OS: Ubuntu Linux, kernel `5.15.0-112-generic`, x86_64.
- Python: 3.12.4 in a dedicated 113MB prefix.
- Git: 2.34.1.
- uv: 0.9.22.
- PRGuard: 0.3.0 installed from a prebuilt Wheel.
- Project release: `/srv/prguard/releases/0.3.0`.
- Artifact root: `/srv/prguard/artifacts`, mode 0700.
- Full server checks: Ruff passed; Pytest 72 passed in 21.60 seconds.

The server's system Python was 3.10 and its Python 3.12/uv installation lived under inaccessible
root-owned Anaconda paths. A minimal Python 3.12.4 prefix was created from the server's existing
offline Conda package cache. No permission on `/root` was relaxed.

## Supply-chain checks

- Source bundle SHA-256 matched before extraction:
  `e08c8fd7be3ea4d664d9d1bda81797d948b7dceb29dd25ae833e00c1f096b023`.
- Linux CPython 3.12 Wheelhouse archive matched:
  `656911e545df0d208ed55279360816b2f8358f69b4e25a5d9a9e58df381f9a4b`.
- PRGuard Wheel matched:
  `12e64376a67fa4d59522fd74edeb53ce64f5fa49e16d8248e69f326274facc4c`.
- A separately hashed `colorama==0.4.6` Wheel was added because uv required the conditional pytest
  dependency to exist during offline resolution even on Linux.
- All 22 locked runtime/dev dependencies were installed with `--offline --no-index`; the project
  was then installed from the verified Wheel.

The initial macOS source archive carried 146 AppleDouble `._*` metadata files. Only those generated
metadata files were deleted from the release after enumeration; the original verified archive was
retained for recovery. Future bundles should suppress macOS extended attributes at creation.

## Server live metrics

| Entry | Outcome | Input | Output | Cached | Duration |
|---|---|---:|---:|---:|---:|
| `fix` public slug fixture | accepted; 2 passed | 3,822 | 1,472 | 3,328 | 28.38s |
| `review` known regression | 1 P2; request_changes | 5,621 | 817 | 4,352 | 19.26s |
| **Total** | **2/2 expected** | **9,443** | **2,289** | **7,680** | **47.63s** |

An offline scripted repair case also passed: attempt 0 produced 1 failed / 2 passed; attempt 1
produced 3 passed; final outcome accepted in 1.26 seconds.

## Credential and workspace audit

The DeepSeek Key was sent over SSH standard input to a one-shot root launcher. The launcher read it
into memory, dropped supplementary groups and UID/GID to `prguard`, and used `execve` with a minimal
environment. The Key was never supplied in command arguments, written to disk, added to a task, or
placed in a Shell history.

- Exact configured Key absent from all server live Artifact bytes.
- Generic API-key and Authorization patterns absent.
- Both live Manifests verified on the server.
- Both Artifact directories were owned entirely by `prguard:prguard`.
- Both source fixture repositories remained clean.
- After copying Artifacts back to the local workspace, both Manifests verified again.

## Retrieved evidence

- Fix run: `outputs/phase-3-server-validation-60a5ad2f`
- Review run: `outputs/phase-3-server-review-validation-abf7afb3`

## Residual risks

The server still has root SSH access because that is how it was provided; PRGuard does not require
root after bootstrap. The host filesystem was 84% used at inspection time. Most importantly, this
deployment uses the existing Git worktree/process boundary, not a hostile-code container sandbox.
Only trusted fixtures were executed. Network denial, read-only mounts, CPU/memory/PID quotas, and a
container runtime remain Phase 5 work before running hostile repositories.
