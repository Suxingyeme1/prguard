# Live provider runbook

## Purpose

This runbook promotes the Phase 2 Implementer from offline workflow proof to measured live-model
evidence. Start with the two tiny public fixtures. Do not send a private or third-party repository
until its owner has approved external model processing.

## Local prerequisite

Install Python 3.12, Git, uv, and the locked optional agent dependency:

```bash
uv sync --extra agent --extra dev --no-editable --reinstall-package prguard
.venv/bin/python scripts/materialize_fix_fixtures.py \
  --output work/materialized-fix-fixtures
```

Enter the key without placing it in shell history. PRGuard deliberately has no `--api-key` option:

```bash
read -rs "DEEPSEEK_API_KEY?DeepSeek API key: " && echo
export DEEPSEEK_API_KEY
```

Run the direct-success case first:

```bash
.venv/bin/prguard fix work/materialized-fix-fixtures/direct-success/task.json \
  --provider deepseek \
  --model deepseek-v4-pro \
  --reasoning-effort high \
  --progress \
  --artifacts work/deepseek-live-artifacts
```

If accepted, run `repair-once` with a fresh artifact root. The model is not forced to reproduce the
scripted fixture's deliberately broken first attempt, so repair behavior is recorded only when an
actual verification failure occurs. Finish by removing the key from the interactive environment:

```bash
unset DEEPSEEK_API_KEY
```

## Promotion criteria

A run counts as live evidence only when all of the following hold:

- the fix manifest verifies and its resolved base commit matches the fixture;
- the final Harness result is `passed`, with no policy violation or checkout mutation;
- the proposal records provider, model, response ID, token usage, and available backend fingerprint;
- no credential appears in task, report, proposal, patch, command output, or manifest;
- a human checks that the diff is minimal and actually resolves the Issue.

Archive accepted evidence under `outputs/` only after these checks. Failed attempts also remain
useful raw evidence but must be labelled as failures rather than silently discarded.

For the public real-repository flow, follow [Demo A](demo-a.md). Its materializer reconstructs and
checks the frozen Humanize evaluation Base Commit before any model call.

## Server execution

Use a dedicated unprivileged account and a clean checkout at the same project revision. Install
from `uv.lock`; inject `DEEPSEEK_API_KEY` through the server's secret manager or a session-scoped
environment; never copy a `.env` file into the repository. Restrict file permissions with
`umask 077` before creating artifacts.

Do not put a secret assignment in process arguments such as
`env DEEPSEEK_API_KEY=<value> prguard ...`: process listings and orchestration logs can expose that
argv. Source a mode-`0600` environment file in a privileged/session shell or use the server secret
manager, export the variable, then launch the unprivileged process with inherited environment. Do
not print `env`, use `ps ... e`, or enable shell tracing. Rotate a credential immediately if any
diagnostic output exposes it, and scan copied Artifacts for provider-key patterns before freezing.

The current Git worktree boundary is not a hostile-code sandbox. Until container/network/resource
isolation is implemented, run only trusted fixtures or repositories whose test code you are
willing to execute as that server account. Copy the complete artifact directory back, verify its
manifest independently, and record the server OS, Python version, Git version, provider/model, and
wall-clock duration alongside the run.
