# Changelog

All notable changes are recorded here. PRGuard is pre-1.0; contracts can still evolve between minor
versions.

## 0.9.0 — 2026-08-24

### Added

- a Harness-owned Reviewer router after an accepted Fix, with backwards-compatible `always`,
  measurement-only `shadow`, and explicit `selective` modes;
- versioned routing schemas for the recommendation/effective route, integer evidence factors,
  Patch statistics, pytest argv scope, changed Python symbols, bounded caller/test impact, analysis
  completeness, and Fix/Verification Manifest bindings;
- `fix --review --review-policy {always,shadow,selective}` and lazy Reviewer/repair provider
  construction, so a selective skip does not require credentials or spend provider tokens;
- a dedicated `review-routing.json`, Markdown routing section, and recursive top-level Manifest
  coverage of the decision and exact delivered Patch;
- hard review triggers for Implementer repair, candidate-controlled tests/gates, sensitive paths,
  dependency/build files, unsupported source, incomplete AST/replay evidence, uncovered reachable
  tests, broad Patches, and high bounded static fan-in;
- security and integration cases for every routing mode, narrow-gate regression detection,
  provider non-construction, hard-trigger boundaries, invalid AST, prompt/self-report
  non-interference, and routing Artifact tamper detection.

### Changed

- the Issue-to-PR workflow contract is now `issue-to-pr-v4`; old Task JSON remains valid and
  defaults to unconditional Independent Review;
- a selective skip is represented as top-level `accepted` with `effective_route=skip`, no fabricated
  Reviewer result, and a byte-identical copy of the verified Fix Patch;
- routing uses a 30-second logical deadline, cannot skip after it expires, executes no repository
  code, counts intent-to-add files, and fails closed to Review on analysis or replay uncertainty;
- manifest identity, in-memory/archived Fix equality, resolved Base Commit, and verified Patch hash
  are checked before any route can accept a skip;
- successful host commands now terminate residual descendants in their isolated process group, and
  top-level delivery rechecks its cross-Artifact Patch binding before and after Manifest creation.

### Evidence

- a frozen PrettyTable #474 source-only Patch passed 21 targeted and 338 wider tests; exact static
  impact found only the explicitly selected HTML test file and shadow policy recommended `skip`
  with score 0/5;
- a frozen Humanize #366 source-only Patch passed 76 targeted and 700 wider tests plus Ruff, but
  shadow policy conservatively recommended `review` with score 9/5 because an unchanged reachable
  i18n test was outside the targeted gate;
- the path-free two-case routing package, raw routing contracts, source Patches, wider-gate Manifest
  hashes, and public-file hashes are independently verifiable. This pair is not a false-skip-rate
  estimate and selective remains opt-in.

## 0.8.2 — 2026-08-23

### Added

- `trace_call_graph`, a read-only Python AST tool shared by Implementer and Independent Reviewer;
- `inspect-symbol`, a key-free CLI that runs the same query in a detached worktree at the Task's
  resolved Base Commit;
- bounded caller, callee, or bidirectional traversal with a fixed one-to-three-hop depth and a
  caller-to-callee edge cap;
- exact/unique/ambiguous root resolution, repository-definition anchors, external-node labels,
  per-edge resolution evidence, reachable-test anchors, and deterministic truncation metadata.

### Changed

- package re-export resolution now handles member access through `__init__.py` aliases, so calls
  such as `PublicClass.method()` map back to the defining module when static evidence permits;
- package runtime version metadata is synchronized with the project release version and covered by
  a contract test;
- provider instructions now describe the bounded graph as navigation evidence and still require
  source-line reads before editing or filing a review finding.

### Evidence

- at frozen PrettyTable commit `3c80d392d32f48b0ab1e368793ddb751dbe41807`, tracing
  `prettytable.prettytable.from_html` indexed 15 files and returned 7 nodes, 6 edges, and three
  reachable public tests without truncation or source execution;
- the result linked `from_html_one` and `tests/test_html.py` through re-export-aware edges. This is
  deterministic code-navigation evidence, not proof of a runtime-complete call graph or a new
  model task-resolution result.

## 0.8.1 — 2026-08-23

### Added

- non-secret partial provider-failure evidence with response metadata, accumulated Token usage,
  bounded tool-call records, dedicated JSON artifacts, Markdown summaries, and recursive hashes;
- deterministic read-budget feedback on every model tool result plus one terminal-only submission
  slot for Implementer and Reviewer providers;
- Base-Commit readiness execution for every declared non-pytest gate before model tokens are spent;
- policy detection for verification commands that modify the candidate worktree.

### Changed

- default bounded source-file analysis increased from 100 KB to 250 KB so realistic single-file
  Python modules remain searchable and AST-indexed without weakening the 1 MB schema maximum,
  20 MB total index cap, or shared context budget;
- Issue-aware test selection now passes the qualified symbol to related-test ranking rather than
  collapsing it to a source-module path;
- generic GitHub onboarding no longer treats Ruff configuration presence as repository policy;
  repositories opt in through reviewed `.prguard.toml`, and Ruff is limited to
  `check --no-fix`;
- the Hatch VCS runtime scaffold now uses the conservative PEP 440 version `0.0.0`.

### Evidence

- a fresh PrettyTable #474 live run at exact upstream commit
  `3c80d392d32f48b0ab1e368793ddb751dbe41807` was accepted in one attempt with 21 read calls plus
  one structured-edit submission;
- the targeted HTML gate passed 22 tests and a separate wider gate passed all 339 tests with no
  policy violations; both recursive Manifests verified;
- the Issue itself disclosed the root cause, so this is navigation/project-adaptation evidence,
  not a blind semantic benchmark.

## 0.8.0 — 2026-08-23

### Added

- `prepare-github` for public GitHub Issue title/body, repository metadata, exact Base Commit,
  same-origin cached checkout, and frozen FixTask preparation;
- direct `prguard fix https://github.com/.../issues/...` composition that retains preparation
  artifacts and continues into the normal verified Fix workflow;
- `prguard review FIX_TASK --candidate-patch PATCH` so review and optional repair reuse the frozen
  repository/Issue/policy contract instead of requiring duplicated ReviewTask JSON;
- strict `.prguard.toml` support plus conservative pytest/Ruff and source/test-scope discovery;
- Issue-symbol-to-public-test targeting and a recorded runtime-only adapter for missing Hatch VCS
  version files;
- bounded Python AST symbol, import/re-export, reference, incoming/outgoing call, and related-test
  navigation for Implementer and Independent Reviewer contexts;
- exact `replace_text` and `create_file` proposals, applied in an isolated worktree and converted
  by Git into the final unified diff;
- a preparation report and standard SHA-256 RunManifest accepted by `verify-manifest`.
- deterministic execution of added/modified Python test modules even when the original pytest
  target is narrower; test changes without a declared pytest capability are policy-blocked.

### Evidence

- a frozen Humanize #366 run exposed a missing generated-version module before the adapter existed;
- after readiness and runtime adaptation, a fresh live run was accepted in one attempt with two
  structured edits, 78 targeted tests, and Ruff;
- the accepted Patch then passed a separate wider gate with 702 passed and 74 optional benchmark
  skips, and both recursive Manifests verified.
- a narrow-gate regression case produced one manually confirmed independent finding, one exact
  controlled repair, and passing fail-to-pass/pass-to-pass checks; a clean Humanize Patch incurred
  no false block but 221.875 seconds of Reviewer latency.

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
- the only Harness-derived command form is fixed `pytest -q` plus Git-reported changed test paths;
  it passes the argv grammar and is retained in VerificationResult and TraceEvent artifacts.

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
