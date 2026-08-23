"""Bounded Python AST index for repository-level agent navigation.

The index deliberately reports lexical/static relationships. Python reflection,
runtime monkey-patching, dependency injection, and dynamically constructed names
cannot be represented as a complete call graph without executing repository code.
"""

from __future__ import annotations

import ast
import builtins
from collections import deque
from dataclasses import dataclass, field
from pathlib import PurePosixPath


def _module_name(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[0] in {"src", "lib", "test", "tests"}:
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def _parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    arguments = node.args
    values = [*arguments.posonlyargs, *arguments.args]
    names = [item.arg for item in values]
    if arguments.vararg is not None:
        names.append(f"*{arguments.vararg.arg}")
    names.extend(item.arg for item in arguments.kwonlyargs)
    if arguments.kwarg is not None:
        names.append(f"**{arguments.kwarg.arg}")
    return names


@dataclass(frozen=True)
class PythonSource:
    path: str
    content: str


@dataclass
class _ModuleRecord:
    path: str
    module: str
    imports: list[dict[str, object]] = field(default_factory=list)
    symbols: list[dict[str, object]] = field(default_factory=list)
    calls: list[dict[str, object]] = field(default_factory=list)
    references: list[dict[str, object]] = field(default_factory=list)


class _ModuleVisitor(ast.NodeVisitor):
    def __init__(
        self, record: _ModuleRecord, module_definitions: dict[str, str]
    ) -> None:
        self.record = record
        self.parents: list[str] = []
        self.kinds: list[str] = []
        self.aliases: dict[str, str] = {}
        self.module_definitions = module_definitions

    @property
    def current_symbol(self) -> str | None:
        if not self.parents:
            return None
        return ".".join(filter(None, [self.record.module, *self.parents]))

    @property
    def current_class(self) -> str | None:
        for index in range(len(self.kinds) - 1, -1, -1):
            if self.kinds[index] == "class":
                return ".".join(
                    filter(None, [self.record.module, *self.parents[: index + 1]])
                )
        return None

    def _qualify(self, name: str) -> str:
        return ".".join(filter(None, [self.record.module, *self.parents, name]))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            binding = alias.asname or alias.name.split(".")[0]
            target = alias.name if alias.asname else binding
            self.aliases[binding] = target
            self.record.imports.append(
                {
                    "path": self.record.path,
                    "line": node.lineno,
                    "module": alias.name,
                    "name": None,
                    "alias": alias.asname,
                    "binding": binding,
                    "target": target,
                    "scope": self.current_symbol,
                }
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = self._resolve_import_module(node.module, node.level)
        for alias in node.names:
            binding = alias.asname or alias.name
            target = f"{module}.{alias.name}" if module else alias.name
            if alias.name != "*":
                self.aliases[binding] = target
            self.record.imports.append(
                {
                    "path": self.record.path,
                    "line": node.lineno,
                    "module": module,
                    "name": alias.name,
                    "alias": alias.asname,
                    "binding": binding,
                    "target": target,
                    "scope": self.current_symbol,
                }
            )

    def _resolve_import_module(self, module: str | None, level: int) -> str:
        if level == 0:
            return module or ""
        current = self.record.module.split(".") if self.record.module else []
        if PurePosixPath(self.record.path).name != "__init__.py":
            current = current[:-1]
        parents_to_remove = max(0, level - 1)
        if parents_to_remove:
            current = current[:-parents_to_remove]
        return ".".join([*current, *(module or "").split(".")]).strip(".")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualified_name = self._qualify(node.name)
        self.record.symbols.append(
            {
                "name": node.name,
                "qualified_name": qualified_name,
                "kind": "class",
                "path": self.record.path,
                "line": node.lineno,
                "end_line": node.end_lineno or node.lineno,
                "parent": self.current_symbol,
                "parameters": [],
                "decorators": [
                    name
                    for item in node.decorator_list
                    if (name := _dotted_name(item)) is not None
                ],
            }
        )
        self.parents.append(node.name)
        self.kinds.append("class")
        self.generic_visit(node)
        self.kinds.pop()
        self.parents.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, asynchronous=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, asynchronous=True)

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, asynchronous: bool
    ) -> None:
        in_class = bool(self.kinds and self.kinds[-1] == "class")
        kind = "async_method" if asynchronous and in_class else "async_function"
        if not asynchronous:
            kind = "method" if in_class else "function"
        self.record.symbols.append(
            {
                "name": node.name,
                "qualified_name": self._qualify(node.name),
                "kind": kind,
                "path": self.record.path,
                "line": node.lineno,
                "end_line": node.end_lineno or node.lineno,
                "parent": self.current_symbol,
                "parameters": _parameters(node),
                "decorators": [
                    name
                    for item in node.decorator_list
                    if (name := _dotted_name(item)) is not None
                ],
            }
        )
        self.parents.append(node.name)
        self.kinds.append(kind)
        self.generic_visit(node)
        self.kinds.pop()
        self.parents.pop()

    def visit_Call(self, node: ast.Call) -> None:
        expression = _dotted_name(node.func)
        if expression is not None:
            target, confidence = self._resolve_expression(expression)
            self.record.calls.append(
                {
                    "path": self.record.path,
                    "line": node.lineno,
                    "caller": self.current_symbol,
                    "expression": expression,
                    "target": target,
                    "resolution": confidence,
                }
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            target, confidence = self._resolve_expression(node.id)
            self.record.references.append(
                {
                    "path": self.record.path,
                    "line": node.lineno,
                    "scope": self.current_symbol,
                    "expression": node.id,
                    "target": target,
                    "resolution": confidence,
                }
            )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load):
            expression = _dotted_name(node)
            if expression is not None:
                target, confidence = self._resolve_expression(expression)
                self.record.references.append(
                    {
                        "path": self.record.path,
                        "line": node.lineno,
                        "scope": self.current_symbol,
                        "expression": expression,
                        "target": target,
                        "resolution": confidence,
                    }
                )
        self.generic_visit(node)

    def _resolve_expression(self, expression: str) -> tuple[str, str]:
        head, separator, tail = expression.partition(".")
        imported = self.aliases.get(head)
        if imported is not None:
            return f"{imported}{separator}{tail}", "import_alias"
        definition = self.module_definitions.get(head)
        if definition is not None:
            return f"{definition}{separator}{tail}", "module_definition"
        if head in vars(builtins):
            return f"builtins.{expression}", "builtin"
        if head in {"self", "cls"} and self.current_class is not None and tail:
            return f"{self.current_class}.{tail}", "class_lexical"
        if "." not in expression and self.record.module:
            return f"{self.record.module}.{expression}", "module_lexical"
        return expression, "unresolved_lexical"


