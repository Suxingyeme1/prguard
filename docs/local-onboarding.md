# Local repository onboarding

PRGuard can start from a clean local Git repository and ordinary Issue text. You do not need to
write Task JSON by hand.

## One-command Fix

Keep the PRGuard workspace outside the source repository:

```bash
uv run prguard fix \
  "Fix add() so it returns the sum of both operands." \
  --repository /path/to/project \
  --workspace /path/to/prguard-runs/add-fix \
  --base-commit HEAD \
  --trust-host \
  --provider deepseek \
  --progress
```

For a longer requirement, use a UTF-8 text file and omit the positional Issue:

```bash
uv run prguard fix \
  --repository /path/to/project \
  --issue-file /path/to/issue.md \
  --workspace /path/to/prguard-runs/add-fix \
  --base-commit HEAD \
  --trust-host \
  --provider deepseek \
  --progress
```

`HEAD` is resolved to a 40-character commit before any model call. The source working tree must be
clean. PRGuard initializes a separate checkout, fetches only the resolved commit from the local Git
object source, disables repository hooks and user/system Git config during materialization, and
verifies the detached checkout is clean and exact.

## Two-stage review

To inspect the generated contract before spending model tokens or running tests:

```bash
uv run prguard prepare-local \
  --repository /path/to/project \
  --issue-file /path/to/issue.md \
  --output /path/to/prguard-runs/add-fix \
  --base-commit HEAD \
  --trust-host

uv run prguard verify-manifest \
  /path/to/prguard-runs/add-fix/artifacts/preparation-manifest.json

uv run prguard fix \
  /path/to/prguard-runs/add-fix/artifacts/task.json \
  --provider deepseek \
  --progress
```

The preparation report records the source path, requested and resolved Base Commit, Issue SHA-256,
execution boundary, discovered commands, writable/protected paths, runtime scaffolds, warnings, and
Task path. The Manifest binds the Task and report.

## Policy boundary

Automatic discovery is conservative: it recognizes Python source/test layout, pytest configuration,
issue-related public tests, and a small runtime-file case. It does not install dependencies, infer
external services, or invent arbitrary shell commands. If the repository cannot be described
safely, preparation stops and asks for a reviewed `.prguard.toml`.

`--trust-host` is an explicit operator decision. For higher-risk code, pass a digest-pinned
`--container-image` instead. The model does not choose the execution boundary.
