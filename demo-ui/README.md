# PRGuard Studio

PRGuard Studio offers a local coding workspace and evidence replay for two flagship workflows:

- `attrs #1575`: a held-out Issue-to-Patch run accepted by an independent Reviewer;
- `Click #3199`: a green candidate where independent review found and repaired a regression.

The evidence replay tab is a recorded evidence viewer. Its hashes, test
counts, timing, and verdicts are copied from the checked public evidence packages. The source fields
are read-only so changing the displayed Issue cannot silently reuse unrelated recorded results.

Use the language selector in the top-right corner for 中文 or English. Chinese is the default;
the browser remembers the selection. Switching languages preserves the active replay and tab.
Code, commands, hashes, and exported evidence retain their original values.

Run it from the repository root:

```bash
python3 -m http.server 4317 --bind 127.0.0.1 --directory demo-ui/dist
```

Then open <http://127.0.0.1:4317/>. No package install, API key, or server-side process is required.

## Execute a local task

```bash
uv run --no-editable --extra demo prguard studio
```

This opens an authenticated local URL, bound to `127.0.0.1:4318`. The default **Offline execution
demo** creates a temporary clamp repository and previews the exact Task before execution. Confirm
it to run the real FixRunner and Harness, including a failed first attempt and a passing repair.
Only model responses are scripted. Git, isolated worktrees, pytest, artifacts, and manifest checks
are real. Generated work is saved under `work/studio/session-…`.

To work on an existing repository:

```bash
uv run --no-editable --extra agent --extra demo prguard studio \
  --repository /path/to/project \
  --workspace /path/to/prguard-runs \
  --trust-host --provider deepseek
```

The repository must be clean and the workspace must be outside it. The terminal configures the
repository, provider, reviewed `--policy-file` if needed, and explicit host/container execution
choice. For an eligible container worker, replace `--trust-host` with
`--container-image name@sha256:…`. The browser submits only the Issue and Git version; it cannot
choose new filesystem paths, Shell commands, provider keys, or a different execution boundary.
Live provider keys are read from the server process environment, never a browser form.

Preparation uses the existing local onboarding to materialize a frozen checkout and Task. The
preview lists the exact commit, commands, editable/protected paths, timeout, repair limit, and
Task hash. Confirming starts that exact in-memory Task, even if the original source HEAD moves.
Preparing does not call a model or run repository tests.

The page polls ordered progress records while one worker executes the task. Refreshing reconnects
to the current run; it does not submit another model request. A connection error is not a cancelled
run. `Ctrl+C` stops the server and waits for active verification to write its artifacts under the
existing task deadlines. There is no browser cancellation or background job scheduler yet.

Both attempts include proposal summaries/plans and bounded command output. Final Patch and
report/Manifest downloads are selected by the server and checked against recorded SHA-256 values;
modified or symlinked files are rejected. A snapshot can expose a failed outcome and never turns it
into an acceptance. Independent Reviewer is not yet part of the browser execution path; use
`prguard fix --review` for the composed workflow.

The hosted static site provides the local startup instructions. It does not remotely control your
machine. Keep the token-bearing local launch URL private. Use `--no-browser` to print the local
URL, `--port 0` to choose a free port, and `--workspace` to choose a persistent output location.

## Three-minute walkthrough

1. Open `prguard studio` and select the offline execution demo.
2. Explain the Issue and show the frozen Commit, test command, and edit boundary.
3. Confirm execution. Point out the first failed verification and the failure-feedback event.
4. Open both attempt results: the first loses the upper bound, the repair enforces both bounds.
5. Show the actual final diff and download its verified Patch and Manifest.
6. Switch to Evidence replay → Review to explain the recorded Click regression and independent
   Reviewer. State clearly that this step replays an earlier live run.
