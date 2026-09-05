from pathlib import Path

import pytest

from prguard.onboarding.errors import ProjectDiscoveryError
from prguard.onboarding.profile import discover_project_policy


def test_deterministic_python_policy_discovers_pytest_ruff_and_scopes(tmp_path: Path) -> None:
    (tmp_path / "src" / "orders").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\n[tool.ruff]\nline-length = 100\n",
        encoding="utf-8",
    )

    policy = discover_project_policy(tmp_path)

    assert [command.argv for command in policy.commands] == [
        ["pytest", "-q"],
    ]
    assert policy.writable_paths == ["src/**", "tests/**"]
    assert ".github/**" in policy.protected_paths
    assert policy.source == "deterministic_discovery"
    assert any("Ruff configuration" in warning for warning in policy.warnings)


def test_project_config_cannot_remove_fixed_protected_paths(tmp_path: Path) -> None:
    (tmp_path / ".prguard.toml").write_text(
        "version = 1\n"
        "verification_commands = [['pytest', '-q', 'tests']]\n"
        "writable_paths = ['package/**', 'tests/**']\n"
        "protected_paths = ['release/**']\n",
        encoding="utf-8",
    )

    policy = discover_project_policy(tmp_path)

    assert policy.source == "repository_config"
    assert [command.argv for command in policy.commands] == [["pytest", "-q", "tests"]]
    assert set(policy.protected_paths) >= {".github/**", ".prguard.toml", "release/**"}


def test_project_config_cannot_authorize_shell_or_arbitrary_python(tmp_path: Path) -> None:
    (tmp_path / ".prguard.toml").write_text(
        "version = 1\n"
        "verification_commands = [['python', 'setup.py', 'test']]\n"
        "writable_paths = ['src/**']\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectDiscoveryError, match="unsafe verification command"):
        discover_project_policy(tmp_path)


def test_discovery_fails_closed_without_test_command_or_source_scope(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("documentation only", encoding="utf-8")

    with pytest.raises(ProjectDiscoveryError, match="no safe pytest/Ruff"):
        discover_project_policy(tmp_path)


def test_issue_aware_discovery_targets_related_test_and_hatch_vcs_scaffold(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "humanize"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text(
        "from ._version import __version__\nfrom .filesize import naturalsize\n"
    )
    (source / "filesize.py").write_text("def naturalsize(value):\n    return str(value)\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_filesize.py").write_text(
        "import humanize\n\ndef test_size():\n    assert humanize.naturalsize(1) == '1'\n"
    )
    (tests / "test_other.py").write_text("def test_other():\n    assert True\n")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\n"
        "[tool.hatch.build.hooks.vcs]\n"
        "version-file = 'src/humanize/_version.py'\n"
    )

    policy = discover_project_policy(
        tmp_path,
        issue="`naturalsize()` should handle a custom formatter.",
    )

    assert [command.argv for command in policy.commands] == [
        ["pytest", "-q", "tests/test_filesize.py"]
    ]
    assert policy.runtime_files[0].path == "src/humanize/_version.py"
    assert '__version__ = "0.0.0"' in policy.runtime_files[0].content
    assert "version = __version__" in policy.runtime_files[0].content
    assert "src/humanize/_version.py" in policy.protected_paths
    assert any("Issue-related" in warning for warning in policy.warnings)


def test_issue_discovery_indexes_realistic_large_python_module(tmp_path: Path) -> None:
    source = tmp_path / "src" / "package"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("from .large import target\n")
    (source / "large.py").write_text(
        ("# module implementation padding\n" * 4_500) + "\ndef target():\n    return 'fixed'\n"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_large.py").write_text(
        "import package.large\n\ndef test_module():\n    assert package.large\n"
    )
    (tests / "test_target.py").write_text(
        "from package.large import target\n\ndef test_target():\n    assert target()\n"
    )
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n")

    policy = discover_project_policy(tmp_path, issue="`target()` should return fixed.")

    assert (source / "large.py").stat().st_size > 100_000
    assert [command.argv for command in policy.commands] == [
        ["pytest", "-q", "tests/test_target.py"]
    ]
