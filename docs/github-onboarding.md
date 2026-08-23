# GitHub Issue onboarding

`fix` can accept one public GitHub Issue URL directly, while `prepare-github` exposes the same
onboarding as a separate review checkpoint. Both fetch the Issue title and body, repository default
branch, and full Base Commit SHA. They deliberately do not fetch comments, linked solutions, hidden
tests, Gold Patches, or evaluator labels.

## Basic flow

The shortest product path is one command:

```bash
uv run prguard fix \
  https://github.com/OWNER/REPOSITORY/issues/NUMBER \
  --workspace work/issue-NUMBER \
  --trust-host \
  --provider deepseek \
  --progress
```

`work/issue-NUMBER` must be new. It retains the checkout and preparation contract under
`artifacts/`, while implementation results are written under `fix-runs/`. Stdout remains only the
versioned final report; onboarding and run progress go to stderr.

Without `--base-commit`, the default-branch tip is resolved and frozen at preparation time. Supply
an explicit 7–40 digit commit SHA to reproduce a historical task. Public repositories only are
supported in this release; URLs that identify Pull Requests are rejected.

Preparation always requires an explicit execution boundary:

- `--trust-host` records that repository tests may run without OS sandboxing;
- `--container-image sha256:...` selects the fail-closed container backend.

The model does not select between those choices. If the network cannot fetch Git objects, a local
clone with the same canonical GitHub `origin` may be used only as a cache:

```bash
uv run prguard prepare-github ISSUE_URL \
  --output work/issue \
  --source-repository /path/to/same/repository \
  --trust-host
```

For a human/CI approval point before the provider call or repository execution, stop after
preparation:

```bash
uv run prguard prepare-github ISSUE_URL \
  --output work/issue \
  --trust-host
```

The output contains an isolated checkout plus `artifacts/task.json`,
`artifacts/preparation-report.json`, and `artifacts/preparation-manifest.json`. Verify before use:

```bash
uv run prguard verify-manifest work/issue/artifacts/preparation-manifest.json
uv run prguard fix work/issue/artifacts/task.json --provider openai --progress
```

## Project policy

Absent configuration, PRGuard conservatively enables `pytest -q` when it sees public test/pytest
configuration, maps explicit Issue symbols to the strongest related public test file when possible,
does not infer lint as a gate from configuration presence alone, and limits edits to discovered
Python source/test roots. Before any model call, the selected pytest targets must collect
successfully and every declared non-pytest gate must pass at the Base Commit; failing pytest
assertions are allowed, while missing imports/plugins and unhealthy quality gates are classified as
environment readiness failures. It fails closed when it cannot find both a verification command
and a source scope. Dependency installation and external service setup are never inferred.

For a missing Python file explicitly declared by Hatch VCS as `version-file`, PRGuard can create a
fixed runtime-only version scaffold inside each detached verification worktree. The Task records
its path, content, and reason; the path is automatically protected, its hash is checked after tests,
and it is excluded from changed files and the delivered Patch. This narrow adapter does not imply
general dependency or build-system installation.

A repository can publish a reviewed `.prguard.toml`:

```toml
version = 1
verification_commands = [
  ["pytest", "-q"],
  ["ruff", "check", "--no-fix", "."],
]
writable_paths = ["src/**", "tests/**"]
protected_paths = ["release/**"]
command_timeout_seconds = 120
task_timeout_seconds = 900
max_repair_attempts = 1
```

Configuration is data, not shell: every argv still passes PRGuard's fixed pytest/Ruff grammar.
Built-in credential/configuration protections are unioned with repository paths and cannot be
removed by the file. Inspect the generated report and Task before allowing execution.
