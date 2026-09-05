import hashlib
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
    ReplaceLinesEdit,
    ReplacePythonSymbolEdit,
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


def test_hash_guarded_line_edit_disambiguates_repeated_text(tmp_path: Path) -> None:
    source = tmp_path / "src" / "values.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\nVALUE = 1\n", encoding="utf-8")
    selected = "VALUE = 1\n"
    edit = ReplaceLinesEdit(
        operation="replace_lines",
        path="src/values.py",
        start_line=2,
        end_line=2,
        expected_sha256=hashlib.sha256(selected.encode()).hexdigest(),
        new_text="VALUE = 2\n",
    )

    changed = apply_structured_edits(tmp_path, _task(tmp_path), [edit])

    assert changed == ["src/values.py"]
    assert source.read_text(encoding="utf-8") == "VALUE = 1\nVALUE = 2\n"


def test_hash_guarded_line_edit_rejects_stale_source(tmp_path: Path) -> None:
    source = tmp_path / "src" / "values.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\n", encoding="utf-8")
    edit = ReplaceLinesEdit(
        operation="replace_lines",
        path="src/values.py",
        start_line=1,
        end_line=1,
        expected_sha256="0" * 64,
        new_text="VALUE = 2\n",
    )

    with pytest.raises(PatchPolicyError, match="content hash changed"):
        apply_structured_edits(tmp_path, _task(tmp_path), [edit])

    assert source.read_text(encoding="utf-8") == "VALUE = 1\n"


def test_python_symbol_edit_selects_one_repeated_method_body(tmp_path: Path) -> None:
    source = tmp_path / "src" / "values.py"
    source.parent.mkdir()
    content = (
        "class First:\n"
        "    def value(self):\n"
        "        return 1\n\n"
        "class Second:\n"
        "    def value(self):\n"
        "        return 1\n"
    )
    source.write_text(content, encoding="utf-8")
    selected = "    def value(self):\n        return 1\n"
    edit = ReplacePythonSymbolEdit(
        operation="replace_python_symbol",
        path="src/values.py",
        symbol="Second.value",
        expected_sha256=hashlib.sha256(selected.encode()).hexdigest(),
        new_text="    def value(self):\n        return 2\n",
    )

    apply_structured_edits(tmp_path, _task(tmp_path), [edit])

    updated = source.read_text(encoding="utf-8")
    assert "class First:\n    def value(self):\n        return 1" in updated
    assert "class Second:\n    def value(self):\n        return 2" in updated


def test_python_symbol_edit_rejects_invalid_result(tmp_path: Path) -> None:
    source = tmp_path / "src" / "values.py"
    source.parent.mkdir()
    selected = "def value():\n    return 1\n"
    source.write_text(selected, encoding="utf-8")
    edit = ReplacePythonSymbolEdit(
        operation="replace_python_symbol",
        path="src/values.py",
        symbol="value",
        expected_sha256=hashlib.sha256(selected.encode()).hexdigest(),
        new_text="def value(:\n",
    )

    with pytest.raises(PatchPolicyError, match="invalid Python syntax"):
        apply_structured_edits(tmp_path, _task(tmp_path), [edit])

    assert source.read_text(encoding="utf-8") == selected


@pytest.mark.parametrize("path", ["tests/hidden/test_secret.py", "docs/readme.md"])
def test_structured_edits_enforce_protected_and_writable_scopes(tmp_path: Path, path: str) -> None:
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
