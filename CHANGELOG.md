# Changelog

All notable changes are recorded here. PRGuard is pre-1.0; contracts can still evolve between minor
versions.

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