class PythonAstIndex:
    """Immutable static index built only from caller-approved Python source text."""

    def __init__(
        self,
        sources: list[PythonSource],
        *,
        truncated: bool = False,
        skipped_large_files: int = 0,
    ) -> None:
        self.records: list[_ModuleRecord] = []
        self.parse_errors: list[dict[str, object]] = []
        self.truncated = truncated
        self.skipped_large_files = skipped_large_files
        for source in sources:
            module = _module_name(source.path)
            record = _ModuleRecord(path=source.path, module=module)
            try:
                tree = ast.parse(source.content, filename=source.path)
            except (SyntaxError, ValueError) as exc:
                self.parse_errors.append(
                    {
                        "path": source.path,
                        "line": getattr(exc, "lineno", None),
                        "error": type(exc).__name__,
                    }
                )
                continue
            record.symbols.append(
                {
                    "name": module.rsplit(".", 1)[-1] if module else source.path,
                    "qualified_name": module,
                    "kind": "module",
                    "path": source.path,
                    "line": 1,
                    "end_line": len(source.content.splitlines()) or 1,
                    "parent": None,
                    "parameters": [],
                    "decorators": [],
                }
            )
            module_definitions = {
                item.name: ".".join(filter(None, [module, item.name]))
                for item in tree.body
                if isinstance(
                    item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                )
            }
            _ModuleVisitor(record, module_definitions).visit(tree)
            self.records.append(record)
        self._resolve_reexports()

    @staticmethod
    def _rewrite_export_prefix(value: str, exports: dict[str, str]) -> str:
        """Resolve both direct re-exports and members reached through a re-export."""

        matches = [
            alias
            for alias in exports
            if value == alias or value.startswith(f"{alias}.")
        ]
        if not matches:
            return value
        alias = max(matches, key=len)
        return f"{exports[alias]}{value[len(alias):]}"

    def _resolve_reexports(self) -> None:
        exports = {
            f"{record.module}.{item['binding']}": str(item["target"])
            for record in self.records
            for item in record.imports
            if item["scope"] is None and item["binding"] != "*" and record.module
        }
        for _ in range(8):
            changed = False
            for alias, target in list(exports.items()):
                resolved = self._rewrite_export_prefix(target, exports)
                if resolved != target:
                    exports[alias] = resolved
                    changed = True
            if not changed:
                break
        for record in self.records:
            for item in [*record.calls, *record.references]:
                target = str(item["target"])
                resolved = self._rewrite_export_prefix(target, exports)
                if resolved != target:
                    item["target"] = resolved
                    item["resolution"] = f"{item['resolution']}_reexport"

    def metadata(self) -> dict[str, object]:
        return {
            "language": "python",
            "analysis": "bounded_static_ast",
            "indexed_files": len(self.records),
            "parse_error_count": len(self.parse_errors),
            "skipped_large_files": self.skipped_large_files,
            "truncated": self.truncated,
            "limitations": (
                "Direct lexical approximation; runtime dispatch, reflection, monkey-patching, "
                "and generated code are not resolved."
            ),
        }

    def find_symbols(self, query: str, max_results: int) -> dict[str, object]:
        normalized = query.casefold()
        candidates = [
            symbol
            for record in self.records
            for symbol in record.symbols
            if normalized in str(symbol["name"]).casefold()
            or normalized in str(symbol["qualified_name"]).casefold()
        ]
        candidates.sort(
            key=lambda item: (
                0 if str(item["qualified_name"]).casefold() == normalized else 1,
                0 if str(item["name"]).casefold() == normalized else 1,
                str(item["path"]),
                int(item["line"]),
            )
        )
        return {
            "symbols": candidates[:max_results],
            "truncated": len(candidates) > max_results,
            "index": self.metadata(),
        }

    def list_imports(self, path: str, max_results: int) -> dict[str, object]:
        imports = [
            item
            for record in self.records
            if record.path == path
            for item in record.imports
        ]
        imports.sort(key=lambda item: (int(item["line"]), str(item["module"])))
        return {
            "imports": imports[:max_results],
            "truncated": len(imports) > max_results,
            "index": self.metadata(),
        }

    @staticmethod
    def _matches_target(item: dict[str, object], query: str) -> bool:
        normalized = query.casefold()
        leaf = normalized.rsplit(".", 1)[-1]
        expression = str(item["expression"]).casefold()
        target = str(item["target"]).casefold()
        if "." in normalized:
            return (
                target == normalized
                or target.endswith(f".{normalized}")
                or expression == normalized
            )
        return (
            expression.rsplit(".", 1)[-1] == leaf
            or target.rsplit(".", 1)[-1] == leaf
        )

    def find_callers(self, symbol: str, max_results: int) -> dict[str, object]:
        calls = [
            call
            for record in self.records
            for call in record.calls
            if self._matches_target(call, symbol)
        ]
        calls.sort(key=lambda item: (str(item["path"]), int(item["line"])))
        return {
            "callers": calls[:max_results],
            "truncated": len(calls) > max_results,
            "index": self.metadata(),
        }

    def find_callees(self, symbol: str, max_results: int) -> dict[str, object]:
        normalized = symbol.casefold()
        calls = [
            call
            for record in self.records
            for call in record.calls
            if call["caller"] is not None
            and (
                str(call["caller"]).casefold() == normalized
                or str(call["caller"]).casefold().endswith(f".{normalized}")
            )
        ]
        calls.sort(key=lambda item: (str(item["path"]), int(item["line"])))
        return {
            "callees": calls[:max_results],
            "truncated": len(calls) > max_results,
            "index": self.metadata(),
        }

    def find_references(self, symbol: str, max_results: int) -> dict[str, object]:
        references = [
            reference
            for record in self.records
            for reference in record.references
            if self._matches_target(reference, symbol)
        ]
        references.sort(key=lambda item: (str(item["path"]), int(item["line"])))
        return {
            "references": references[:max_results],
            "truncated": len(references) > max_results,
            "index": self.metadata(),
        }

    def find_related_tests(self, target: str, max_results: int) -> dict[str, object]:
        normalized = target.replace("\\", "/")
        path_target = normalized.endswith(".py") or "/" in normalized
        path = PurePosixPath(normalized) if path_target else None
        leaf = (path.stem if path is not None else normalized.rsplit(".", 1)[-1]).casefold()
        results: list[dict[str, object]] = []
        for record in self.records:
            candidate = PurePosixPath(record.path)
            is_test = (
                bool({"test", "tests"} & set(candidate.parts))
                or candidate.name.startswith("test_")
                or candidate.name.endswith("_test.py")
            )
            if not is_test:
                continue
            score = 0
            evidence: set[str] = set()
            stem = candidate.stem.removeprefix("test_").removesuffix("_test").casefold()
            if leaf and stem == leaf:
                score += 6
                evidence.add(f"test filename matches {leaf}")
            imported_targets = {str(item["target"]).casefold() for item in record.imports}
            if any(leaf in imported.split(".") for imported in imported_targets):
                score += 3
                evidence.add(f"imports {leaf}")
            reference_names = {
                str(item["expression"]).casefold().rsplit(".", 1)[-1]
                for item in record.references
            }
            if leaf in reference_names:
                score += 4
                evidence.add(f"references {leaf}")
            if score:
                results.append(
                    {
                        "path": record.path,
                        "module": record.module,
                        "score": score,
                        "evidence": sorted(evidence),
                    }
                )
        results.sort(key=lambda item: (-int(item["score"]), str(item["path"])))
        return {
            "tests": results[:max_results],
            "truncated": len(results) > max_results,
            "index": self.metadata(),
        }

    def _resolve_graph_root(self, query: str) -> tuple[str, list[dict[str, object]]]:
        symbols = [symbol for record in self.records for symbol in record.symbols]
        normalized = query.casefold()
        exact = [
            symbol
            for symbol in symbols
            if str(symbol["qualified_name"]).casefold() == normalized
        ]
        if len(exact) == 1:
            return "exact", exact
        if exact:
            return "ambiguous", exact
        named = [
            symbol
            for symbol in symbols
            if str(symbol["name"]).casefold() == normalized
            or str(symbol["qualified_name"]).casefold().endswith(f".{normalized}")
        ]
        named.sort(key=lambda item: (str(item["path"]), int(item["line"])))
        if len(named) == 1:
            return "unique_suffix", named
        if named:
            return "ambiguous", named
        suggestions = [
            symbol
            for symbol in symbols
            if normalized in str(symbol["name"]).casefold()
            or normalized in str(symbol["qualified_name"]).casefold()
        ]
        suggestions.sort(key=lambda item: (str(item["path"]), int(item["line"])))
        return "not_found", suggestions

    def trace_call_graph(
        self,
        symbol: str,
        direction: str,
        max_depth: int,
        max_results: int,
    ) -> dict[str, object]:
        """Return a bounded, evidence-carrying static neighborhood for one symbol."""

        root_resolution, candidates = self._resolve_graph_root(symbol)
        base: dict[str, object] = {
            "query": symbol,
            "root_resolution": root_resolution,
            "root_candidates": candidates[:20],
            "nodes": [],
            "edges": [],
            "reachable_tests": [],
            "related_tests": [],
            "limits": {
                "direction": direction,
                "max_depth": max_depth,
                "max_results": max_results,
            },
            "truncated": len(candidates) > 20,
            "index": self.metadata(),
        }
        if root_resolution in {"ambiguous", "not_found"}:
            return base

        root = str(candidates[0]["qualified_name"])
        definitions = {
            str(item["qualified_name"]): item
            for record in self.records
            for item in record.symbols
        }
        calls_by_caller: dict[str, list[dict[str, object]]] = {}
        calls_by_target: dict[str, list[dict[str, object]]] = {}
        for record in self.records:
            for call in record.calls:
                if call["caller"] is None:
                    continue
                calls_by_caller.setdefault(str(call["caller"]).casefold(), []).append(call)
                calls_by_target.setdefault(str(call["target"]).casefold(), []).append(call)
        nodes: dict[str, dict[str, object]] = {}
        edges: dict[tuple[str, str, str, int], dict[str, object]] = {}
        truncated = False

        def add_node(name: str, depth: int, discovered_via: str) -> None:
            definition = definitions.get(name)
            existing = nodes.get(name)
            if existing is None:
                nodes[name] = {
                    "symbol": name,
                    "depth": depth,
                    "discovered_via": {discovered_via},
                    "defined_in_repository": definition is not None,
                    "path": definition["path"] if definition is not None else None,
                    "line": definition["line"] if definition is not None else None,
                    "kind": definition["kind"] if definition is not None else None,
                }
                return
            existing["depth"] = min(int(existing["depth"]), depth)
            existing["discovered_via"].add(discovered_via)  # type: ignore[union-attr]

        def add_edge(call: dict[str, object], depth: int, discovered_via: str) -> bool:
            nonlocal truncated
            caller = str(call["caller"])
            callee = str(call["target"])
            key = (caller, callee, str(call["path"]), int(call["line"]))
            existing = edges.get(key)
            if existing is not None:
                existing["depth"] = min(int(existing["depth"]), depth)
                existing["discovered_via"].add(discovered_via)  # type: ignore[union-attr]
                return True
            if len(edges) >= max_results:
                truncated = True
                return False
            edges[key] = {
                "caller": caller,
                "callee": callee,
                "path": call["path"],
                "line": call["line"],
                "expression": call["expression"],
                "resolution": call["resolution"],
                "depth": depth,
                "discovered_via": {discovered_via},
            }
            return True

        add_node(root, 0, "root")
        traversals = ("callers", "callees") if direction == "both" else (direction,)
        for traversal in traversals:
            queue: deque[tuple[str, int]] = deque([(root, 0)])
            visited = {root}
            while queue and not truncated:
                current, depth = queue.popleft()
                if depth >= max_depth:
                    continue
                if traversal == "callers":
                    adjacent = list(calls_by_target.get(current.casefold(), []))
                    neighbor_key = "caller"
                else:
                    adjacent = list(calls_by_caller.get(current.casefold(), []))
                    neighbor_key = "target"
                adjacent.sort(key=lambda item: (str(item["path"]), int(item["line"])))
                for call in adjacent:
                    neighbor = str(call[neighbor_key])
                    if not add_edge(call, depth + 1, traversal):
                        break
                    add_node(neighbor, depth + 1, traversal)
                    if neighbor in definitions and neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))

        node_values = list(nodes.values())
        for item in node_values:
            item["discovered_via"] = sorted(item["discovered_via"])  # type: ignore[arg-type]
        node_values.sort(key=lambda item: (int(item["depth"]), str(item["symbol"])))
        edge_values = list(edges.values())
        for item in edge_values:
            item["discovered_via"] = sorted(item["discovered_via"])  # type: ignore[arg-type]
        edge_values.sort(
            key=lambda item: (
                int(item["depth"]),
                str(item["caller"]),
                str(item["callee"]),
                str(item["path"]),
                int(item["line"]),
            )
        )
        reachable_tests = [
            {
                "path": item["path"],
                "symbol": item["symbol"],
                "depth": item["depth"],
                "evidence": "reachable static caller",
            }
            for item in node_values
            if item["path"] is not None
            and (
                bool({"test", "tests"} & set(PurePosixPath(str(item["path"])).parts))
                or PurePosixPath(str(item["path"])).name.startswith("test_")
                or PurePosixPath(str(item["path"])).name.endswith("_test.py")
            )
            and "callers" in item["discovered_via"]
        ]
        reachable_tests.sort(
            key=lambda item: (int(item["depth"]), str(item["path"]), str(item["symbol"]))
        )
        related = self.find_related_tests(root, min(max_results, 25))
        base.update(
            {
                "nodes": node_values,
                "edges": edge_values,
                "reachable_tests": reachable_tests,
                "related_tests": related["tests"],
                "truncated": truncated or bool(related["truncated"]),
            }
        )
        return base
