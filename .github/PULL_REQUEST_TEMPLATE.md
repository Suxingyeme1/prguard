## What changed

Describe the user-visible or contract-level change.

## Evidence

- [ ] `uv run ruff check src tests scripts`
- [ ] `uv run pytest -q`
- [ ] New behavior has a focused test or a written reason why it does not need one
- [ ] No credential, private source, hidden evaluator input, or machine-specific path was added

## Trust-boundary impact

Explain any change to command execution, filesystem access, model context, credentials, timeouts,
policy gates, or artifacts. Write `None` when the boundary is unchanged.
