# Demo A: real Issue to verified Patch

Demo A runs PRGuard against [Humanize #366](https://github.com/python-humanize/humanize/issues/366)
at a frozen public commit. The Agent receives the Issue, repository tools, writable-path policy, and
declared verification commands. It does not receive a Gold Patch, hidden test, root-cause label, or
issue-discussion solution.

## Run it

Install the locked development and provider dependencies, then materialize the public case:

```bash
uv sync --extra agent --extra dev --no-editable --reinstall-package prguard
uv run python scripts/materialize_demo_a.py
```

Inject the key into the current process environment and run with human-readable stderr progress:

```bash
export DEEPSEEK_API_KEY='...'
uv run prguard fix work/demo-a-humanize-366/task.json \
  --provider deepseek \
  --model deepseek-v4-pro \
  --reasoning-effort high \
  --progress \
  --artifacts work/demo-a-artifacts
unset DEEPSEEK_API_KEY
```

`--progress` prints stage changes and a 15-second heartbeat to stderr. The versioned JSON report
remains the only stdout payload, so automation can parse it unchanged.

## Frozen observed run

On 2026-08-20, run `e86edeeb-2a34-4ada-ae6e-9ee2880c4147` exercised the complete bounded repair
path:

1. DeepSeek used 16 repository tool calls and submitted a malformed unified diff.
2. Git rejected attempt 0 as `patch_failed` with `corrupt patch at line 21`.
3. PRGuard returned structured failure evidence and allowed one full replacement attempt.
4. Attempt 1 used 13 repository tool calls and changed only `src/humanize/filesize.py`.
5. The public reproduction passed 1/1, the filesize regression file passed 76/76, and Ruff passed.

The accepted run took 330.303 seconds. Its final Patch SHA-256 is
`719dd088f244bbfa6610cb1051eaa97d2fef0706d89d26c91897e8febe98550e`; the frozen raw recursive
Manifest's declared digest is
`654bbb2bdf8c4eec3337964999a6284f5aba75feff31e2769534b18379f57eb5`.
The exact source checkout remained clean and an exact-key scan found zero Artifact matches.

This is a reproducible engineering demonstration, not a claim that model output itself is
deterministic or that one case estimates general task-resolution accuracy.
