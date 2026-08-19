# ADR 0007: DeepSeek uses a bounded Chat Completions adapter

- Status: accepted
- Date: 2026-08-19

## Context

Phase 2 needs live-model evidence without coupling the Implementer workflow to one vendor API.
DeepSeek exposes an OpenAI-compatible Chat Completions interface with function tools, thinking mode,
usage accounting, and a backend fingerprint. Its beta strict-function mode is not necessary for
PRGuard because tool arguments and patches already fail closed at local schema and policy gates.

## Decision

Implement a separate `DeepSeekChatProvider` behind the existing `ImplementerProvider` protocol.
Expose only `list_files`, `search_text`, `read_file`, and `submit_patch`; reject any turn that ends
without a tool call; preserve assistant messages between tool rounds; enable thinking with high
effort by default; and account for every request's prompt, completion, and cached tokens. Do not
send `tool_choice=required`, because DeepSeek thinking mode rejects that combination.

Read `DEEPSEEK_API_KEY` only from the process environment. Allow a configurable base URL through
the environment or constructor, but reject embedded credentials, query strings, fragments, and
non-HTTPS remote endpoints. Do not archive private reasoning content. Archive only auditable tool
records, the submitted proposal, identifiers, usage, and non-secret provider metadata.

Use the standard endpoint and local validation rather than beta strict mode. A malformed tool call
becomes bounded error feedback; an invalid patch is rejected before verification.

## Consequences

The deterministic Harness and artifacts remain provider-neutral, while DeepSeek can be evaluated
without granting shell or write access. Exact generation is not replayable, so provider/model,
backend fingerprint, token counts, final patch, and deterministic verification evidence define the
reproducible boundary. Live success cannot be claimed until authorized online fixture runs pass.

## References

- [DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls)
- [DeepSeek Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode)
- [DeepSeek Chat Completion API](https://api-docs.deepseek.com/api/create-chat-completion)
