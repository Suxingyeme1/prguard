import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from prguard.implementer.errors import ProviderError
from prguard.implementer.tools import RepositoryTools
from prguard.reviewer.providers import DeepSeekReviewerProvider, ReviewProviderRequest
from prguard.schemas import (
    HarnessReport,
    PatchApplicationResult,
    ReviewTask,
    RunOutcome,
)


class FakeReviewerCompletions:
    def __init__(self, *, never_submit: bool = False) -> None:
        self.never_submit = never_submit
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        captured = dict(kwargs)
        captured["messages"] = list(kwargs["messages"])  # type: ignore[arg-type]
        self.requests.append(captured)
        if len(self.requests) == 1 or self.never_submit:
            name = "read_file"
            arguments = '{"path":"service.py","start_line":1,"end_line":100}'
        else:
            name = "submit_review"
            arguments = json.dumps(
                {
                    "summary": "The patch regresses normalization.",
                    "findings": [
                        {
                            "severity": "P1",
                            "category": "regression",
                            "file": "service.py",
                            "line": 2,
                            "symbol": "normalize",
                            "claim": "Lowercasing was removed.",
                            "evidence": "The changed return only strips whitespace.",
                            "verification": "Run the normalization regression test.",
                            "confidence": 0.98,
                        }
                    ],
                }
            )
        message = SimpleNamespace(
            role="assistant",
            content="",
            reasoning_content="private",
            tool_calls=[
                SimpleNamespace(
                    id=f"call-{len(self.requests)}",
                    function=SimpleNamespace(name=name, arguments=arguments),
                )
            ],
        )
        usage = SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            prompt_tokens_details=SimpleNamespace(cached_tokens=2),
        )
        return SimpleNamespace(
            id=f"review-{len(self.requests)}",
            choices=[SimpleNamespace(message=message, finish_reason="tool_calls")],
            usage=usage,
            system_fingerprint="fp-review",
        )


def test_deepseek_reviewer_has_independent_bounded_context(tmp_path: Path) -> None:
    (tmp_path / "service.py").write_text(
        "def normalize(value: str) -> str:\n    return value.strip()\n", encoding="utf-8"
    )
    patch = (
        "diff --git a/service.py b/service.py\n--- a/service.py\n+++ b/service.py\n"
        "@@ -1,2 +1,2 @@\n def normalize(value: str) -> str:\n"
        "-    return value.strip().lower()\n+    return value.strip()\n"
    )
    task = ReviewTask(
        case_id="review-provider-contract",
        repository=tmp_path,
        base_commit="a" * 40,
        issue="Preserve lowercase normalization.",
        candidate_patch=tmp_path / "candidate.patch",
    )
    now = datetime.now(UTC)
    verification = HarnessReport(
        run_id="verification",
        case_id=task.case_id,
        resolved_base_commit=task.base_commit,
        outcome=RunOutcome.FAILED_VERIFICATION,
        started_at=now,
        finished_at=now,
        duration_seconds=0,
        patch=PatchApplicationResult(attempted=True, applied=True),
    )
    completions = FakeReviewerCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    envelope = DeepSeekReviewerProvider(client=client, model="test-model").review(
        ReviewProviderRequest(
            task=task,
            candidate_patch=patch,
            verification=verification,
            compatibility_signals=("service.normalize: public implementation changed",),
        ),
        RepositoryTools(tmp_path, task),
    )

    assert envelope.submission.findings[0].file == "service.py"
    assert [call.name for call in envelope.tool_calls] == ["read_file", "submit_review"]
    assert envelope.token_usage.input_tokens == 20
    assert envelope.provider_metadata["context_scope"] == "independent-review-v1"
    first_messages = completions.requests[0]["messages"]
    assert "compare changed public signatures and default behavior" in first_messages[0][
        "content"
    ]
    assert "identify the violated invariant" in first_messages[0]["content"]
    assert "only hides the observed crash" in first_messages[0]["content"]
    public_payload = json.loads(first_messages[1]["content"])
    serialized = json.dumps(public_payload)
    assert "implementer" not in serialized.casefold()
    assert "gold_patch" not in serialized.casefold()
    assert "hidden" not in serialized.casefold()
    assert public_payload["compatibility_signals"] == [
        "service.normalize: public implementation changed"
    ]
    assert "tool_choice" not in completions.requests[0]
    tool_names = [
        item["function"]["name"] for item in completions.requests[0]["tools"]
    ]
    assert "find_symbols" in tool_names
    assert "find_callers" in tool_names
    assert "trace_call_graph" in tool_names
    assert "submit_review" in tool_names
    assert "submit_edits" not in tool_names
    assert "submit_patch" not in tool_names
    budget = json.loads(completions.requests[1]["messages"][-1]["content"])[
        "_prguard_budget"
    ]
    assert budget["read_tool_calls_remaining"] == 11


