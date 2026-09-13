# PRGuard Studio

PRGuard Studio offers a local coding workspace and two recorded examples of flagship workflows:

- `attrs #1575`: a held-out Issue-to-Patch run accepted by an independent Reviewer;
- `Click #3199`: a green candidate where independent review found and repaired a regression.

The recorded examples are evidence viewers. Their hashes, test counts, timing, and verdicts come
from checked public evidence packages. They are visibly labelled as completed recordings: opening
one does not call a model, write source code, or imitate a fresh run.

Use the language selector in the top-right corner for 中文 or English. Chinese is the default and
the browser remembers the selection. Product copy is translated through explicit message IDs;
commands, hashes, source paths, user input, and recorded evidence retain their original values.

Run it from the repository root:

```bash
python3 -m http.server 4317 --bind 127.0.0.1 --directory demo-ui/dist
```

Then open <http://127.0.0.1:4317/>. No package install, API key, or server-side process is required.

## Execute a local task

```bash
uv run --no-editable --extra demo prguard studio --enable-independent-review
```

This opens an authenticated local URL, bound to `127.0.0.1:4318`. The default **Offline execution
demo** creates a temporary clamp repository and previews the exact Task before execution. Confirm
it to run the real FixRunner and Harness, including a failed first attempt and a passing repair.
Only model responses are scripted. Git, isolated worktrees, pytest, artifacts, and manifest checks
are real. Choose **Fix, verify and review** to execute the composed pipeline with a fresh scripted
Reviewer. The demo's final clamp patch receives no findings. The persistent demo label identifies
this as scripted model output, including on the result page. Generated work is saved under
`work/studio/session-…`. Omit `--enable-independent-review` for a Fix-only session.

With review enabled, select **Green tests → review finds regression → repair and test**. Its small
normalizer repository starts with one incomplete test. A scripted change passes it but drops
lowercase conversion; the scripted Reviewer supplies a source-linked finding. The repair restores
the behavior and adds a regression test. In the review result, expand the reproduction record to
inspect the command, failing output and reference Patch hash, then compare final passing output.
The workflow is fixed to reviewed Fix for this case. All reasoning and edits are predetermined;
the case is a runnable product demonstration, not an upstream evaluation or model success claim.

To work on an existing repository:

```bash
uv run --no-editable --extra agent --extra demo prguard studio \
  --repository /path/to/project \
  --workspace /path/to/prguard-runs \
  --trust-host --provider deepseek --enable-independent-review
```

The repository must be clean and the workspace must be outside it. The terminal configures the
repository, provider, reviewed `--policy-file` if needed, and explicit host/container execution
choice. Reviewer configuration is also set here: `--review-provider`, `--review-model`,
`--review-reasoning-effort` and `--review-max-tool-calls` (default 12). The current live Reviewer
adapter is DeepSeek; its credentials stay in the server environment. For an eligible container
worker, replace `--trust-host` with `--container-image name@sha256:…`. The browser submits the
Issue, Git version and one enabled workflow; it cannot choose new filesystem paths, Shell
commands, provider keys, or a different execution boundary.
Live provider keys are read from the server process environment, never a browser form.

Preparation uses the existing local onboarding to materialize a frozen checkout and Task. The
preview lists the exact commit, commands, editable/protected paths, timeout, repair limit, and
Task hash. Reviewed tasks also freeze Reviewer settings, stage budgets and any scripted proposal
contents, including the separate review-repair proposal sequence. Changing those input files after
preview does not change an approved execution. Confirming starts that exact Task, even if the
original source HEAD moves.
Preparing does not call a model or run repository tests.

The page polls ordered progress records while one worker executes the task. The sidebar lists up
to 50 tasks prepared during this server process. Switching tasks or refreshing recovers the
selected run; it does not submit another model request. A connection error is not a cancelled
run. History does not recover across server restarts, but artifacts remain on disk.
`Ctrl+C` stops the server and waits for active verification to write its artifacts under the
existing task deadlines. There is no browser cancellation or background job scheduler yet.

Both attempts include proposal summaries/plans and bounded command output. Final Patch and
report/Manifest downloads are selected by the server and checked against recorded SHA-256 values;
modified or symlinked files are rejected. A snapshot can expose a failed outcome and never turns it
into an acceptance. Reviewed tasks show source-linked findings, routing details, independent
verification and any controlled repair. Fix may repair one verification failure, and the composed
workflow may make one additional repair after review. An accepted repair means its deterministic
verification passed; there is no second independent review pass. A failed review blocks final
Patch delivery even when the initial Fix passed. Reports remain downloadable for diagnosis.

The changes tab groups the exact unified diff by file with old/new line numbers and addition/
deletion highlights. The viewer is presentation-only; copying or downloading preserves the original
Patch bytes. Scripted repository testing requires `--proposal-sequence`, `--review-submission`
and `--review-repair-proposal-sequence` when the corresponding providers are scripted.

The hosted static site provides the local startup instructions. It does not remotely control your
machine. Keep the token-bearing local launch URL private. Use `--no-browser` to print the local
URL, `--port 0` to choose a free port, and `--workspace` to choose a persistent output location.

## Three-minute walkthrough

The collapsed **Connect your own repository** guide is available on the static welcome page and
local task form. It explains clean-checkout preparation, credentials in the launching terminal,
the source/workspace split and host/container choice. Its command uses placeholders and is never
executed by the page. The external-policy TOML is a format example, not an automatically approved
gate. Missing tests still require real test preparation or an explicitly selected static gate;
static checks are not proof of Issue resolution.

Approval displays the policy source and original discovery warnings. Automatically detected
commands require human review for Issue coverage and necessary regressions. Preparation errors
show category-specific recovery guidance, retain the raw error separately, and offer **Return to
request** without automatically retrying. The submitted Issue, version and workflow survive this
return even after refreshing the failed run. These drafts are recovered from the current server
session, not from a durable browser history.

1. Open `prguard studio --enable-independent-review`. The workspace opens to a new local task.
2. Explain the Issue and show the configured repository receipt. Enter the requested Git version if
   it is not `HEAD`.
3. Choose Fix alone or Fix with review, then prepare the execution plan. Show the resolved Commit,
   test command, edit boundary, timeout, and
   explicit confirmation before any model call or repository test run.
4. Confirm execution. Point out the first failed verification and the failure-feedback event.
5. Inspect attempt summaries, file diffs, test output and verified Patch/report/Manifest downloads.
   On reviewed tasks, open the Review tab. Explain that the offline Reviewer response is scripted;
   actual model review requires a configured local repository and model credentials.
6. Open **Example runs** to explain the recorded Click regression and independent Reviewer finding.
   State clearly that this is evidence from an earlier completed run, not a new execution.

For automated checks, see the [browser test guide](../tests/browser/README.md). Playwright is a
development-only dependency; end users still need no Node packages to open Studio.
