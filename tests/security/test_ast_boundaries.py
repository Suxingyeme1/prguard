from pathlib import Path

import pytest

from prguard.implementer.errors import RepositoryAccessError
from prguard.implementer.tools import RepositoryTools
from prguard.schemas import CommandSpec, FixTask


def _task(repository: Path, **overrides: object) -> FixTask:
    values: dict[str, object] = {
        "case_id": "ast-security",
        "repository": repository,
        "base_commit": "a" * 40,
        "issue": "Inspect safely.",
        "commands": [CommandSpec(argv=["pytest", "-q"], kind="pytest")],
        "allowed_commands": [["pytest", "-q"]],
        "writable_paths": ["src/**"],
    }
    values.update(overrides)
    return FixTask.model_validate(values)


@pytest.mark.security
def test_ast_index_does_not_follow_python_symlink_outside_repository(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("def leaked_credential():\n    return 'secret'\n")
    (repository / "leak.py").symlink_to(outside)

    result = RepositoryTools(repository, _task(repository)).find_symbols(
        "leaked_credential", 20
    )

    assert result["symbols"] == []
    assert result["index"]["indexed_files"] == 0


@pytest.mark.security
def test_ast_results_share_the_repository_context_budget(tmp_path: Path) -> None:
    source = "\n".join(
        f"def sensitive_function_{index:03d}_with_long_name():\n    return {index}\n"
        for index in range(100)
    )
    (tmp_path / "module.py").write_text(source)
    tools = RepositoryTools(tmp_path, _task(tmp_path, max_context_bytes=4096))

    with pytest.raises(RepositoryAccessError, match="context byte budget"):
        tools.find_symbols("sensitive_function", 200)


@pytest.mark.security
def test_ast_index_skips_files_over_per_file_read_limit(tmp_path: Path) -> None:
    (tmp_path / "large.py").write_text(
        "def should_not_be_indexed():\n    return '" + "x" * 5000 + "'\n"
    )
    task = _task(tmp_path, max_file_bytes=4096)

    result = RepositoryTools(tmp_path, task).find_symbols("should_not_be_indexed", 20)

    assert result["symbols"] == []
    assert result["index"]["skipped_large_files"] == 1
