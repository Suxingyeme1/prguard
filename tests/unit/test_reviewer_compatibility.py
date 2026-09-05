from pathlib import Path

from prguard.reviewer.compatibility import analyze_python_compatibility


def _write(root: Path, relative: str, value: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_reports_public_contract_and_protocol_changes_but_ignores_tests(
    tmp_path: Path,
) -> None:
    base = tmp_path / "base"
    candidate = tmp_path / "candidate"
    _write(
        base,
        "src/package/api.py",
        '__all__ = ["Client", "convert"]\n'
        "class Client:\n"
        "    def __exit__(self, exc_type, exc, traceback):\n"
        "        return False\n\n"
        "    def _internal(self):\n"
        "        return 1\n\n"
        "def convert(value: str = 'legacy') -> str:\n"
        "    return value\n\n"
        "def _private() -> int:\n"
        "    return 1\n\n"
        "class _PrivateClient:\n"
        "    def visible_name(self):\n"
        "        return 1\n",
    )
    _write(
        candidate,
        "src/package/api.py",
        '__all__ = ["Client"]\n'
        "class Client:\n"
        "    def __exit__(self, exc_type, exc, traceback):\n"
        "        return True\n\n"
        "    def _internal(self):\n"
        "        return 2\n\n"
        "def convert(value: str = 'new') -> str:\n"
        "    return value\n\n"
        "def _private() -> int:\n"
        "    return 2\n\n"
        "class _PrivateClient:\n"
        "    def visible_name(self):\n"
        "        return 2\n",
    )
    _write(base, "tests/test_api.py", "def public():\n    return 1\n")
    _write(candidate, "tests/test_api.py", "def public():\n    return 2\n")

    signals = analyze_python_compatibility(
        base,
        candidate,
        ["src/package/api.py", "tests/test_api.py"],
        max_file_bytes=10_000,
    )

    assert any("package.api.Client.__exit__" in signal for signal in signals)
    assert any("package.api.convert" in signal and "signature" in signal for signal in signals)
    assert any("__all__ export surface changed" in signal for signal in signals)
    assert all("_private" not in signal for signal in signals)
    assert all("_internal" not in signal for signal in signals)
    assert all("PrivateClient" not in signal for signal in signals)
    assert all("tests.test_api" not in signal for signal in signals)


def test_skips_files_over_the_read_budget(tmp_path: Path) -> None:
    base = tmp_path / "base"
    candidate = tmp_path / "candidate"
    _write(base, "module.py", "VALUE = 1\n")
    _write(candidate, "module.py", "VALUE = 2\n")

    signals = analyze_python_compatibility(
        base,
        candidate,
        ["module.py"],
        max_file_bytes=5,
    )

    assert signals == ["module.py: compatibility analysis skipped because the file is too large"]


def test_reports_public_symbols_removed_with_a_python_module(tmp_path: Path) -> None:
    base = tmp_path / "base"
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    _write(base, "legacy.py", "def public_api(value=1):\n    return value\n")

    signals = analyze_python_compatibility(
        base,
        candidate,
        ["legacy.py"],
        max_file_bytes=10_000,
    )

    assert signals == [
        "legacy.public_api: public callable or class removed; verify backward compatibility"
    ]


def test_bounds_changed_file_count_and_signal_size(tmp_path: Path) -> None:
    base = tmp_path / "base"
    candidate = tmp_path / "candidate"
    changed_files: list[str] = []
    for index in range(51):
        relative = f"module_{index:02d}.py"
        changed_files.append(relative)
        _write(base, relative, "def public(value='old'):\n    return value\n")
        default = repr("x" * 2_500) if index == 0 else repr("new")
        _write(candidate, relative, f"def public(value={default}):\n    return value\n")

    signals = analyze_python_compatibility(
        base,
        candidate,
        changed_files,
        max_file_bytes=10_000,
    )

    assert len(signals) == 50
    assert signals[-1] == "additional compatibility signals omitted"
    assert all(len(signal) <= 2_000 for signal in signals)
    assert any(signal.endswith("...[signal truncated]") for signal in signals)
