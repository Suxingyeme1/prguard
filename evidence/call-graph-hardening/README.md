# Bounded call-graph evidence: PrettyTable #474

This package records a deterministic, path-free code-navigation check at PrettyTable commit
`3c80d392d32f48b0ab1e368793ddb751dbe41807`.

## Query

- root: `prettytable.prettytable.from_html`
- direction: `both`
- maximum depth: 3
- maximum edges: 80
- analysis: Python standard-library AST only; repository source was not imported or executed

After preparing the same Issue and commit, the query can be replayed with:

```bash
uv run prguard inspect-symbol WORKSPACE/artifacts/task.json \
  --symbol prettytable.prettytable.from_html \
  --direction both --max-depth 3 --max-results 80
```

## Observed result

PRGuard indexed 15 Python files with no parse errors, large-file skips, or index truncation. The
query returned 7 nodes and 6 caller-to-callee edges without graph truncation. It identified three
reachable test symbols in `tests/test_html.py` and ranked the same file as the leading related test.

Selected relationships were:

- `prettytable.prettytable.from_html_one -> prettytable.prettytable.from_html`;
- `test_html.TestHtmlConstructor.test_html_and_back -> prettytable.prettytable.from_html`;
- two additional `test_html` methods -> `prettytable.prettytable.from_html_one`;
- `prettytable.prettytable.from_html -> prettytable.prettytable._make_table_handler`;
- `prettytable.prettytable.from_html -> parser.feed`.

Calls imported through PrettyTable's package exports were labeled `import_alias_reexport`; the
local helper used `module_definition`; `parser.feed` remained `unresolved_lexical`. This distinction
is intentional: the tool exposes what static evidence supports instead of upgrading an instance
call into a guessed target.

## Claim boundary

This is real-repository evidence for bounded static navigation and re-export resolution. It is not
a live-model run, a benchmark accuracy result, or a runtime-complete call graph. Dynamic dispatch,
reflection, dependency injection, monkey-patching, generated code, and unavailable source can
produce missing or ambiguous relationships.

`run-summary.json` contains the machine-readable frozen observation. `manifest.json` hashes this
report and summary so `uv run python scripts/verify_public_evidence.py` can detect modification.
