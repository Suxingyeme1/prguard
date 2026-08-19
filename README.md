# PRGuard

PRGuard is a verifiable multi-agent coding system for real code repositories: an Implementer
generates and repairs a patch from an Issue, an independently scoped Reviewer supplies code-review
evidence, and a deterministic harness owns tests, permissions, regression gates, and auditable
delivery.

The primary product flow is repository-level coding, not a comparison experiment or a review-only
bot:

```text
Issue -> understand/search repository -> plan -> edit code/tests -> verify
      -> repair once from deterministic evidence -> Review-ready Patch
```

PR review and controlled repair are a quality module around that core capability.

This repository now implements the local **Phase 4B Issue-to-PR MVP** on top of the Phase 0/1
contracts and deterministic harness. It includes offline scripted providers for reproducible demos
plus optional DeepSeek Chat Completions and OpenAI Responses adapters. A blocking independent
review can trigger exactly one bounded Implementer replacement Patch followed by a fresh final
gate. It intentionally does not yet integrate GitHub, an API server, or containers.

The coding MVP has now been exercised against three current public Issues from Humanize,
PrettyTable, and Inflect at frozen upstream commits. All three reached a verified one-file Patch;
the Humanize run demonstrated one evidence-guided replacement attempt and passed pytest plus ruff.
Extended functional regression checks passed 701, 338, and 208 tests respectively. The frozen set
also retains a provider timeout, two malformed-Patch failures, and one tool-budget exhaustion rather
than reporting only successful runs. See the [real-repository report](outputs/real-repository-cases-report.md).

The Phase 4A Demo B gate has also passed locally and on an unprivileged server run: DeepSeek
identified a seeded regression, requested changes, produced one complete replacement Patch, and
passed both FAIL_TO_PASS and PASS_TO_PASS final gates. This proves the integrated mechanism on one
known case, not broad review precision or repository-level generalization. Automatic `fix --review`
composition is now deterministically tested and has passed local and unprivileged-server live gates.

## Product entries

- `prguard fix`: repository + base commit + Issue -> tested, review-ready patch. Planning remains
  an internal Implementer step; the test runner is not an Agent. `--review` continues an accepted
  Fix through independent review, optional one-time replacement repair, and a top-level final gate.
- `prguard review`: repository + Issue + candidate patch -> deterministic verification plus
  independently scoped structured findings and verdict. `--repair` permits one controlled full
  replacement Patch and a fresh final Harness gate.

## What works now

- gives the Implementer byte-budgeted `list_files`, `search_text`, and `read_file` tools without a
  shell or direct filesystem writes;
- accepts one complete unified-diff proposal, enforcing writable/protected paths, patch bytes, and
  changed-file limits before execution;
- supports an initial implementation plus at most one replacement patch based on structured test
  failure evidence;
- exposes provider-neutral scripted, DeepSeek Chat Completions, and OpenAI Responses Implementer
  adapters;
- provides a working `prguard fix` CLI and nested fix/verification manifests;
- provides a working `prguard review` CLI with a fresh read-only model context, source-linked
  findings, deterministic verdict policy, and nested review/verification manifests;
- connects a blocking review to at most one controlled replacement Patch while retaining the
  original candidate, initial review, repair proposal, final verification, and recursive manifest;
- composes `fix --review` into one total time budget and top-level Issue-to-PR Manifest; failed Fix
  stages never invoke the Reviewer;
- validates a local Git repository and an exact base commit;
- creates and removes a detached Git worktree per run;
- checks and applies a candidate patch without invoking a shell;
- executes only explicitly allowed `pytest` and `ruff` argv forms;
- enforces per-command and total task deadlines and bounded captured output;
- fails closed when an Implementer or Reviewer result returns after its logical stage deadline;
- records structured verification results and trace events;
- blocks protected-file changes and reports writes beside the isolated worktree;
- writes JSON, Markdown, the final diff, and a SHA-256 manifest;
- verifies an artifact directory without rerunning untrusted code.

## Quick start

