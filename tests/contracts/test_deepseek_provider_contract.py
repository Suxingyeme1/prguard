import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from prguard.implementer.errors import ProviderError
from prguard.implementer.providers import DeepSeekChatProvider, ProviderRequest
from prguard.implementer.tools import RepositoryTools
from prguard.schemas import FixTask


class FakeChatCompletions:
    def __init__(self, patch: str) -> None:
        self.patch = patch
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        captured = dict(kwargs)
        captured["messages"] = list(kwargs["messages"])  # type: ignore[arg-type]
        self.requests.append(captured)
        if len(self.requests) == 1:
            calls = [
                SimpleNamespace(
                    id="call-list",
                    function=SimpleNamespace(
                        name="list_files",
                        arguments='{"pattern":"**/*.py","max_results":20}',
                    ),
                )
            ]
        else:
            arguments = {
                "plan": ["Inspect source", "Apply minimal fix"],
                "summary": "Use the inspected contract.",
                "patch": self.patch,
                "tests_changed": False,
            }
            calls = [
                SimpleNamespace(
                    id="call-submit",
                    function=SimpleNamespace(
                        name="submit_patch", arguments=json.dumps(arguments)
                    ),
                )
            ]
        message = SimpleNamespace(
            role="assistant",
            content="",
            reasoning_content="bounded reasoning",
            tool_calls=calls,
        )
        usage = SimpleNamespace(
            prompt_tokens=11,
            completion_tokens=7,
            prompt_tokens_details=SimpleNamespace(cached_tokens=3),
        )
        return SimpleNamespace(
            id=f"chat-{len(self.requests)}",
            choices=[SimpleNamespace(message=message, finish_reason="tool_calls")],
            usage=usage,
            system_fingerprint="fp-test",
        )


def test_deepseek_adapter_runs_bounded_chat_tool_loop(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    )
    completions = FakeChatCompletions(patch)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    task = FixTask(
        case_id="deepseek-provider-contract",
        repository=tmp_path,
        base_commit="a" * 40,
        issue="Set VALUE to two.",
        writable_paths=["*.py"],
    )
    provider = DeepSeekChatProvider(client=client, model="test-model")
    envelope = provider.propose(
        ProviderRequest(task=task, attempt=0), RepositoryTools(tmp_path, task)
    )

    assert envelope.proposal.patch == patch
    assert envelope.provider == "deepseek"
    assert envelope.response_id == "chat-2"
    assert [call.name for call in envelope.tool_calls] == ["list_files", "submit_patch"]
    assert envelope.token_usage.input_tokens == 22
    assert envelope.token_usage.output_tokens == 14
    assert envelope.token_usage.cached_tokens == 6
    assert envelope.provider_metadata["system_fingerprint"] == "fp-test"
    first = completions.requests[0]
    assert "tool_choice" not in first
    assert first["extra_body"] == {"thinking": {"type": "enabled"}}
    assert first["reasoning_effort"] == "high"
    function = first["tools"][0]["function"]  # type: ignore[index]
    assert function["name"] == "list_files"
    second_messages = completions.requests[1]["messages"]
    assert second_messages[2].reasoning_content == "bounded reasoning"  # type: ignore[index,union-attr]
    assert second_messages[3]["role"] == "tool"  # type: ignore[index]


def test_deepseek_adapter_requires_environment_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="DEEPSEEK_API_KEY"):
        DeepSeekChatProvider()


def test_deepseek_adapter_rejects_unsupported_reasoning_effort() -> None:
    with pytest.raises(ProviderError, match=r"high.*max"):
        DeepSeekChatProvider(client=object(), reasoning_effort="medium")


@pytest.mark.parametrize(
    "base_url",
    [
        "https://secret@example.com",
        "http://api.deepseek.com",
        "https://api.deepseek.com?key=secret",
    ],
)
def test_deepseek_adapter_rejects_unsafe_base_url(base_url: str) -> None:
    with pytest.raises(ProviderError, match="base URL"):
        DeepSeekChatProvider(client=object(), base_url=base_url)


def test_deepseek_adapter_allows_loopback_http_endpoint() -> None:
    provider = DeepSeekChatProvider(client=object(), base_url="http://127.0.0.1:8000/")
    assert provider.base_url == "http://127.0.0.1:8000"
