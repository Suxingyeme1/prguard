from pathlib import Path

import pytest

from prguard.implementer.errors import PatchPolicyError, RepositoryAccessError
from prguard.implementer.tools import RepositoryTools, validate_proposed_patch
from prguard.schemas import CommandSpec, FixTask


def fix_task(repository: Path, **overrides: object) -> FixTask:
    values: dict[str, object] = {
        "case_id": "tools",
        "repository": repository,
        "base_commit": "a" * 40,
        "issue": "Fix it.",
        "commands": [CommandSpec(argv=["pytest", "-q"], kind="pytest")],
        "allowed_commands": [["pytest", "-q"]],
        "writable_paths": ["src/**", "tests/**"],
        "protected_paths": ["tests/hidden/**"],
    }
    values.update(overrides)
    return FixTask.model_validate(values)


def test_list_search_and_bounded_read(tmp_path: Path) -> None:
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def parse(value):\n    return value.strip()\n", encoding="utf-8")
    tools = RepositoryTools(tmp_path, fix_task(tmp_path))
    assert tools.list_files("src/**", 10)["files"] == ["src/service.py"]
    match = tools.search_text("strip", "src/**", 10)["matches"][0]
    assert match["line"] == 2
    assert "2:     return value.strip()" in tools.read_file("src/service.py", 2, 2)["content"]


def test_recursive_glob_also_matches_root_files(tmp_path: Path) -> None:
    (tmp_path / "root.py").write_text("VALUE = 1\n", encoding="utf-8")
    tools = RepositoryTools(tmp_path, fix_task(tmp_path))
    assert tools.list_files("**/*.py", 10)["files"] == ["root.py"]


@pytest.mark.parametrize(
    "path", ["../secret", "/etc/passwd", ".env", ".env.production", "cert.pem"]
)
def test_read_rejects_escape_and_credentials(tmp_path: Path, path: str) -> None:
    tools = RepositoryTools(tmp_path, fix_task(tmp_path))
    with pytest.raises(RepositoryAccessError):
        tools.read_file(path)


def test_read_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-prguard-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "src" / "link.py"
    link.parent.mkdir()
    link.symlink_to(outside)
    try:
        with pytest.raises(RepositoryAccessError):
            RepositoryTools(tmp_path, fix_task(tmp_path)).read_file("src/link.py")
    finally:
        outside.unlink(missing_ok=True)


def test_context_budget_is_enforced(tmp_path: Path) -> None:
    (tmp_path / "large.py").write_text("VALUE = '" + "x" * 5000 + "'\n", encoding="utf-8")
    tools = RepositoryTools(
        tmp_path,
        fix_task(tmp_path, max_context_bytes=4096, max_file_bytes=10_000),
    )
    with pytest.raises(RepositoryAccessError, match="budget"):
        tools.read_file("large.py")


def test_patch_policy_accepts_scoped_text_patch(tmp_path: Path) -> None:
    patch = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n+++ b/src/app.py\n"
        "@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    )
    assert validate_proposed_patch(fix_task(tmp_path), patch) == ["src/app.py"]


@pytest.mark.parametrize(
    "header",
    [
        "diff --git a/tests/hidden/test_app.py b/tests/hidden/test_app.py",
        "diff --git a/docs/readme.md b/docs/readme.md",
        "diff --git a/../escape.py b/../escape.py",
    ],
)
def test_patch_policy_rejects_protected_outside_and_traversal(tmp_path: Path, header: str) -> None:
    patch = f"{header}\n--- a/value\n+++ b/value\n@@ -1 +1 @@\n-a\n+b\n"
    with pytest.raises(PatchPolicyError):
        validate_proposed_patch(fix_task(tmp_path), patch)


def test_patch_policy_rejects_undeclared_traditional_diff(tmp_path: Path) -> None:
    patch = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n+++ b/src/app.py\n"
        "@@ -1 +1 @@\n-a\n+b\n"
        "--- docs/secret.md\n+++ docs/secret.md\n"
        "@@ -1 +1 @@\n-secret\n+exposed\n"
    )
    with pytest.raises(PatchPolicyError, match="not declared"):
        validate_proposed_patch(fix_task(tmp_path), patch)