```bash
uv sync --extra dev --no-editable --reinstall-package prguard
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/python scripts/materialize_fixtures.py
.venv/bin/prguard run benchmark/generated/correct-patch/case.json \
  --artifacts work/example-artifacts
.venv/bin/prguard verify-manifest work/example-artifacts/<run-id>/manifest.json
.venv/bin/prguard replay work/example-artifacts/<run-id>/manifest.json \
  --artifacts work/replayed-artifacts

# Reproducible offline Issue-to-Patch demo with one failed attempt and one repair
.venv/bin/python scripts/materialize_fix_fixtures.py \
  --output work/materialized-fix-fixtures
.venv/bin/prguard fix work/materialized-fix-fixtures/repair-once/task.json \
  --provider scripted \
  --proposal-sequence work/materialized-fix-fixtures/repair-once/proposals.json \
  --artifacts work/fix-artifacts

# One-command implementation plus independent review for an IssueToPRTask
.venv/bin/prguard fix work/issue-to-pr-task.json \
  --provider deepseek \
  --review \
  --review-provider deepseek \
  --artifacts work/issue-to-pr-artifacts

# Independent review of a candidate Patch
.venv/bin/python scripts/materialize_fixtures.py \
  --output work/materialized-review-fixtures
.venv/bin/prguard review work/materialized-review-fixtures/regression/case.json \
  --provider deepseek \
  --model deepseek-v4-pro \
  --reasoning-effort high \
  --artifacts work/review-artifacts

# Add --repair when the task also declares writable_paths and review_timeout_seconds
.venv/bin/prguard review work/review-repair-task.json \
  --provider deepseek \
  --repair \
  --repair-provider deepseek \
  --artifacts work/review-repair-artifacts
```

The five fixture cases cover a correct patch, incorrect patch, regression, patch application
failure, and command timeout. They are materialized into ignored Git repositories so the source
checkout does not contain nested repositories.

For a live DeepSeek run, install the agent extra, place the API key only in the process environment,
and select the provider explicitly:

```bash
uv sync --extra agent --extra dev --no-editable --reinstall-package prguard
read -rs "DEEPSEEK_API_KEY?DeepSeek API key: " && echo
export DEEPSEEK_API_KEY
.venv/bin/prguard fix work/materialized-fix-fixtures/direct-success/task.json \
  --provider deepseek \
  --model deepseek-v4-pro \
  --reasoning-effort high \
  --artifacts work/deepseek-live-artifacts
unset DEEPSEEK_API_KEY
```

Never put an API key in task JSON, a CLI argument, a proposal, or an artifact path. Repository bytes
are sent only when the model calls one of the bounded read tools. See the
[live-provider runbook](docs/live-provider-runbook.md) before sending non-fixture source.

## Trust boundary

Phase 1 provides process control and post-execution write detection, not a security sandbox.
Commands are launched with `shell=False`, a minimal environment, a private HOME/TMPDIR, and a
strict tool grammar. Arbitrary test code can still access resources available to the host user.
Running untrusted public repositories requires the container/network/resource isolation planned
for a later phase. See [the threat model](docs/threat-model.md).

## Project map

- `src/prguard/schemas`: versioned public contracts;
- `src/prguard/harness`: Git/worktree, command, policy, and artifact implementation;
- `src/prguard/implementer`: bounded repository tools, Patch policy, and provider adapters;
- `src/prguard/fix`: Issue-to-Patch orchestration and fix-run artifacts;
- `src/prguard/review`: independent review plus optional controlled-repair orchestration;
- `src/prguard/pipeline`: top-level Issue-to-PR composition and recursive delivery artifacts;
- `benchmark/fixtures`: deterministic fixture templates;
- `benchmark/fix-fixtures`: manually checked Issue-to-Patch workflow fixtures;
- `outputs/real-repository-cases`: frozen live-run reports, diffs, traces, and manifests for three
  public open-source Issues;
- `tests`: unit, integration, contract, and security checks;
- `docs`: architecture, evaluation protocol, case authoring, and ADRs.

See [milestones](docs/milestones.md) for the coding-first delivery order.

The design goal is useful repository-level coding backed by evidence, not agent count: every
conclusion must resolve to an input commit, candidate diff, command result, policy decision, and
content-addressed artifact.
