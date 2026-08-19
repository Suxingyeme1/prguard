# Phase 2.1 report: DeepSeek live-provider gate

Date: 2026-08-19

## Outcome

The DeepSeek provider path is implemented, offline-validated, and minimally live-validated. PRGuard
0.2.1 can drive the
existing Issue-to-Patch workflow through DeepSeek's OpenAI-compatible Chat Completions API without
granting the model shell access or direct filesystem writes. Two authorized public-fixture runs
were accepted after resolving one API-compatibility issue and one Patch-format issue.

This is small-sample task-resolution evidence, not a broad DeepSeek quality claim.

## Implemented

- Added `DeepSeekChatProvider` behind the provider-neutral Implementer protocol.
- Exposed only `list_files`, `search_text`, `read_file`, and `submit_patch` function tools.
- Failed closed when a turn contains no tool call and retained assistant tool-call messages across
  rounds, including DeepSeek thinking-mode context. The first live request showed that thinking
  mode rejects `tool_choice=required`, so the adapter omits that incompatible API parameter while
  retaining the local fail-closed rule.
- Enabled thinking mode with `high` effort by default; model and effort remain explicit CLI inputs.
- Accumulated prompt, completion, and cached-token usage across API requests.
- Recorded response ID, API class, safe base URL, reasoning setting, finish reason, and available
  backend fingerprint in the proposal envelope.
- Read credentials only from `DEEPSEEK_API_KEY`; no API-key CLI or task field exists.
- Rejected endpoint URLs containing credentials, query strings, fragments, or insecure remote HTTP.
- Retained all existing Patch policy, fresh-worktree verification, timeouts, repair limit, and
  SHA-256 artifact controls.
- Added a live-provider runbook and ADR 0007.

## Verification

- Ruff: all checks passed.
- Pytest: 66 passed in 13.25 seconds.
- DeepSeek tests cover the bounded function loop, missing credentials, reasoning-effort validation,
  endpoint safety, loopback development endpoints, and a real OpenAI SDK HTTP transport round trip.
- Wheel: `prguard-0.2.1-py3-none-any.whl` built successfully from the locked environment.
- Offline repair fixture: first verification failed with one regression, one evidence-guided
  replacement Patch passed all three tests, and the source checkout remained clean.
- Fix Manifest `414713f2-c945-4270-8f0c-6cdae94e42d5` verified independently.
- Artifact credential-pattern scan returned no matches.

## Preserved boundary

The model selects and receives bounded source excerpts, but it does not execute commands, apply its
Patch, decide policy, or declare success. The deterministic Harness owns those operations. The
current worktree/process controls are still not a hostile-code sandbox, so server validation must
start with trusted fixtures under an unprivileged account.

Private reasoning content is passed back only as required for a live tool-call turn; it is not
written into PRGuard artifacts. Submitted plans, tool-call metadata, Patch content, identifiers,
usage, and deterministic command evidence remain auditable.

## Next gate

1. Make `DEEPSEEK_API_KEY` visible to the task process without putting it in chat, source, task JSON,
   CLI arguments, or repository files.
2. Run `direct-success`, verify and human-check the frozen artifact.
3. Run `repair-once`; record repair only if the model actually produces a failing first Patch.
4. Run two or three small, manually checked real-repository Issues with source-owner approval.
5. Freeze token, latency, attempt count, task resolution, PASS_TO_PASS, and failure evidence.
6. Promote Phase 2 to live-validated, then implement the read-only Independent Reviewer and
   `prguard review` CLI.

## Evidence

- Offline artifacts: `outputs/phase-2-1-offline-artifacts/414713f2-c945-4270-8f0c-6cdae94e42d5`
- Run instructions: `docs/live-provider-runbook.md`
- Decision: `docs/adr/0007-deepseek-chat-provider.md`
