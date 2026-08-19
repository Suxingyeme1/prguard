from pathlib import Path
from types import SimpleNamespace

from prguard.implementer.providers import OpenAIResponsesProvider, ProviderRequest
from prguard.implementer.tools import RepositoryTools
from prguard.schemas import FixTask


class FakeResponses:
    def __init__(self, patch: str) -> None:
        self.patch = patch
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.requests.append(kwargs)
        if len(self.requests) == 1:
            output = [
                SimpleNamespace(
                    type="function_call",
                    name="list_files",
                    arguments='{"pattern":"**/*.py","max_results":20}',
                    call_id="call-list",
                )
            ]
        else:
            arguments = {
                "plan": ["Inspect source", "Apply minimal fix"],
                "summary": "Use the inspected contract.",
                "patch": self.patch,
                "tests_changed": False,
            }
            import json

            output = [
                SimpleNamespace(
                    type="function_call",
                    name="submit_patch",
                    arguments=json.dumps(arguments),
                    call_id="call-submit",
                )
            ]
        usage = SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            input_tokens_details=SimpleNamespace(cached_tokens=2),
        )
        return SimpleNamespace(id=f"response-{len(self.requests)}", output=output, usage=usage)


def test_openai_adapter_runs_bounded_read_tool_loop(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    )
    responses = FakeResponses(patch)
    client = SimpleNamespace(responses=responses)
    task = FixTask(
        case_id="provider-contract",
        repository=tmp_path,
        base_commit="a" * 40,
        issue="Set VALUE to two.",
        writable_paths=["*.py"],
    )
    provider = OpenAIResponsesProvider(client=client, model="test-model")
    envelope = provider.propose(
        ProviderRequest(task=task, attempt=0), RepositoryTools(tmp_path, task)
    )
    assert envelope.proposal.patch == patch
    assert [call.name for call in envelope.tool_calls] == ["list_files", "submit_patch"]
    assert envelope.token_usage.input_tokens == 20
    assert responses.requests[0]["store"] is False
    assert responses.requests[0]["tools"]
