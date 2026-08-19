# Phase 4A controlled review-repair report

Date: 2026-08-19
Version: `0.4.0`

## Outcome

PRGuard now supports the Demo B path:

```text
Issue + repository + Base Commit + defective candidate Patch
  -> deterministic candidate verification
  -> fresh-context, read-only Independent Reviewer
  -> structured blocking Finding
  -> one Implementer full replacement Patch against the same Base Commit
  -> fresh deterministic final gate
  -> review-ready Patch + recursive SHA-256 Manifest
```

This completes Phase 4A. It does not yet compose the primary `fix` entry directly into the Reviewer;
that is Phase 4B.

## Implementation

- Added `ReviewRepairTask`, `ReviewRepairReport`, `ReviewRepairOutcome`, and workflow version
  `review-repair-v1`.
- Added `ReviewRepairRunner` with one total deadline and a separately bounded Reviewer budget.
- Added `prguard review --repair` with independent Reviewer and Implementer provider selection.
- A clean initial review returns `accepted_without_repair` and never calls the Implementer.
- A blocking review gives the Implementer only the original candidate, structured findings,
  review summary, public Harness outcome/policy data, and failed command output.
- The repair must be one complete Base-Commit-relative unified diff. Writable/protected paths,
  Patch bytes, and changed-file count are checked before execution.
- Acceptance requires a new Harness worktree and a passing final gate.
- The original candidate, nested initial review, proposal, repair Patch, final verification, final
  Patch, JSON/Markdown report, and all nested manifests are recursively hashed.
- Added ADR 0009 and updated README, architecture, milestones, and threat model.

## Deterministic verification

- Local Ruff: passed.
- Local pytest: `80 passed in 17.46s` after non-editable `0.4.0` reinstall.
- Server Ruff: passed in the isolated `0.4.0/.venv`.
- Server pytest: `80 passed in 27.67s` as unprivileged user `prguard`.
- New cases cover successful repair, failed repair, no-op after clean review, policy-blocked repair,
  CLI composition, schema time budgeting, evaluator-secret exclusion, structured feedback, source
  checkout cleanliness, and recursive Manifest verification.

## DeepSeek live Demo B

Both runs used `deepseek-v4-pro` with thinking enabled and high reasoning effort.

### Local

- Outer run: `87ee7361-4c18-4e21-a3e6-6ff7dd7e0309`.
- Initial verdict: `request_changes`; one P2 regression at `service.py:4`.
- Final outcome: `accepted_after_repair`.
- Final gate: one FAIL_TO_PASS and one PASS_TO_PASS command, both passed.
- Duration: `33.725s`.
- Tokens: 12,683 input, 1,967 output, 9,600 cached.
- Final Patch SHA-256: `c60a72e530ae2a5ee46f4570521ec0c758a530de6a734864a9ac1b89f02cf46e`.
- Manifest copied to `outputs/phase-4-deepseek-live-review-repair` and verified after copying.

### Server `60.204.250.91`

- Outer run: `1f8f5020-3641-40e7-b073-20172bf33959`.
- Execution identity: unprivileged `prguard` (`uid=997`, `gid=997`).
- Initial verdict: `request_changes`; one P2 regression at `service.py:4`.
- Final outcome: `accepted_after_repair`.
- Final gate: one FAIL_TO_PASS and one PASS_TO_PASS command, both passed.
- Duration: `27.529s`.
- Tokens: 12,533 input, 1,635 output, 9,472 cached.
- Final Patch SHA-256: `c60a72e530ae2a5ee46f4570521ec0c758a530de6a734864a9ac1b89f02cf46e`.
- Manifest copied to `outputs/phase-4-server-deepseek-review-repair` and verified after copying.

The independently generated local and server replacement Patches are byte-identical. This is
reproducibility evidence for this small case, not a claim that model outputs are generally
deterministic.

## Deployment and security evidence

- Wheel SHA-256: `d4891e6850f99a6bd1dd9ccec55c0362bff65ca752150b16fc044ef14686667b`.
- Clean source archive SHA-256:
  `3f38b6d9493d6559759ac3ccc550bf3c8c059de872a65b9b55fe681b2fd7aaaf`.
- Frozen Demo B case archive SHA-256:
  `5566c7eca6a733533f5d396f12d5266e5f0838755211c6236ff249af0493b6c6`.
- Server verified all upload hashes before extraction and installed dependencies offline from the
  existing wheelhouse into a new `0.4.0/.venv`.
- The first source archive exposed macOS AppleDouble metadata during server lint. The archive was
  rebuilt with AppleDouble emission disabled; 208 exact `._*` deployment artifacts were removed
  only from the new `0.4.0` release/case directories. Source code and prior releases were untouched.
- The API key was read from macOS Keychain, sent to the server over SSH standard input, and injected
  only into the downgraded process environment. It was not placed in task JSON, CLI argv, files, or
  shell history.
- Exact-key persistence scans: zero matches locally and zero matches under the server release,
  case, runtime-home, and Artifact scopes.
- No lingering server process owned by `prguard`; source fixture repositories remained clean.

## Fact boundary and residual risks

- This is one seeded regression. It does not establish Review Finding precision/recall or broad
  Issue-to-Patch resolution.
- Reviewer and Implementer used the same model family, so independent context does not imply
  statistically independent errors.
- Git worktrees and uid separation are not a hostile-code sandbox. Server tests still had host
  network/filesystem access available to the `prguard` account.
- The server root filesystem was 84% used before this deployment, with about 160 GB available.
- No GitHub API, push, merge, FastAPI, Docker, multi-model routing, or Diagnostician was added.

## Next priority

Implement Phase 4B: compose a successful `fix` run into independent review and optional controlled
repair under one top-level result and Manifest. After that, validate on two or three manually
checked real-repository Issues before investing in broader A/B evaluation or a Diagnostician.
