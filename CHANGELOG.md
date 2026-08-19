# Changelog

All notable changes are recorded here. PRGuard is pre-1.0; contracts can still evolve between minor
versions.

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
