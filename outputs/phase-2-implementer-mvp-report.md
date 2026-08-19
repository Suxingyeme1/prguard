# PRGuard Phase 2: single Implementer MVP report

Date: 2026-08-19

## Result

PRGuard 0.2.0 now has a working Issue-to-Patch `fix` path:

```text
FixTask (repository + Base Commit + Issue)
  -> detached discovery worktree
  -> bounded list/search/read tools
  -> Implementer complete unified-diff proposal
  -> Patch policy
  -> fresh deterministic Verification Harness worktree
  -> optional one replacement patch from structured failure evidence
  -> final.patch + nested JSON/Markdown/SHA-256 artifacts
```

This moves the project from a Candidate-Patch verifier to a provider-neutral Coding Agent MVP.
The deterministic scripted provider proves orchestration and replay. A live OpenAI Responses API
adapter is implemented and contract-tested, but no live-model quality claim is made because this
environment has no `OPENAI_API_KEY` and no repository content was sent externally.

## Implemented

- `FixTask`, `ImplementerProposal`, `ProposalEnvelope`, `AgentToolCall`, `FixAttempt`, `FixReport`,
  and terminal `FixOutcome` Pydantic contracts;
- read-only `list_files`, `search_text`, and `read_file` tools with repository containment,
  credential-like path denial, symlink containment, binary/file/context byte limits, line limits,
  and result limits;
- complete unified-diff submission instead of direct model filesystem writes;
- writable/protected glob enforcement, maximum patch bytes, maximum changed files, consistent
  `diff --git` and `---/+++` headers, and rejection of binary/rename/copy patches;
- provider-neutral protocol, deterministic scripted provider, and live OpenAI Responses adapter;
- strict function schemas, bounded tool-call count, provider timeout tied to task deadline, token
  accounting fields, and stored tool-call evidence;
- one initial implementation plus at most one complete replacement patch against the same Base
  Commit;
- structured repair feedback containing prior patch, outcome, policy violations, and only failed
  command evidence—never gold patches, defect labels, or hidden tests;
- working `prguard fix` CLI with configurable provider, model, reasoning effort, task, and artifact
  root;
- fix-run JSON/Markdown, proposal/patch files, nested verification artifacts, final patch, and one
  SHA-256 manifest covering every nested file;
- project wheel `prguard-0.2.0-py3-none-any.whl` built successfully.

The OpenAI adapter follows the official Responses API direct function-calling pattern: preserve
response output, execute only application-owned tools, and return `function_call_output` items.
The adapter uses `store=false`; repository content is disclosed only by bounded tool outputs.

## Demo cases

| Case | Flow | Result |
|---|---|---|
| `direct-success` | Issue -> one Patch -> 2 pytest tests | accepted |
| `repair-once` | initial Patch -> 1 failed/2 passed -> replacement Patch -> 3 passed | accepted |

The final repair demo:

- run id: `0d78c198-fb38-4d81-9f2d-6d644d62f701`;
- base commit: `52037f668c84c7d62f83d26fd37f2882f7e51c90`;
- initial patch SHA-256: `dbf57b8f480b0c24bd11bc16391ecb40d14d4374e907da904edff5ed8e5809d0`;
- final patch SHA-256: `473925523d5455c47a123250a767c3b9489bd1b8e732df5693db23422f2382ea`;
- fix manifest payload SHA-256:
  `0f7f5f15fe1b3819cf5bed99179c6564e4bb76937e1f6bed452946287aecff8f`;
- total offline workflow duration: 1.229 seconds;
- source checkout remained clean;
- complete fix manifest verified successfully.

The scripted provider inspected repository files, but its pre-authored patches mean these results
measure deterministic workflow behavior—not model task resolution.

## Quality gates

- Ruff: all checks passed;
- pytest: 58 passed in 11.11 seconds;
- wheel build: passed;
- CLI `run`, `verify-manifest`, `replay`, and `fix` entry points: present;
- direct CLI repair demo: passed;
- nested fix-manifest verification: passed.

New coverage includes repository read policies, credential/symlink/path traversal denial, context
budgets, root-level recursive globs, Patch header smuggling, writable/protected path rules, OpenAI
tool-loop contracts, direct success, repair evidence, repair budget exhaustion, protected Patch
blocking, CLI execution, and nested Artifact tampering.

## Honest boundary

- No live model run has been performed. The OpenAI adapter is implemented against the current SDK
  and tested with a deterministic fake Responses client, but account/model availability, real
  latency, token use, and task-resolution quality remain unverified.
- The discovery tools are application-level capabilities, not an OS sandbox. A third-party Python
  provider loaded in-process is trusted code; the bundled OpenAI provider only exposes declared
  read tools to the remote model.
- Git worktrees still do not contain hostile test code. Public repositories require container,
  network, uid, and resource isolation before execution.
- The Patch MVP intentionally rejects binary, rename/copy, and non-standard/quoted path diffs.
- `pytest` and `ruff` remain the only command capability grammar. Project-specific commands require
  new explicit parsers and tests.
- Model-selected source snippets may contain ordinary in-repository secrets that are not identified
  by filename. Teams need repository classification/redaction policy before production use.

## Remaining acceptance work before Phase 3

1. Configure an authorized API credential and explicitly approve sending the small fixture source
   to the selected provider.
2. Run the two fixture tasks and 2–3 manually checked real repository tasks with a fixed model and
   reasoning setting.
3. Record task resolution, fail-to-pass/pass-to-pass, patch minimality, token use, latency, and
   repair count from raw artifacts.
4. Fix any observed tool/prompt failures without expanding permissions.
5. Freeze a `fix-v1` live-demo manifest.

After those checks, Phase 2 can be called fully validated and the next product priority is the
read-only Independent Reviewer plus `prguard review` CLI.

