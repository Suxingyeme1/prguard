"""Provider-neutral Independent Reviewer adapters."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from prguard.implementer.errors import ProviderError
from prguard.implementer.providers import (
    _READ_TOOLS,
    _call_read_tool,
    _chat_tools,
    _failure_error,
    _safe_error,
    _serialize_tool_result,
    _validated_base_url,
)
from prguard.implementer.tools import RepositoryTools
from prguard.schemas import (
    AgentToolCall,
    HarnessReport,
    ReviewEnvelope,
    ReviewerSubmission,
    ReviewTask,
    TokenUsage,
)


@dataclass(frozen=True)
class ReviewProviderRequest:
    task: ReviewTask
    candidate_patch: str
    verification: HarnessReport
    deadline_monotonic: float | None = None


class ReviewerProvider(Protocol):
    name: str
    model: str

    def review(
        self, request: ReviewProviderRequest, tools: RepositoryTools
    ) -> ReviewEnvelope: ...


class ScriptedReviewerProvider:
    name = "scripted-reviewer"
    model = "deterministic-fixture"

    def __init__(self, submission: ReviewerSubmission) -> None:
        self.submission = submission

    @classmethod
    def from_file(cls, path: Path) -> ScriptedReviewerProvider:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return cls(ReviewerSubmission.model_validate(value))
        except (OSError, ValueError, ValidationError) as exc:
            raise ProviderError(f"invalid scripted review file: {exc}") from exc

    def review(self, request: ReviewProviderRequest, tools: RepositoryTools) -> ReviewEnvelope:
        listing = tools.list_files("**/*.py", 200)
        call = AgentToolCall(
            sequence=0,
            name="list_files",
            arguments={"pattern": "**/*.py", "max_results": 200},
            succeeded=True,
            output_bytes=len(json.dumps(listing).encode()),
        )
        return ReviewEnvelope(
            submission=self.submission,
            provider=self.name,
            model=self.model,
            tool_calls=[call],
        )


_SUBMIT_REVIEW = {
    "type": "function",
    "name": "submit_review",
    "description": "Submit only evidence-backed findings. Use an empty findings list if clean.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
                        "category": {
                            "type": "string",
                            "enum": [
                                "correctness",
                                "regression",
                                "security",
                                "api_contract",
                                "error_handling",
                                "maintainability",
                                "test_gap",
                                "environment",
                            ],
                        },
                        "file": {"type": "string"},
                        "line": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                        "symbol": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "claim": {"type": "string"},
                        "evidence": {"type": "string"},
                        "verification": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": [
                        "severity",
                        "category",
                        "file",
                        "line",
                        "symbol",
                        "claim",
                        "evidence",
                        "verification",
                        "confidence",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["summary", "findings"],
        "additionalProperties": False,
    },
}

_REVIEW_TOOLS = [*_READ_TOOLS, _SUBMIT_REVIEW]
_REVIEW_TERMINAL_TOOLS = [_SUBMIT_REVIEW]

_REVIEW_INSTRUCTIONS = """You are PRGuard's Independent Reviewer in a fresh context.
Review the candidate patch against the Issue, patched source, public tests, and deterministic
verification evidence. You do not know or infer Implementer reasoning. Use the bounded text and
Python AST navigation tools; you have no shell or write tool. Report only actionable defects caused
or exposed by the patch. Every finding must name a repository-relative file, the tightest known
line/symbol, concrete evidence, and a reproducible verification condition. Use P0 for catastrophic,
P1 for high-impact, P2 for ordinary blocking correctness/security/regression defects, and P3 for
non-blocking concerns. Do not invent a finding merely because tests fail: link the failure to
source. Before accepting, compare changed public signatures and default behavior with the Base:
an Issue asking for a new capability does not by itself authorize changing existing callers'
defaults. Check whether an opt-in mode or compatibility path is required, and whether tests cover
both legacy defaults and the requested behavior. Treat an unrequested breaking default as a
blocking API-contract or regression finding even when new tests and the existing suite pass.
Call submit_review once; submit an empty findings list when no evidence-backed defect exists.
"""


class DeepSeekReviewerProvider:
    name = "deepseek-reviewer"
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
                raise ProviderError("DeepSeek Reviewer requires DEEPSEEK_API_KEY")
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ProviderError("DeepSeek Reviewer requires the 'agent' dependency") from exc
            client = OpenAI(
                api_key=self._api_key, base_url=self.base_url, timeout=timeout_seconds
            )
        self.client = client

    def review(self, request: ReviewProviderRequest, tools: RepositoryTools) -> ReviewEnvelope:
        verification = request.verification
        public_evidence = {
            "case_id": request.task.case_id,
            "base_commit": request.task.base_commit,
            "issue": request.task.issue,
            "candidate_patch": request.candidate_patch,
            "verification": {
                "outcome": verification.outcome.value,
                "changed_files": verification.changed_files,
                "policy_violations": [
                    item.model_dump(mode="json") for item in verification.policy_violations
                ],
                "commands": [item.model_dump(mode="json") for item in verification.commands],
            },
        }
        messages: list[object] = [
            {"role": "system", "content": _REVIEW_INSTRUCTIONS},
            {"role": "user", "content": json.dumps(public_evidence, ensure_ascii=False)},
        ]
        calls: list[AgentToolCall] = []
        usage = TokenUsage()
        metadata = {
            "api": "chat.completions",
            "base_url": self.base_url,
            "reasoning_effort": self.reasoning_effort,
            "thinking": "enabled",
            "context_scope": "independent-review-v1",
        }
        last_response_id: str | None = None
        terminal_prompt_added = False
        for _turn in range(request.task.max_tool_calls + 2):
            terminal_only = len(calls) >= request.task.max_tool_calls
            if terminal_only:
                metadata["terminal_submission_forced"] = "true"
                metadata["terminal_thinking"] = "disabled"
                if not terminal_prompt_added:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "The read-tool budget is exhausted. Do not request more source. "
                                "Use the evidence already gathered and call submit_review now."
                            ),
                        }
                    )
                    terminal_prompt_added = True
            timeout = None
            if request.deadline_monotonic is not None:
                timeout = max(0.1, request.deadline_monotonic - time.monotonic())
            try:
                response = self.client.chat.completions.create(  # type: ignore[attr-defined]
                    model=self.model,
                    messages=messages,
                    tools=_chat_tools(
                        _REVIEW_TERMINAL_TOOLS if terminal_only else _REVIEW_TOOLS
                    ),
                    **(
                        {
                            "tool_choice": {
                                "type": "function",
                                "function": {"name": "submit_review"},
                            },
                            "extra_body": {"thinking": {"type": "disabled"}},
                        }
                        if terminal_only
                        else {
                            "reasoning_effort": self.reasoning_effort,
                            "extra_body": {"thinking": {"type": "enabled"}},
                        }
                    ),
                    timeout=timeout,
                )
            except Exception as exc:
                raise _safe_error(
                    "DeepSeek Reviewer request failed",
                    exc,
                    secret=self._api_key,
                    provider=self.name,
                    model=self.model,
                    calls=calls,
                    usage=usage,
                    response_id=last_response_id,
                    provider_metadata=metadata,
                ) from exc
            last_response_id = getattr(response, "id", None)
            fingerprint = getattr(response, "system_fingerprint", None)
            if fingerprint:
                metadata["system_fingerprint"] = str(fingerprint)
            api_usage = getattr(response, "usage", None)
            if api_usage is not None:
                usage.input_tokens += int(getattr(api_usage, "prompt_tokens", 0) or 0)
                usage.output_tokens += int(getattr(api_usage, "completion_tokens", 0) or 0)
                details = getattr(api_usage, "prompt_tokens_details", None)
                usage.cached_tokens += int(getattr(details, "cached_tokens", 0) or 0)
            choices = getattr(response, "choices", None) or []
            if not choices:
                raise _failure_error(
                    "DeepSeek Reviewer returned no choices",
                    provider=self.name,
                    model=self.model,
                    calls=calls,
                    usage=usage,
                    response_id=last_response_id,
                    provider_metadata=metadata,
                )
            choice = choices[0]
            message = choice.message
            metadata["finish_reason"] = str(getattr(choice, "finish_reason", "unknown"))
            messages.append(message)
            tool_calls = getattr(message, "tool_calls", None) or []
            if not tool_calls:
                raise _failure_error(
                    "Reviewer ended without submitting a review",
                    provider=self.name,
                    model=self.model,
                    calls=calls,
                    usage=usage,
                    response_id=last_response_id,
                    provider_metadata=metadata,
                )
            for item in tool_calls:
                name = item.function.name
                try:
                    if name != "submit_review" and len(calls) >= request.task.max_tool_calls:
                        error = (
                            "Reviewer read-tool budget exhausted; call submit_review "
                            "without requesting more source"
                        )
                        serialized = json.dumps({"error": error}, ensure_ascii=False)
                        calls.append(
                            AgentToolCall(
                                sequence=len(calls),
                                name=name,
                                arguments={},
                                succeeded=False,
                                output_bytes=len(serialized.encode()),
                                error=error,
                            )
                        )
                        metadata["terminal_protocol_violations"] = str(
                            int(metadata.get("terminal_protocol_violations", "0")) + 1
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": item.id,
                                "content": serialized,
                            }
                        )
                        continue
                    arguments = json.loads(item.function.arguments)
                    if name == "submit_review":
                        submission = ReviewerSubmission.model_validate(arguments)
                        calls.append(
                            AgentToolCall(
                                sequence=len(calls),
                                name=name,
                                arguments={"finding_count": len(submission.findings)},
                                succeeded=True,
                                output_bytes=0,
                            )
                        )
                        return ReviewEnvelope(
                            submission=submission,
                            provider=self.name,
                            model=self.model,
                            response_id=last_response_id,
                            provider_metadata=metadata,
                            token_usage=usage,
                            tool_calls=calls,
                        )
                    result = _call_read_tool(name, arguments, tools)
                    calls.append(
                        AgentToolCall(
                            sequence=len(calls),
                            name=name,
                            arguments=arguments,
                            succeeded=True,
                            output_bytes=0,
                        )
                    )
                    serialized = _serialize_tool_result(
                        result,
                        used=len(calls),
                        budget=request.task.max_tool_calls,
                    )
                    calls[-1].output_bytes = len(serialized.encode())
                except ProviderError as exc:
                    if exc.evidence is not None:
                        raise
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
        terminal_error = (
            "Reviewer terminal submission budget exhausted"
            if terminal_prompt_added
            else "Reviewer response-turn budget exhausted"
        )
        raise _failure_error(
            terminal_error,
            provider=self.name,
            model=self.model,
            calls=calls,
            usage=usage,
            response_id=last_response_id,
            provider_metadata=metadata,
        )
