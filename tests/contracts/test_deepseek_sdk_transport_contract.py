import json
from pathlib import Path

import pytest

from prguard.implementer.providers import DeepSeekChatProvider, ProviderRequest
from prguard.implementer.tools import RepositoryTools
from prguard.schemas import FixTask

httpx = pytest.importorskip("httpx")
openai = pytest.importorskip("openai")


def test_deepseek_contract_round_trips_through_openai_sdk(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    )
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            name = "list_files"
            arguments = '{"pattern":"**/*.py","max_results":20}'
        else:
            name = "submit_patch"
            arguments = json.dumps(
                {
                    "plan": ["Inspect source", "Apply minimal fix"],
                    "summary": "Use the inspected contract.",
                    "patch": patch,
                    "tests_changed": False,
                }
            )
        return httpx.Response(
            200,
            json={
                "id": f"chat-{len(requests)}",
                "object": "chat.completion",
                "created": 1,
                "model": "test-model",
                "system_fingerprint": "fp-transport",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "private reasoning",
                            "tool_calls": [
                                {
                                    "id": f"call-{len(requests)}",
                                    "type": "function",
                                    "function": {"name": name, "arguments": arguments},
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                        "logprobs": None,
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "prompt_tokens_details": {"cached_tokens": 2},
                },
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = openai.OpenAI(
        api_key="test-only-key",
        base_url="https://api.deepseek.test",
        http_client=http_client,
    )
    task = FixTask(
        case_id="deepseek-sdk-contract",
        repository=tmp_path,
        base_commit="a" * 40,
        issue="Set VALUE to two.",
        writable_paths=["*.py"],
    )
    try:
        envelope = DeepSeekChatProvider(
            client=client, model="test-model", base_url="https://api.deepseek.test"
        ).propose(ProviderRequest(task=task, attempt=0), RepositoryTools(tmp_path, task))
    finally:
        client.close()

    assert envelope.proposal.patch == patch
    assert envelope.provider_metadata["system_fingerprint"] == "fp-transport"
    assert requests[1]["messages"][2]["reasoning_content"] == "private reasoning"  # type: ignore[index]
    assert requests[1]["messages"][3]["role"] == "tool"  # type: ignore[index]
