import json

from prguard.schemas import FixTask, IssueToPRTask, ReviewRepairTask, Task


def test_serialized_agent_context_cannot_contain_benchmark_answers() -> None:
    schema = Task.model_json_schema()
    fields = set(schema["properties"])
    forbidden = {"gold_patch", "hidden_tests", "defects", "is_valid_patch", "labels"}
    assert fields.isdisjoint(forbidden)

    task = Task(
        case_id="context-contract",
        repository="/tmp/repo",
        base_commit="a" * 40,
        issue="Public issue only.",
    )
    serialized = json.dumps(task.public_context())
    assert all(field not in serialized for field in forbidden)


def test_fix_task_contract_excludes_evaluator_answers() -> None:
    fields = set(FixTask.model_json_schema()["properties"])
    forbidden = {"gold_patch", "hidden_tests", "defects", "is_valid_patch", "labels"}
    assert fields.isdisjoint(forbidden)


def test_review_repair_contract_excludes_evaluator_answers() -> None:
    fields = set(ReviewRepairTask.model_json_schema()["properties"])
    forbidden = {
        "gold_patch",
        "hidden_tests",
        "defects",
        "is_valid_patch",
        "labels",
        "reviewer_reasoning",
        "implementer_reasoning",
    }
    assert fields.isdisjoint(forbidden)


def test_issue_to_pr_contract_excludes_evaluator_answers() -> None:
    fields = set(IssueToPRTask.model_json_schema()["properties"])
    forbidden = {
        "gold_patch",
        "hidden_tests",
        "defects",
        "is_valid_patch",
        "labels",
        "reviewer_reasoning",
        "implementer_reasoning",
    }
    assert fields.isdisjoint(forbidden)