def test_reviewer_budget_failure_preserves_partial_evidence(tmp_path: Path) -> None:
    (tmp_path / "service.py").write_text("VALUE = 1\n", encoding="utf-8")
    task = ReviewTask(
        case_id="reviewer-partial-evidence",
        repository=tmp_path,
        base_commit="a" * 40,
        issue="Review the candidate.",
        candidate_patch=tmp_path / "candidate.patch",
        max_tool_calls=1,
    )
    now = datetime.now(UTC)
    verification = HarnessReport(
        run_id="verification",
        case_id=task.case_id,
        resolved_base_commit=task.base_commit,
        outcome=RunOutcome.PASSED,
        started_at=now,
        finished_at=now,
        duration_seconds=0,
        patch=PatchApplicationResult(attempted=True, applied=True),
    )
    completions = FakeReviewerCompletions(never_submit=True)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    with pytest.raises(ProviderError, match="terminal submission budget") as captured:
        DeepSeekReviewerProvider(client=client, model="test-model").review(
            ReviewProviderRequest(
                task=task,
                candidate_patch="candidate",
                verification=verification,
            ),
            RepositoryTools(tmp_path, task),
        )

    evidence = captured.value.evidence
    assert evidence.provider == "deepseek-reviewer"
    assert [call.name for call in evidence.tool_calls] == [
        "read_file",
        "read_file",
        "read_file",
    ]
    assert evidence.tool_calls[1].succeeded is False
    assert evidence.tool_calls[2].succeeded is False
    assert evidence.token_usage.input_tokens == 30
    assert evidence.provider_metadata["context_scope"] == "independent-review-v1"
    assert evidence.provider_metadata["terminal_submission_forced"] == "true"
    assert evidence.provider_metadata["terminal_protocol_violations"] == "2"
    terminal_tool_names = [
        item["function"]["name"] for item in completions.requests[1]["tools"]
    ]
    assert terminal_tool_names == ["submit_review"]
    assert completions.requests[1]["tool_choice"] == {
        "type": "function",
        "function": {"name": "submit_review"},
    }
    assert completions.requests[1]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in completions.requests[1]
    assert "read-tool budget is exhausted" in completions.requests[1]["messages"][-1][
        "content"
    ]


def test_reviewer_gets_terminal_submission_turn_after_final_read(tmp_path: Path) -> None:
    (tmp_path / "service.py").write_text("VALUE = 1\n", encoding="utf-8")
    task = ReviewTask(
        case_id="reviewer-terminal-turn",
        repository=tmp_path,
        base_commit="a" * 40,
        issue="Review the candidate.",
        candidate_patch=tmp_path / "candidate.patch",
        max_tool_calls=1,
    )
    now = datetime.now(UTC)
    verification = HarnessReport(
        run_id="verification",
        case_id=task.case_id,
        resolved_base_commit=task.base_commit,
        outcome=RunOutcome.PASSED,
        started_at=now,
        finished_at=now,
        duration_seconds=0,
        patch=PatchApplicationResult(attempted=True, applied=True),
    )
    completions = FakeReviewerCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    envelope = DeepSeekReviewerProvider(client=client, model="test-model").review(
        ReviewProviderRequest(
            task=task,
            candidate_patch="candidate",
            verification=verification,
        ),
        RepositoryTools(tmp_path, task),
    )

    assert [call.name for call in envelope.tool_calls] == ["read_file", "submit_review"]
    assert envelope.provider_metadata["terminal_submission_forced"] == "true"
    terminal_tool_names = [
        item["function"]["name"] for item in completions.requests[1]["tools"]
    ]
    assert terminal_tool_names == ["submit_review"]
    assert completions.requests[1]["tool_choice"] == {
        "type": "function",
        "function": {"name": "submit_review"},
    }
    assert completions.requests[1]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in completions.requests[1]
