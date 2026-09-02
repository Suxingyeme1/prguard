# Real-repository evidence

Frozen: 2026-08-19<br>
PRGuard: 0.5.1<br>
Provider: DeepSeek `deepseek-v4-pro`, high reasoning

PRGuard produced Harness-accepted one-file patches for three public Python issues at exact upstream
commits. This is a manually checked engineering gate, not a statistically representative
benchmark. All three selected runs passed their declared gates; later independent review found an
additional PrettyTable multi-table regression, so this package must not be read as 3/3 semantic
task resolution. Only one case succeeded on its first complete provider invocation.

| Case | Upstream commit | Deterministic gate | Wider check | Attempts | Duration |
| --- | --- | --- | --- | ---: | ---: |
| [Humanize #366](https://github.com/python-humanize/humanize/issues/366) | `ce4147b6c8f8a132f772be0929d58305eb22c5d9` | reproduction 1/1; filesize 76/76; ruff | 701 passed, 74 skipped* | 2 | 258.676 s |
| [PrettyTable #474](https://github.com/prettytable/prettytable/issues/474) | `3c80d392d32f48b0ab1e368793ddb751dbe41807` | reproduction 1/1; HTML 21/21 | 338 existing tests passed; later multi-table evaluator check failed** | 1 | 39.125 s |
| [Inflect #242](https://github.com/jaraco/inflect/issues/242) | `262a247d2d99a47a520cdb2d46adb90df88b4326` | reproduction 1/1; numwords 4/4 | 208 passed, 16 xfailed | 1 | 77.433 s |

\* The optional benchmark module was excluded because its plugin was unavailable.<br>
\** One evaluator-version-stub assertion was deselected and recorded in the private raw run.

Selected diffs: [Humanize](humanize-366.patch),
[PrettyTable](prettytable-474.patch), and [Inflect](inflect-242.patch). Their bytes are authenticated
by [manifest.json](manifest.json). Run:

```bash
uv run python scripts/verify_public_evidence.py
```

## Case boundary

- Agent-visible task text included behavior, reproduction, and expected result only. Root-cause and
  suggested-fix text from issue discussions was excluded.
- Evaluator bases added public reproduction tests. Humanize and PrettyTable also needed generated
  version stubs. There were no hidden tests or Gold Patches.
- Source and tests ran with host-user permissions. This is not hostile-code sandbox evidence.
- API token counters are omitted from the public summary because they are provider accounting, not
  a correctness signal. Raw reports remain frozen locally.

## Failures that changed the design

- A late Implementer response motivated post-return deadline checks.
- A Humanize patch passed an incomplete pytest-only gate but later failed ruff; the selected rerun
  declares both.
- Humanize then exercised the intended finite repair loop: a corrupt first diff was rejected and a
  full replacement passed.
- An Inflect diff with malformed hunk context was rejected by strict `git apply`; its repair turn
  exhausted the first tool budget before a bounded rerun passed.
- A late Reviewer response motivated the same fail-closed post-return deadline rule for review.
- A later same-Patch Reviewer found that the PrettyTable fix leaks maximum row width across
  multiple tables. Base/Candidate replay confirmed the regression despite all existing tests
  passing; this motivated explicit False-Skip blocking in the v0.10.1 scorecard.

These cases support the claim that PRGuard can localize and modify three unrelated repositories,
execute declared gates, and retain useful failure evidence. They also demonstrate why “gate
passed” is not synonymous with “semantically resolved.” They do not establish arbitrary-repository
accuracy, production isolation, or complete Reviewer recall.
