# Contributing to PRGuard

PRGuard welcomes focused fixes, deterministic fixtures, provider-contract improvements, and
trust-boundary hardening. Changes should preserve the separation between model proposals and
deterministic acceptance.

## Development setup

Use Python 3.12, Git, and uv:

```bash
uv sync --extra dev --no-editable --reinstall-package prguard
uv run ruff check src tests scripts
uv run pytest -q
```

Run `uv run python scripts/run_offline_demo.py` for the shortest end-to-end check.

## Change expectations

- Add the smallest test that proves the behavior or regression.
- Keep commands as explicit argv arrays. Do not add shell-string execution.
- Keep model providers behind the existing proposal/review contracts.
- Preserve exact base-commit resolution and source-checkout cleanliness.
- Treat manifests and frozen artifacts as immutable content-addressed records.
- Record new limits, permissions, or verdict behavior in an ADR when they alter the trust boundary.

Unit, integration, contract, and security tests live in separate directories. A change to schemas,
provider payloads, command policy, path handling, deadlines, or artifact verification should include
the corresponding contract or security coverage.

## Adding a case

Use the [case authoring guide](docs/case-authoring-guide.md). A useful case has one exact base
commit, a human-checkable Issue, declared public commands, an evaluator-only expected record, and a
documented reason for every deselection or missing optional dependency. Never expose a Gold Patch,
hidden test, or defect label in an Agent-visible task.

## Pull requests

Keep a pull request limited to one coherent change. Describe the observed problem, the contract or
implementation change, the commands run, and any trust-boundary effect. Sanitize logs and artifacts
before attaching them: remove credentials, private source, personal paths, and provider request
headers.

By contributing, you agree that your contribution is licensed under the MIT License.
