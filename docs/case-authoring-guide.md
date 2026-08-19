# Case authoring guide

Each case must identify a local Git repository, full base commit, issue that is understandable
without hidden information, optional candidate patch, exact argv allowlist, protected globs, and
timeouts. Prefer two command groups when possible: fail-to-pass and pass-to-pass.

Before freezing a case:

1. prove the base commit and patch apply deterministically;
2. prove each fail-to-pass fails before and passes after the valid repair;
3. prove pass-to-pass tests pass both before and after;
4. inspect the final diff for unrelated and protected changes;
5. materialize twice and compare semantic results;
6. store gold, hidden tests, and labels only in evaluator-owned storage;
7. hash the frozen inputs and record rejected cases with reasons.

The committed templates under `benchmark/fixtures` are harness fixtures, not benchmark evidence.
Run `scripts/materialize_fixtures.py` to create real Git repositories and runnable Task JSON files.

