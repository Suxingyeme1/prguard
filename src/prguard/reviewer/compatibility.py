"""Bounded Base/Candidate Python compatibility signals for Independent Review."""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path, PurePosixPath

_MAX_FILES = 50
_MAX_SIGNALS = 50
_MAX_SIGNAL_CHARS = 2_000


def _decode_python(path: Path) -> str:
    payload = path.read_bytes()
    encoding, _ = tokenize.detect_encoding(io.BytesIO(payload).readline)
    return payload.decode(encoding)


def _module_name(relative: str) -> str:
    parts = list(PurePosixPath(relative).with_suffix("").parts)
    if parts and parts[0] in {"src", "lib"}:
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or relative


def _is_test_path(relative: str) -> bool:
    path = PurePosixPath(relative)
    return (
        any(part in {"test", "tests"} for part in path.parts[:-1])
        or path.name.startswith("test_")
        or path.name.endswith("_test.py")
    )


def _is_public_callable(name: str, parents: tuple[str, ...]) -> bool:
    if not parents:
        return not name.startswith("_")
    return not name.startswith("_") or _is_special_method(name)


def _is_special_method(name: str) -> bool:
    return len(name) > 4 and name.startswith("__") and name.endswith("__")


def _truncate_signal(value: str) -> str:
    if len(value) <= _MAX_SIGNAL_CHARS:
        return value
    suffix = "...[signal truncated]"
    return f"{value[: _MAX_SIGNAL_CHARS - len(suffix)]}{suffix}"


def _callable_state(tree: ast.Module, module: str) -> dict[str, tuple[str, str]]:
    values: dict[str, tuple[str, str]] = {}

    def walk(body: list[ast.stmt], parents: tuple[str, ...]) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                if node.name.startswith("_"):
                    continue
                symbol = ".".join((module, *parents, node.name))
                bases = repr(
                    (
                        [ast.dump(item, include_attributes=False) for item in node.bases],
                        [ast.dump(item, include_attributes=False) for item in node.keywords],
                    )
                )
                values[symbol] = (
                    f"class-bases:{bases}",
                    f"class-bases:{bases}",
                )
                walk(node.body, (*parents, node.name))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not _is_public_callable(node.name, parents):
                    continue
                symbol = ".".join((module, *parents, node.name))
                kind = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                returns = ast.unparse(node.returns) if node.returns is not None else ""
                signature = f"{kind}({ast.unparse(node.args)}) -> {returns}"
                values[symbol] = (signature, ast.dump(node, include_attributes=False))

    walk(tree.body, ())
    return values


def _exports(tree: ast.Module) -> tuple[str, ...] | None:
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            continue
        value = node.value
        if not isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            return None
        strings = [
            item.value
            for item in value.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        ]
        return tuple(sorted(strings)) if len(strings) == len(value.elts) else None
    return None


def analyze_python_compatibility(
    base_root: Path,
    candidate_root: Path,
    changed_files: list[str],
    *,
    max_file_bytes: int,
) -> list[str]:
    """Return bounded review prompts; never classify a compatibility defect automatically."""

    signals: list[str] = []
    python_paths = sorted(
        path
        for path in changed_files
        if path.endswith(".py") and not _is_test_path(path)
    )
    files_omitted = len(python_paths) > _MAX_FILES
    for relative in python_paths[:_MAX_FILES]:
        base_path = base_root / relative
        candidate_path = candidate_root / relative
        existing = [path for path in (base_path, candidate_path) if path.is_file()]
        if not existing:
            continue
        if any(path.is_symlink() for path in existing):
            continue
        if max(path.stat().st_size for path in existing) > max_file_bytes:
            signals.append(
                f"{relative}: compatibility analysis skipped because the file is too large"
            )
            continue
        try:
            base_tree = (
                ast.parse(_decode_python(base_path), filename=relative)
                if base_path.is_file()
                else ast.Module(body=[], type_ignores=[])
            )
            candidate_tree = (
                ast.parse(_decode_python(candidate_path), filename=relative)
                if candidate_path.is_file()
                else ast.Module(body=[], type_ignores=[])
            )
        except (OSError, SyntaxError, UnicodeError, ValueError):
            signals.append(
                f"{relative}: compatibility analysis skipped because Python parsing failed"
            )
            continue
        module = _module_name(relative)
        before = _callable_state(base_tree, module)
        after = _callable_state(candidate_tree, module)
        for symbol in sorted(before.keys() | after.keys()):
            old = before.get(symbol)
            new = after.get(symbol)
            if old is None:
                signals.append(
                    f"{symbol}: public callable or class added; verify the intended API surface"
                )
            elif new is None:
                signals.append(
                    f"{symbol}: public callable or class removed; verify backward compatibility"
                )
            elif old[0] != new[0]:
                signals.append(
                    f"{symbol}: public signature or class bases changed from {old[0]} to {new[0]}"
                )
            elif old[1] != new[1]:
                detail = (
                    "Python protocol behavior changed; verify legacy default semantics"
                    if _is_special_method(symbol.rsplit(".", 1)[-1])
                    else "public implementation changed; verify existing callers and defaults"
                )
                signals.append(f"{symbol}: {detail}")
        old_exports = _exports(base_tree)
        new_exports = _exports(candidate_tree)
        if old_exports != new_exports and (old_exports is not None or new_exports is not None):
            signals.append(
                f"{relative}: __all__ export surface changed; verify public API compatibility"
            )
        if len(signals) >= _MAX_SIGNALS:
            bounded = signals[: _MAX_SIGNALS - 1]
            bounded.append("additional compatibility signals omitted")
            return [_truncate_signal(signal) for signal in bounded]
    if files_omitted:
        signals.append("additional changed Python files omitted from compatibility analysis")
    return [_truncate_signal(signal) for signal in signals]
