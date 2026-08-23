from pathlib import Path

import pytest

from prguard.implementer.errors import RepositoryAccessError
from prguard.implementer.tools import RepositoryTools
from prguard.schemas import CommandSpec, FixTask


def _task(repository: Path, **overrides: object) -> FixTask:
    values: dict[str, object] = {
        "case_id": "python-ast-tools",
        "repository": repository,
        "base_commit": "a" * 40,
        "issue": "Correct price calculation.",
        "commands": [CommandSpec(argv=["pytest", "-q"], kind="pytest")],
        "allowed_commands": [["pytest", "-q"]],
        "writable_paths": ["src/**", "tests/**"],
    }
    values.update(overrides)
    return FixTask.model_validate(values)


def _write_python_project(root: Path) -> None:
    source = root / "src" / "shop"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text(
        "from .pricing import Price, quote\n", encoding="utf-8"
    )
    (source / "tax.py").write_text(
        "def tax(amount):\n    return amount * 2\n", encoding="utf-8"
    )
    (source / "pricing.py").write_text(
        "from decimal import Decimal as D\n"
        "from shop.tax import tax\n\n"
        "class Price:\n"
        "    @staticmethod\n"
        "    def total(amount, rate=1):\n"
        "        adjusted = tax(amount)\n"
        "        return D(adjusted) * rate\n\n"
        "def quote(amount):\n"
        "    return Price.total(amount)\n",
        encoding="utf-8",
    )
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_pricing.py").write_text(
        "from shop import Price, quote\n\n"
        "def test_quote():\n"
        "    assert quote(2) == Price.total(2)\n",
        encoding="utf-8",
    )


def test_ast_index_finds_qualified_symbols_imports_and_direct_callers(
    tmp_path: Path,
) -> None:
    _write_python_project(tmp_path)
    tools = RepositoryTools(tmp_path, _task(tmp_path))

    symbols = tools.find_symbols("Price.total", 20)
    total = symbols["symbols"][0]
    assert total["qualified_name"] == "shop.pricing.Price.total"
    assert total["kind"] == "method"
    assert total["parameters"] == ["amount", "rate"]
    assert total["line"] == 6

    imports = tools.list_imports("src/shop/pricing.py", 20)["imports"]
    assert [(item["module"], item["name"], item["alias"]) for item in imports] == [
        ("decimal", "Decimal", "D"),
        ("shop.tax", "tax", None),
    ]

    callers = tools.find_callers("shop.tax.tax", 20)["callers"]
    assert callers[0]["caller"] == "shop.pricing.Price.total"
    assert callers[0]["target"] == "shop.tax.tax"
    assert callers[0]["resolution"] == "import_alias"

    callees = tools.find_callees("shop.pricing.Price.total", 20)["callees"]
    assert [item["target"] for item in callees] == ["shop.tax.tax", "decimal.Decimal"]


def test_ast_index_maps_references_and_related_public_tests(tmp_path: Path) -> None:
    _write_python_project(tmp_path)
    tools = RepositoryTools(tmp_path, _task(tmp_path))

    references = tools.find_references("shop.pricing.quote", 20)["references"]
    test_reference = next(item for item in references if item["path"].startswith("tests/"))
    assert test_reference["scope"] == "test_pricing.test_quote"
    assert test_reference["line"] == 4

    related = tools.find_related_tests("src/shop/pricing.py", 20)
    assert related["tests"][0]["path"] == "tests/test_pricing.py"
    assert related["tests"][0]["score"] >= 6
    assert related["index"]["analysis"] == "bounded_static_ast"
    assert "runtime dispatch" in related["index"]["limitations"]


def test_ast_index_reports_parse_errors_without_exposing_file_content(
    tmp_path: Path,
) -> None:
    (tmp_path / "broken.py").write_text("TOP_SECRET = 'do-not-return'\ndef (\n")
    tools = RepositoryTools(tmp_path, _task(tmp_path, writable_paths=["*.py"]))

    result = tools.find_symbols("anything", 10)

    assert result["symbols"] == []
    assert result["index"]["parse_error_count"] == 1
    assert "do-not-return" not in str(result)


@pytest.mark.parametrize(
    ("method", "arguments"),
    [
        ("find_symbols", {"query": "\nsecret", "max_results": 10}),
        ("list_imports", {"path": "../outside.py", "max_results": 10}),
        ("find_related_tests", {"target": "../outside.py", "max_results": 10}),
        ("find_callers", {"symbol": "value", "max_results": 201}),
    ],
)
def test_ast_queries_reject_unsafe_or_unbounded_inputs(
    tmp_path: Path, method: str, arguments: dict[str, object]
) -> None:
    tools = RepositoryTools(tmp_path, _task(tmp_path))

    with pytest.raises(RepositoryAccessError):
        getattr(tools, method)(**arguments)
