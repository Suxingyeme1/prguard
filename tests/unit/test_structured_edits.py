from pathlib import Path

import pytest
from pydantic import ValidationError

from prguard.implementer.edits import apply_structured_edits
from prguard.implementer.errors import PatchPolicyError
from prguard.schemas import (
    CommandSpec,
    CreateFileEdit,
    FixTask,
    ImplementerProposal,
    ReplaceTextEdit,
)


def _task(repository: Path, **overrides: object) -> FixTask:
    values: dict[str, object] = {
        "case_id": "structured-edits",
        "repository": repository,
        "base_commit": "a" * 40,
        "issue": "Correct behavior.",
        "commands": [CommandSpec(argv=["pytest", "-q"], kind="pytest")],
        "allowed_commands": [["pytest", "-q"]],
        "writable_paths": ["src/**", "tests/**"],
        "protected_paths": ["tests/hidden/**"],
    }
    values.update(overrides)
    return FixTask.model_validate(values)


def test_structured_edits_replace_exact_text_and_create_public_test(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "calc.py"
    source.parent.mkdir()
    source.write_text("def add(a, b):\n    return a - b\n")
    edits = [
        ReplaceTextEdit(
            operation="replace_text",
            path="src/calc.py",
            old_text="    return a - b\n",
            new_text="    return a + b\n",
        ),
        CreateFileEdit(
            operation="create_file",
            path="tests/test_calc.py",
            content="from src.calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        ),
    ]

    changed = apply_structured_edits(tmp_path, _task(tmp_path), edits)

    assert changed == ["src/calc.py", "tests/test_calc.py"]
    assert "a + b" in source.read_text()
    assert (tmp_path / "tests" / "test_calc.py").is_file()


def test_structured_replace_rejects_ambiguous_old_text(tmp_path: Path) -> None:
    source = tmp_path / "src" / "values.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\nVALUE = 1\n")
    edit = ReplaceTextEdit(
        operation="replace_text",
        path="src/values.py",
        old_text="VALUE = 1",
        new_text="VALUE = 2",
    )

    with pytest.raises(PatchPolicyError, match="exactly once; found 2"):
        apply_structured_edits(tmp_path, _task(tmp_path), [edit])

    assert source.read_text() == "VALUE = 1\nVALUE = 1\n"


@pytest.mark.parametrize("path", ["tests/hidden/test_secret.py", "docs/readme.md"])
def test_structured_edits_enforce_protected_and_writable_scopes(
    tmp_path: Path, path: str
) -> None:
    edit = CreateFileEdit(operation="create_file", path=path, content="value\n")

    with pytest.raises(PatchPolicyError):
        apply_structured_edits(tmp_path, _task(tmp_path), [edit])


def test_proposal_requires_exactly_one_submission_format() -> None:
    common = {
        "plan": ["Make the exact change"],
        "summary": "Correct behavior.",
        "tests_changed": False,
    }
    edit = {
        "operation": "replace_text",
        "path": "src/app.py",
        "old_text": "VALUE = 1",
        "new_text": "VALUE = 2",
    }

    structured = ImplementerProposal.model_validate(common | {"edits": [edit]})

    assert structured.patch is None
    assert structured.edits[0].operation == "replace_text"
    with pytest.raises(ValidationError, match="exactly one"):
        ImplementerProposal.model_validate(common)
    with pytest.raises(ValidationError, match="exactly one"):
        ImplementerProposal.model_validate(common | {"patch": "diff", "edits": [edit]})
