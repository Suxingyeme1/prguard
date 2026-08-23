# PRGuard

[![CI](https://github.com/Suxingyeme1/prguard/actions/workflows/ci.yml/badge.svg)](https://github.com/Suxingyeme1/prguard/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> Issue in. Verified patch out.

PRGuard is a verifiable multi-agent coding system for real repositories. An Implementer turns an
Issue into a patch, an Independent Reviewer checks the change in a separate read-only context, and
a deterministic harness owns execution, timeouts, policy gates, regression checks, and delivery.

The result is not just model output. Every accepted change is tied to an exact base commit, a
unified diff, command evidence, structured decisions, and a SHA-256 manifest.

```mermaid
flowchart LR
    I["GitHub/local Issue + repository + base commit"] --> A["Implementer<br/>text + AST navigation · plan · structured edits"]
    A --> P["Git-authored unified diff"]
    P --> H["Deterministic harness<br/>policy · pytest · ruff · timeout"]
    H -->|"failure evidence; once"| A
    H -->|"verified"| R["Independent Reviewer<br/>fresh read-only context"]
    R --> G["Final deterministic gate"]
    G --> O["Review-ready patch<br/>auditable artifacts"]
```

## Why this project

Coding agents are useful when they can change a real repository, but their claims should not decide
whether their own work is correct. PRGuard separates proposal from judgment:

- the model navigates bounded repository content with text and Python AST tools, then proposes
  exact text edits (or a compatibility Patch fallback);
- PRGuard applies structured edits in an isolated worktree and asks Git to produce the diff;
- the harness applies that patch in an isolated worktree and runs only declared argv commands;
- changed Python test modules are deterministically added to the pytest gate, so an Agent-authored
  regression test cannot sit outside a narrowly selected original test target;
- one failed verification can return structured evidence for a bounded replacement patch;
- review uses an independent context and produces source-linked findings;
- the final gate and artifact hashes are deterministic and replayable.

PRGuard currently exposes two product entries:

```text
prguard fix     repository + base commit + Issue -> tested patch
prguard review  frozen FixTask + candidate patch -> findings + optional repair
```

Planner remains an internal Implementer step. The test runner is deliberately a deterministic tool,
not another Agent.

## Try it offline

Requirements: Git, Python 3.12, and [uv](https://docs.astral.sh/uv/). No model key or network call is
needed for this demo.

```bash
uv sync --extra dev --no-editable --reinstall-package prguard
uv run python scripts/run_offline_demo.py
```

The demo materializes a tiny Git repository, submits an intentionally incomplete first patch,
returns the pytest failure to a scripted Implementer, applies one replacement patch, and verifies
the resulting recursive manifest. It prints the final patch and artifact directory.

For the online real-repository walkthrough, use
[Demo A: Humanize #366](docs/demo-a.md). It freezes the public Issue and Base Commit, discovers a
conservative verification profile, runs DeepSeek with visible progress, and retains the complete
failure/success evidence chain.

## Start from a public GitHub Issue

`fix` accepts either a reviewed Task JSON or a canonical public GitHub Issue URL. The URL form
freezes the Issue and exact commit, checks out the repository, discovers a conservative Python
verification profile, preserves the generated Task/Manifest, and continues into implementation:

```bash
uv run prguard fix \
  https://github.com/python-humanize/humanize/issues/366 \
  --workspace work/humanize-366 \
  --base-commit ce4147b6c8f8a132f772be0929d58305eb22c5d9 \
  --trust-host \
  --provider deepseek \
  --progress
```

Use the two-stage form when a person or CI policy should inspect preparation before spending model
tokens or running repository code:

```bash
uv run prguard prepare-github ISSUE_URL \
  --output work/humanize-366 --trust-host

uv run prguard verify-manifest \
  work/humanize-366/artifacts/preparation-manifest.json

uv run prguard fix work/humanize-366/artifacts/task.json \
  --provider openai --progress
```

The one-command workspace contains the same preparation artifacts plus `fix-runs/`. Omit
`--base-commit` to freeze the default-branch tip at preparation time. Unknown repositories
must explicitly select `--trust-host` or a digest-pinned `--container-image`; the model never makes
that trust decision. See the [GitHub onboarding guide](docs/github-onboarding.md), including the
optional reviewed `.prguard.toml` contract.

The same frozen Task can go directly into independent review without copying its repository,
commit, Issue, or command fields:

```bash
uv run prguard review work/humanize-366/artifacts/task.json \
  --candidate-patch path/to/final.patch \
  --provider deepseek
```

Add `--repair` to permit one controlled repair under the FixTask's original writable/size policy.

Run the complete quality gate:

```bash
uv sync --extra dev --extra agent --no-editable --reinstall-package prguard
uv run ruff check src tests scripts
uv run pytest -q
```

## What is implemented

- public GitHub Issue onboarding, exact commit resolution, safe checkout, and replayable preparation
  artifacts;
- reviewed `.prguard.toml` profiles plus fail-closed pytest/Ruff, Issue-related public-test, source
  scope, and declared Hatch VCS runtime-file discovery;
- bounded text tools plus Python AST symbol/import/reference, incoming/outgoing call, and related-test
  navigation;
- exact `replace_text`/`create_file` submissions applied locally, with Git-authored Patch output;
- compatibility unified-diff proposals with writable/protected path, file-count, and byte limits;
- detached Git worktree execution at an exact base commit;
- strict `pytest` and `ruff` argv grammars with `shell=False`;
- per-command, per-stage, and total-run deadlines with bounded captured output;
- zero-token pytest collection readiness checks before Implementer calls;
- Harness-derived `pytest -q <changed-test-files...>` execution after Patch application; changing
  tests without a declared pytest capability is policy-blocked;
- optional digest-pinned container verification with no network, read-only mounts, and resource
  limits;
- structured pytest/ruff results, policy decisions, review findings, and trace events;
- one evidence-guided implementation repair and one review-triggered controlled repair;
- provider-neutral scripted, DeepSeek Chat Completions, and OpenAI Responses adapters;
- recursive JSON/Markdown artifacts, final diff, and SHA-256 manifest verification;
- one-command GitHub-URL `fix`, inspectable `prepare-github`, `review`, `run`, `replay`, and
  `verify-manifest` CLI workflows.

## Evidence on real repositories

Three manually checked public issues were frozen at exact upstream commits and exercised end to end.
These are engineering case studies, not a claim of broad benchmark generalization.

| Repository | Issue | Selected patch | Wider regression check |
| --- | --- | --- | --- |
| Humanize | [#366](https://github.com/python-humanize/humanize/issues/366) | accepted with two structured edits; pytest + ruff | 702 passed, 74 skipped* |
| PrettyTable | [#474](https://github.com/prettytable/prettytable/issues/474) | accepted | 338 passed** |
| Inflect | [#242](https://github.com/jaraco/inflect/issues/242) | accepted | 208 passed, 16 xfailed |

\* Optional benchmark tests were excluded because their plugin was unavailable.<br>
\** One evaluator-specific version-stub assertion was deselected and recorded.

The private frozen run set intentionally retains failures too: a provider timeout, malformed
patches, a tool-budget exhaustion, and the successful Humanize repair cycle. The public repository
contains a path-free [case report](evidence/real-repositories/README.md), selected patches, and a
machine-verifiable [evidence manifest](evidence/real-repositories/manifest.json).

A separate two-case [Reviewer value check](evidence/reviewer-value/README.md) records one regression
that passed a narrow base gate but was caught and repaired by independent review, plus one accepted
Humanize Patch that was not false-blocked but incurred substantial review latency. It supports
selective review, not a general accuracy claim.

## Live model run

Install the optional provider dependency and keep the API key in the process environment:

```bash
uv sync --extra agent --extra dev --no-editable --reinstall-package prguard
export DEEPSEEK_API_KEY='...'
uv run prguard fix work/materialized-fix-fixtures/direct-success/task.json \
  --provider deepseek \
  --model deepseek-v4-pro \
  --reasoning-effort high \
  --progress \
  --artifacts work/deepseek-live-artifacts
unset DEEPSEEK_API_KEY
```

Materialize that fixture first with
`uv run python scripts/materialize_fix_fixtures.py --output work/materialized-fix-fixtures`.
Read the [live-provider runbook](docs/live-provider-runbook.md) before sending non-fixture source.

## Trust boundary

PRGuard provides strict process orchestration and post-execution write detection. Trusted tasks may
use the default host executor; higher-risk tasks can opt into
[container-backed verification](docs/container-execution.md) with a digest-pinned image, no
network, read-only mounts, non-root execution, and hard resource limits. This is defense in depth,
not protection from a malicious image, Docker daemon, container-runtime exploit, or host-kernel
vulnerability. Model access is bounded, but repository bytes requested through read tools are sent
to the selected provider.

See the [threat model](docs/threat-model.md) and [security policy](SECURITY.md) before using real
source code.

## Project map

| Path | Purpose |
| --- | --- |
| `src/prguard/onboarding` | GitHub Issue freezing, safe checkout, project-policy discovery |
| `src/prguard/implementer` | text/AST navigation, structured edits, patch policy, providers |
| `src/prguard/fix` | Issue-to-Patch orchestration and artifacts |
| `src/prguard/reviewer` | independent read-only Reviewer providers |
| `src/prguard/review` | review and controlled-repair orchestration |
| `src/prguard/pipeline` | complete Issue-to-PR composition |
| `src/prguard/harness` | Git/worktree, command policy, execution, artifacts |
| `src/prguard/schemas` | versioned public contracts |
| `benchmark` | checked deterministic fixture templates |
| `tests` | unit, integration, contract, and security tests |
| `docs` | architecture, ADRs, runbooks, evaluation protocol |

Start with the [architecture](docs/architecture.md), [milestones](docs/milestones.md), and
[contribution guide](CONTRIBUTING.md).

## Current boundary and roadmap

Version 0.8.0 adds public GitHub Issue onboarding, conservative project adaptation, bounded Python
AST/call navigation, and structured edits that are converted into Git-authored Patches. A fresh
Humanize #366 run completed this path in one Implementer attempt, then passed 702 wider regression
tests; see the [v0.8 phase report](docs/v0.8.0-phase-report.md). A first frozen pair shows both a
true-positive Reviewer repair and the high cost of reviewing a clean real-repository Patch; see the
[net-benefit note](docs/reviewer-net-benefit.md). The next priority is selective routing and more
repositories that pressure-test project adaptation. Large benchmark infrastructure and extra Agent
roles remain intentionally deferred.

PRGuard is research-grade software under active development. Accepted means “passed the declared
gate at the frozen commit,” not “proved correct for every environment.”
