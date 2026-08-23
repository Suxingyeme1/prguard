import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from prguard.implementer.errors import ProviderError
from prguard.implementer.providers import OpenAIResponsesProvider, ProviderRequest
from prguard.implementer.tools import RepositoryTools
from prguard.schemas import CommandSpec, FixTask


class FakeResponses:
    def __init__(
        self,
        patch: str,
        *,
        structured: bool = False,
        never_submit: bool = False,
        read_tool_name: str = "list_files",
        read_tool_arguments: str = '{"pattern":"**/*.py","max_results":20}',
    ) -> None:
        self.patch = patch
        self.structured = structured
        self.never_submit = never_submit
        self.read_tool_name = read_tool_name
        self.read_tool_arguments = read_tool_arguments
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.requests.append(kwargs)
        if len(self.requests) == 1 or self.never_submit:
            output = [
                SimpleNamespace(
                    type="function_call",
                    name=self.read_tool_name,
                    arguments=self.read_tool_arguments,
                    call_id="call-read",
                )
            ]
        else:
            if self.structured:
                name = "submit_edits"
                arguments = {
                    "plan": ["Inspect source", "Apply exact replacement"],
                    "summary": "Use a deterministic text edit.",
                    "edits": [
                        {
                            "operation": "replace_text",
                            "path": "app.py",
                            "old_text": "VALUE = 1",
                            "new_text": "VALUE = 2",
                        }
                    ],
                    "tests_changed": False,
                }
            else:
                name = "submit_patch"
                arguments = {
                    "plan": ["Inspect source", "Apply minimal fix"],
                    "summary": "Use the inspected contract.",
                    "patch": self.patch,
                    "tests_changed": False,
                }
            output = [
                SimpleNamespace(
                    type="function_call",
                    name=name,
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
        commands=[CommandSpec(argv=["pytest", "-q"], kind="pytest")],
        allowed_commands=[["pytest", "-q"]],
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
    tool_output = next(
        item
        for item in responses.requests[1]["input"]
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    )
    budget = __import__("json").loads(tool_output["output"])["_prguard_budget"]
    assert budget["read_tool_calls_remaining"] == 23


def test_openai_adapter_accepts_structured_edit_submission(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    responses = FakeResponses("", structured=True)
    client = SimpleNamespace(responses=responses)
    task = FixTask(
        case_id="provider-structured-contract",
        repository=tmp_path,
        base_commit="a" * 40,
        issue="Set VALUE to two.",
        commands=[CommandSpec(argv=["pytest", "-q"], kind="pytest")],
        allowed_commands=[["pytest", "-q"]],
        writable_paths=["*.py"],
    )

    envelope = OpenAIResponsesProvider(client=client, model="test-model").propose(
        ProviderRequest(task=task, attempt=0), RepositoryTools(tmp_path, task)
    )

    assert envelope.proposal.patch is None
    assert envelope.proposal.edits[0].path == "app.py"
    assert envelope.tool_calls[-1].name == "submit_edits"
    names = [tool["name"] for tool in responses.requests[0]["tools"]]
    assert "find_symbols" in names
    assert "find_callees" in names
    assert "trace_call_graph" in names
    assert "submit_edits" in names


def test_openai_adapter_dispatches_bounded_call_graph_tool(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def leaf():\n    return 1\n\ndef entry():\n    return leaf()\n",
        encoding="utf-8",
    )
    responses = FakeResponses(
        "",
        structured=True,
        read_tool_name="trace_call_graph",
        read_tool_arguments=json.dumps(
            {
                "symbol": "app.leaf",
                "direction": "callers",
                "max_depth": 2,
                "max_results": 20,
            }
        ),
    )
    client = SimpleNamespace(responses=responses)
    task = FixTask(
        case_id="provider-call-graph-contract",
        repository=tmp_path,
        base_commit="a" * 40,
        issue="Inspect leaf callers.",
        commands=[CommandSpec(argv=["pytest", "-q"], kind="pytest")],
        allowed_commands=[["pytest", "-q"]],
        writable_paths=["*.py"],
    )

    envelope = OpenAIResponsesProvider(client=client, model="test-model").propose(
        ProviderRequest(task=task, attempt=0), RepositoryTools(tmp_path, task)
    )

    assert [call.name for call in envelope.tool_calls] == [
        "trace_call_graph",
        "submit_edits",
    ]
    output = next(
        item
        for item in responses.requests[1]["input"]
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    )
    graph = json.loads(output["output"])
    assert graph["root_resolution"] == "exact"
    assert graph["edges"][0]["caller"] == "app.entry"
    assert graph["edges"][0]["callee"] == "app.leaf"


def test_openai_budget_failure_preserves_partial_evidence(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    responses = FakeResponses("unused", never_submit=True)
    client = SimpleNamespace(responses=responses)
    task = FixTask(
        case_id="openai-partial-evidence",
        repository=tmp_path,
        base_commit="a" * 40,
        issue="Set VALUE to two.",
        commands=[CommandSpec(argv=["pytest", "-q"], kind="pytest")],
        allowed_commands=[["pytest", "-q"]],
        writable_paths=["*.py"],
        max_tool_calls=1,
    )

    with pytest.raises(ProviderError, match="read-tool budget") as captured:
        OpenAIResponsesProvider(client=client, model="test-model").propose(
            ProviderRequest(task=task, attempt=0), RepositoryTools(tmp_path, task)
        )

    evidence = captured.value.evidence
    assert evidence.provider == "openai"
    assert evidence.response_id == "response-2"
    assert [call.name for call in evidence.tool_calls] == ["list_files"]
    assert evidence.token_usage.input_tokens == 20
    assert evidence.token_usage.output_tokens == 10
