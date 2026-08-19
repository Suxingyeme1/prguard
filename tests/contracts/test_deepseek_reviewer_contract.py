import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from prguard.implementer.tools import RepositoryTools
from prguard.reviewer.providers import DeepSeekReviewerProvider, ReviewProviderRequest
from prguard.schemas import (
    HarnessReport,
    PatchApplicationResult,
    ReviewTask,
    RunOutcome,
)


class FakeReviewerCompletions:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        captured = dict(kwargs)
        captured["messages"] = list(kwargs["messages"])  # type: ignore[arg-type]
        self.requests.append(captured)
        if len(self.requests) == 1:
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
        ReviewProviderRequest(task=task, candidate_patch=patch, verification=verification),
        RepositoryTools(tmp_path, task),
    )

    assert envelope.submission.findings[0].file == "service.py"
    assert [call.name for call in envelope.tool_calls] == ["read_file", "submit_review"]
    assert envelope.token_usage.input_tokens == 20
    assert envelope.provider_metadata["context_scope"] == "independent-review-v1"
    first_messages = completions.requests[0]["messages"]
    public_payload = json.loads(first_messages[1]["content"])
    serialized = json.dumps(public_payload)
    assert "implementer" not in serialized.casefold()
    assert "gold_patch" not in serialized.casefold()
    assert "hidden" not in serialized.casefold()
    assert "tool_choice" not in completions.requests[0]
