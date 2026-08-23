# Changelog

All notable changes are recorded here. PRGuard is pre-1.0; contracts can still evolve between minor
versions.

## 0.8.0 — 2026-08-23

### Added

- `prepare-github` for public GitHub Issue title/body, repository metadata, exact Base Commit,
  same-origin cached checkout, and frozen FixTask preparation;
- direct `prguard fix https://github.com/.../issues/...` composition that retains preparation
  artifacts and continues into the normal verified Fix workflow;
- strict `.prguard.toml` support plus conservative pytest/Ruff and source/test-scope discovery;
- Issue-symbol-to-public-test targeting and a recorded runtime-only adapter for missing Hatch VCS
  version files;
- bounded Python AST symbol, import/re-export, reference, incoming/outgoing call, and related-test
  navigation for Implementer and Independent Reviewer contexts;
- exact `replace_text` and `create_file` proposals, applied in an isolated worktree and converted
  by Git into the final unified diff;
- a preparation report and standard SHA-256 RunManifest accepted by `verify-manifest`.

### Evidence

- a frozen Humanize #366 run exposed a missing generated-version module before the adapter existed;
- after readiness and runtime adaptation, a fresh live run was accepted in one attempt with two
  structured edits, 78 targeted tests, and Ruff;
- the accepted Patch then passed a separate wider gate with 702 passed and 74 optional benchmark
  skips, and both recursive Manifests verified.

### Security and correctness

- public onboarding rejects non-canonical URLs, redirects, Pull Requests, private repositories,
  oversized API responses, unresolvable commits, and implicit execution trust;
- repository-owned configuration cannot expand the fixed pytest/Ruff argv grammar or remove fixed
  protected paths;
- AST indexing inherits file, symlink, credential-name, index-size, and shared context-byte limits,
  and labels call relationships as static approximations;
- structured replacements require one exact match and remain subject to writable/protected path,
  changed-file, file-byte, Patch-byte, and final Harness gates;
- declared pytest targets must collect on the frozen Base Commit before any provider call, so
  missing imports/plugins/generated modules do not consume a repair attempt;
- runtime scaffolds are automatically protected, hash-checked after execution, and excluded from
  changed files and the delivered Patch;
- Fix tasks now require at least one declared and allowlisted verification command.

## 0.7.0 — 2026-08-20

### Added

- opt-in digest-pinned Docker execution in Task, Fix, Review, and Issue-to-PR contracts;
- no-network, non-root, read-only root/worktree, capability, tmpfs, CPU, memory, and PID controls;
- structured backend/image/infrastructure fields in each VerificationResult;
- hash-locked online and offline reference verification-image builds;
- an opt-in runtime probe for UID, privilege, capability, mount, network, and cgroup controls.

### Security and correctness

- container commands remain exact pytest/Ruff argv with `shell=False` and image pulls disabled;
- timed-out Docker runs are forcibly removed through a Harness-owned cidfile;
- an internal Python-start marker separates runtime launch failures from test exit codes even when
  Docker returns an ambiguous status;
- host-mode behavior remains the default and its non-sandbox boundary remains explicit.

## 0.6.0 — 2026-08-20

### Added

- `fix --progress` stage updates and 15-second heartbeats on stderr without changing JSON stdout;
- reproducible public Humanize #366 Demo A materializer with an exact evaluation Base Commit;
- a fresh live repair run covering malformed-Patch rejection, one replacement, pytest, and Ruff.

### Security and correctness

- progress observers cannot change the workflow result;
- the public Demo contains only an Issue, public reproduction, declared policy, and commands—no
  hidden test, Gold Patch, defect label, or issue-discussion solution.

## 0.5.1 — 2026-08-19

### Added

- composed `fix --review` Issue-to-PR workflow with one total deadline and recursive manifest;
- independent read-only review, deterministic verdict policy, and one controlled replacement repair;
- DeepSeek Chat Completions and OpenAI Responses Implementer adapters;
- bounded repository discovery tools and complete unified-diff proposal policy;
- real-repository case evidence for Humanize, PrettyTable, and Inflect;
- source-layout import support in deterministic verification;
- key-free offline repair demo and GitHub Actions quality gate.

### Security and correctness

- late Implementer and Reviewer results fail closed after their logical stage deadline;
- command execution remains argv-allowlisted with `shell=False`;
- recursive artifact manifests authenticate nested workflow evidence;
- credentials remain environment-only and are excluded from task/provider contracts.

### Known limitations

- worktrees and process controls are not a hostile-code sandbox;
- GitHub API integration and container-backed execution are not implemented;
- three public repository cases do not establish general task-resolution or review accuracy;
- historical raw artifacts can contain non-secret execution-machine paths and should not be
  republished without sanitization.
