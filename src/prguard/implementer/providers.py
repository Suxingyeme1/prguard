"""Provider-neutral Implementer interface and bounded live-model adapters."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from pydantic import ValidationError

from prguard.implementer.errors import ProviderError
from prguard.implementer.tools import RepositoryTools
from prguard.schemas import (
    AgentToolCall,
    FixTask,
    ImplementerProposal,
    ProposalEnvelope,
    TokenUsage,
)


@dataclass(frozen=True)
class ProviderRequest:
    task: FixTask
    attempt: int
    feedback: str | None = None
    deadline_monotonic: float | None = None


class ImplementerProvider(Protocol):
    name: str
    model: str

    def propose(self, request: ProviderRequest, tools: RepositoryTools) -> ProposalEnvelope: ...


class ScriptedProvider:
    """Offline provider used for deterministic demos and contract tests."""

    name = "scripted"
    model = "deterministic-fixture"

    def __init__(self, proposals: list[ImplementerProposal]) -> None:
        if not proposals:
            raise ProviderError("scripted provider requires at least one proposal")
        self._proposals = proposals

    @classmethod
    def from_file(cls, path: Path) -> ScriptedProvider:
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
            return cls([ImplementerProposal.model_validate(value) for value in values])
        except (OSError, ValueError, ValidationError) as exc:
            raise ProviderError(f"invalid scripted proposal file: {exc}") from exc

    def propose(self, request: ProviderRequest, tools: RepositoryTools) -> ProposalEnvelope:
        if request.attempt >= len(self._proposals):
            raise ProviderError("scripted provider has no proposal for this attempt")
        calls: list[AgentToolCall] = []
        listing = tools.list_files("**/*.py", 200)
        calls.append(
            AgentToolCall(
                sequence=0,
                name="list_files",
                arguments={"pattern": "**/*.py", "max_results": 200},
                succeeded=True,
                output_bytes=len(json.dumps(listing).encode()),
            )
        )
        files = listing["files"]
        if files:
            result = tools.read_file(str(files[0]), 1, 400)
            calls.append(
                AgentToolCall(
                    sequence=1,
                    name="read_file",
                    arguments={"path": str(files[0]), "start_line": 1, "end_line": 400},
                    succeeded=True,
                    output_bytes=len(json.dumps(result).encode()),
                )
            )
        return ProposalEnvelope(
            proposal=self._proposals[request.attempt],
            provider=self.name,
            model=self.model,
            tool_calls=calls,
        )


_READ_TOOLS: list[dict[str, object]] = [
    {
        "type": "function",
        "name": "list_files",
        "description": "List readable repository files matching a repository-relative glob.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            "required": ["pattern", "max_results"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_text",
        "description": "Search readable text files case-insensitively and return source anchors.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "pattern": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["query", "pattern", "max_results"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "read_file",
        "description": "Read a bounded line range from one repository-relative text file.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
            "required": ["path", "start_line", "end_line"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "find_symbols",
        "description": (
            "Find Python modules, classes, functions, and methods using the bounded local AST "
            "index; returns qualified names and source line ranges."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["query", "max_results"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "list_imports",
        "description": "List statically parsed Python imports for one readable source file.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["path", "max_results"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "find_callers",
        "description": (
            "Find direct lexical Python call sites for a symbol. Results are static "
            "approximations, not a runtime-complete call graph."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["symbol", "max_results"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "find_callees",
        "description": (
            "List direct lexical calls made by a Python function or method, forming the "
            "bounded outgoing side of the static call graph."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["symbol", "max_results"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "find_references",
        "description": (
            "Find lexical Python references to a symbol with file, line, scope, and "
            "resolution evidence."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["symbol", "max_results"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "find_related_tests",
        "description": (
            "Rank Python test files related to a source path or symbol using deterministic "
            "filename, import, and reference evidence."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["target", "max_results"],
            "additionalProperties": False,
        },
    },
]

_SUBMIT_PATCH: dict[str, object] = {
        "type": "function",
        "name": "submit_patch",
        "description": (
            "Submit the complete standard Git unified diff against the base commit and an "
            "auditable plan. The patch must use diff --git, --- a/path, +++ b/path, and @@ hunk "
            "headers. Do not use Markdown fences or *** Begin Patch markers. Call exactly once "
            "after inspecting relevant source and tests."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "plan": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 12,
                },
                "summary": {"type": "string"},
                "patch": {"type": "string"},
                "tests_changed": {"type": "boolean"},
            },
            "required": ["plan", "summary", "patch", "tests_changed"],
            "additionalProperties": False,
        },
}

_SUBMIT_EDITS: dict[str, object] = {
    "type": "function",
    "name": "submit_edits",
    "description": (
        "Submit exact structured text replacements or new files. PRGuard applies them in an "
        "isolated worktree and asks Git to generate the final Patch. Prefer this over manually "
        "constructing a unified diff. Each replace_text old_text must match exactly once."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "plan": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 12,
            },
            "summary": {"type": "string"},
            "edits": {
                "type": "array",
                "minItems": 1,
                "maxItems": 32,
                "items": {
                    "anyOf": [
                        {
                            "type": "object",
                            "properties": {
                                "operation": {"type": "string", "enum": ["replace_text"]},
                                "path": {"type": "string"},
                                "old_text": {"type": "string"},
                                "new_text": {"type": "string"},
                            },
                            "required": ["operation", "path", "old_text", "new_text"],
                            "additionalProperties": False,
                        },
                        {
                            "type": "object",
                            "properties": {
                                "operation": {"type": "string", "enum": ["create_file"]},
                                "path": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["operation", "path", "content"],
                            "additionalProperties": False,
                        },
                    ]
                },
            },
            "tests_changed": {"type": "boolean"},
        },
        "required": ["plan", "summary", "edits", "tests_changed"],
        "additionalProperties": False,
    },
}

_TOOLS: list[dict[str, object]] = [*_READ_TOOLS, _SUBMIT_EDITS, _SUBMIT_PATCH]

_INSTRUCTIONS = """You are PRGuard's single Implementer for a real local repository.
Inspect the repository using the bounded text and Python AST navigation tools. Use AST symbol,
import, caller/reference, and related-test results as static evidence, then read the relevant lines.
Form an internal plan, then prefer submit_edits with exact old/new text operations. PRGuard will
apply those edits locally and ask Git to generate the Patch. submit_patch remains a compatibility
fallback when the required change cannot be represented safely as exact text edits.
Do not modify protected paths, do not invent source you have not read, and do not request or emit
shell commands. Preserve existing behavior and add or modify public tests only when necessary.
If verification feedback is present, return a corrected complete proposal against the same base
commit. A fallback patch string must start with `diff --git a/<path> b/<path>` and
contain `--- a/<path>`, `+++ b/<path>`, and an `@@` hunk header. Never include Markdown fences or
`*** Begin Patch` / `*** End Patch` markers around the patch.
"""


def _chat_tools(tools: list[dict[str, object]] | None = None) -> list[dict[str, object]]:
    """Translate Responses-style direct tools to Chat Completions function tools."""
    tools = tools or _TOOLS
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in tools
    ]


def _safe_error(prefix: str, exc: Exception, *, secret: str | None = None) -> ProviderError:
    detail = str(exc)
    if secret:
        detail = detail.replace(secret, "[REDACTED]")
    return ProviderError(f"{prefix}: {type(exc).__name__}: {detail}")


def _validated_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.username or parsed.password:
        raise ProviderError("provider base URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ProviderError("provider base URL must not contain a query or fragment")
    loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise ProviderError("provider base URL must use HTTPS (HTTP is allowed only on loopback)")
    if not parsed.netloc:
        raise ProviderError("provider base URL must include a host")
    return value.rstrip("/")


def _call_read_tool(
    name: str, arguments: dict[str, object], tools: RepositoryTools
) -> dict[str, object]:
    if name == "list_files":
        return tools.list_files(**arguments)  # type: ignore[arg-type]
    if name == "search_text":
        return tools.search_text(**arguments)  # type: ignore[arg-type]
    if name == "read_file":
        return tools.read_file(**arguments)  # type: ignore[arg-type]
    if name == "find_symbols":
        return tools.find_symbols(**arguments)  # type: ignore[arg-type]
    if name == "list_imports":
        return tools.list_imports(**arguments)  # type: ignore[arg-type]
    if name == "find_callers":
        return tools.find_callers(**arguments)  # type: ignore[arg-type]
    if name == "find_callees":
        return tools.find_callees(**arguments)  # type: ignore[arg-type]
    if name == "find_references":
        return tools.find_references(**arguments)  # type: ignore[arg-type]
    if name == "find_related_tests":
        return tools.find_related_tests(**arguments)  # type: ignore[arg-type]
    raise ProviderError(f"unknown Implementer tool: {name}")


class OpenAIResponsesProvider:
    """Bounded direct-tool loop implemented with the OpenAI Responses API."""

    name = "openai"

    def __init__(
        self,
        *,
        model: str = "gpt-5.6-terra",
        reasoning_effort: str = "medium",
        timeout_seconds: float = 300,
        client: object | None = None,
    ) -> None:
        self.model = model
        self.reasoning_effort = reasoning_effort
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ProviderError(
                    "OpenAI provider requires the optional 'agent' dependency"
                ) from exc
            client = OpenAI(timeout=timeout_seconds)
        self.client = client

    def propose(self, request: ProviderRequest, tools: RepositoryTools) -> ProposalEnvelope:
        prompt = {
            "case_id": request.task.case_id,
            "base_commit": request.task.base_commit,
            "issue": request.task.issue,
            "writable_paths": request.task.writable_paths,
            "protected_paths": request.task.protected_paths,
            "verification_commands": [command.argv for command in request.task.commands],
            "attempt": request.attempt,
            "verification_feedback": request.feedback,
        }
        input_messages: list[object] = [
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}
        ]
        calls: list[AgentToolCall] = []
        usage = TokenUsage()
        last_response_id: str | None = None
        for _turn in range(request.task.max_tool_calls + 1):
            try:
                timeout = None
                if request.deadline_monotonic is not None:
                    timeout = max(0.1, request.deadline_monotonic - time.monotonic())
                response = self.client.responses.create(  # type: ignore[attr-defined]
                    model=self.model,
                    instructions=_INSTRUCTIONS,
                    input=input_messages,
                    tools=_TOOLS,
                    reasoning={"effort": self.reasoning_effort},
                    store=False,
                    timeout=timeout,
                )
            except Exception as exc:
                raise ProviderError(f"OpenAI Responses request failed: {exc}") from exc
            last_response_id = getattr(response, "id", None)
            api_usage = getattr(response, "usage", None)
            if api_usage is not None:
                usage.input_tokens += int(getattr(api_usage, "input_tokens", 0) or 0)
                usage.output_tokens += int(getattr(api_usage, "output_tokens", 0) or 0)
                details = getattr(api_usage, "input_tokens_details", None)
                usage.cached_tokens += int(getattr(details, "cached_tokens", 0) or 0)
            input_messages.extend(response.output)
            function_calls = [item for item in response.output if item.type == "function_call"]
            if not function_calls:
                raise ProviderError("model ended without submitting a proposal")
            outputs: list[dict[str, object]] = []
            for item in function_calls:
                if len(calls) >= request.task.max_tool_calls:
                    raise ProviderError("Implementer tool-call budget exhausted")
                try:
                    arguments = json.loads(item.arguments)
                    if item.name in {"submit_edits", "submit_patch"}:
                        proposal = ImplementerProposal.model_validate(arguments)
                        summary = (
                            {"patch_bytes": len(proposal.patch.encode())}
                            if proposal.patch is not None
                            else {"edit_count": len(proposal.edits)}
                        )
                        calls.append(
                            AgentToolCall(
                                sequence=len(calls),
                                name=item.name,
                                arguments=summary,
                                succeeded=True,
                                output_bytes=0,
                            )
                        )
                        return ProposalEnvelope(
                            proposal=proposal,
                            provider=self.name,
                            model=self.model,
                            response_id=last_response_id,
                            token_usage=usage,
                            tool_calls=calls,
                        )
                    result = _call_read_tool(item.name, arguments, tools)
                    serialized = json.dumps(result, ensure_ascii=False)
                    calls.append(
                        AgentToolCall(
                            sequence=len(calls),
                            name=item.name,
                            arguments=arguments,
                            succeeded=True,
                            output_bytes=len(serialized.encode()),
                        )
                    )
                except Exception as exc:
                    serialized = json.dumps({"error": str(exc)}, ensure_ascii=False)
                    calls.append(
                        AgentToolCall(
                            sequence=len(calls),
                            name=item.name,
                            arguments={},
                            succeeded=False,
                            output_bytes=len(serialized.encode()),
                            error=str(exc),
                        )
                    )
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": serialized,
                    }
                )
            input_messages.extend(outputs)
        raise ProviderError("Implementer response-turn budget exhausted")



class DeepSeekChatProvider:
    """Bounded tool loop for DeepSeek's OpenAI-compatible Chat Completions API."""

    name = "deepseek"
    default_model = "deepseek-v4-pro"
    default_base_url = "https://api.deepseek.com"

    def __init__(
        self,
        *,
        model: str = default_model,
        reasoning_effort: str = "high",
        timeout_seconds: float = 300,
        client: object | None = None,
        base_url: str | None = None,
    ) -> None:
        if reasoning_effort not in {"high", "max"}:
            raise ProviderError("DeepSeek reasoning effort must be 'high' or 'max'")
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.base_url = _validated_base_url(
            base_url or os.environ.get("DEEPSEEK_BASE_URL", self.default_base_url)
        )
        self._api_key: str | None = None
        if client is None:
            self._api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not self._api_key:
                raise ProviderError(
                    "DeepSeek provider requires DEEPSEEK_API_KEY; do not pass secrets on the CLI"
                )
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ProviderError(
                    "DeepSeek provider requires the optional 'agent' dependency"
                ) from exc
            client = OpenAI(
                api_key=self._api_key,
                base_url=self.base_url,
                timeout=timeout_seconds,
            )
        self.client = client

    def propose(self, request: ProviderRequest, tools: RepositoryTools) -> ProposalEnvelope:
        prompt = {
            "case_id": request.task.case_id,
            "base_commit": request.task.base_commit,
            "issue": request.task.issue,
            "writable_paths": request.task.writable_paths,
            "protected_paths": request.task.protected_paths,
            "verification_commands": [command.argv for command in request.task.commands],
            "attempt": request.attempt,
            "verification_feedback": request.feedback,
        }
        messages: list[object] = [
            {"role": "system", "content": _INSTRUCTIONS},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ]
        calls: list[AgentToolCall] = []
        usage = TokenUsage()
        last_response_id: str | None = None
        provider_metadata = {
            "api": "chat.completions",
            "base_url": self.base_url,
            "reasoning_effort": self.reasoning_effort,
            "thinking": "enabled",
        }
        for _turn in range(request.task.max_tool_calls + 1):
            timeout = None
            if request.deadline_monotonic is not None:
                timeout = max(0.1, request.deadline_monotonic - time.monotonic())
            try:
                response = self.client.chat.completions.create(  # type: ignore[attr-defined]
                    model=self.model,
                    messages=messages,
                    tools=_chat_tools(),
                    reasoning_effort=self.reasoning_effort,
                    extra_body={"thinking": {"type": "enabled"}},
                    timeout=timeout,
                )
            except Exception as exc:
                raise _safe_error(
                    "DeepSeek Chat request failed", exc, secret=self._api_key
                ) from exc
            last_response_id = getattr(response, "id", None)
            fingerprint = getattr(response, "system_fingerprint", None)
            if fingerprint:
                provider_metadata["system_fingerprint"] = str(fingerprint)
            api_usage = getattr(response, "usage", None)
            if api_usage is not None:
                usage.input_tokens += int(getattr(api_usage, "prompt_tokens", 0) or 0)
                usage.output_tokens += int(getattr(api_usage, "completion_tokens", 0) or 0)
                details = getattr(api_usage, "prompt_tokens_details", None)
                usage.cached_tokens += int(getattr(details, "cached_tokens", 0) or 0)
            choices = getattr(response, "choices", None) or []
            if not choices:
                raise ProviderError("DeepSeek returned no completion choices")
            choice = choices[0]
            message = choice.message
            finish_reason = getattr(choice, "finish_reason", None)
            if finish_reason:
                provider_metadata["finish_reason"] = str(finish_reason)
            messages.append(message)
            function_calls = getattr(message, "tool_calls", None) or []
            if not function_calls:
                raise ProviderError("model ended without submitting a proposal")
            for item in function_calls:
                if len(calls) >= request.task.max_tool_calls:
                    raise ProviderError("Implementer tool-call budget exhausted")
                name = item.function.name
                try:
                    arguments = json.loads(item.function.arguments)
                    if name in {"submit_edits", "submit_patch"}:
                        proposal = ImplementerProposal.model_validate(arguments)
                        summary = (
                            {"patch_bytes": len(proposal.patch.encode())}
                            if proposal.patch is not None
                            else {"edit_count": len(proposal.edits)}
                        )
                        calls.append(
                            AgentToolCall(
                                sequence=len(calls),
                                name=name,
                                arguments=summary,
                                succeeded=True,
                                output_bytes=0,
                            )
                        )
                        return ProposalEnvelope(
                            proposal=proposal,
                            provider=self.name,
                            model=self.model,
                            response_id=last_response_id,
                            provider_metadata=provider_metadata,
                            token_usage=usage,
                            tool_calls=calls,
                        )
                    result = _call_read_tool(name, arguments, tools)
                    serialized = json.dumps(result, ensure_ascii=False)
                    calls.append(
                        AgentToolCall(
                            sequence=len(calls),
                            name=name,
                            arguments=arguments,
                            succeeded=True,
                            output_bytes=len(serialized.encode()),
                        )
                    )
                except Exception as exc:
                    serialized = json.dumps({"error": str(exc)}, ensure_ascii=False)
                    calls.append(
                        AgentToolCall(
                            sequence=len(calls),
                            name=name,
                            arguments={},
                            succeeded=False,
                            output_bytes=len(serialized.encode()),
                            error=str(exc),
                        )
                    )
                messages.append(
                    {"role": "tool", "tool_call_id": item.id, "content": serialized}
                )
        raise ProviderError("Implementer response-turn budget exhausted")
