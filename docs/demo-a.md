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

## Current frozen observed run

On 2026-08-23, `prepare-github` froze the Issue at
`ce4147b6c8f8a132f772be0929d58305eb22c5d9`, selected a related public test, and recorded a
runtime-only Hatch VCS version scaffold. A fresh DeepSeek run used 14 repository tool calls and
submitted two exact replacements. PRGuard converted those edits into a Git-authored Patch changing
only `src/humanize/filesize.py` and `tests/test_filesize.py`.

The run was accepted in one attempt after 78 tests and Ruff passed. A separate wider gate passed
702 tests, skipped 74 optional benchmarks, and passed Ruff. The Patch SHA-256 is
`76ad64057e591fa6d9a622c3892fbfd55427772206d73cb5da37330e9ad9fa33` and both recursive
Manifests verified. See the [v0.8 phase report](v0.8.0-phase-report.md) for the retained failed run,
environment diagnosis, token counts, and static-analysis boundary.

## Historical bounded-repair run

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
