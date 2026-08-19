from pathlib import Path

from prguard.harness.policy import (
    protected_path_violations,
    snapshot_changes,
    snapshot_tree,
)


def test_protected_glob_matches_changed_file(tmp_path: Path) -> None:
    changed = ["src/app.py", "tests/hidden/test_secret.py"]
    violations = protected_path_violations(tmp_path, changed, ["tests/hidden/**"])
    assert violations[0].code == "protected_path_modified"
    assert violations[0].paths == ["tests/hidden/test_secret.py"]


def test_snapshot_reports_create_modify_delete(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    deleted = tmp_path / "deleted.txt"
    first.write_text("one", encoding="utf-8")
    deleted.write_text("gone", encoding="utf-8")
    before = snapshot_tree(tmp_path)
    first.write_text("two", encoding="utf-8")
    deleted.unlink()
    (tmp_path / "new.txt").write_text("new", encoding="utf-8")
    after = snapshot_tree(tmp_path)
    assert snapshot_changes(before, after) == ["deleted.txt", "first.txt", "new.txt"]
