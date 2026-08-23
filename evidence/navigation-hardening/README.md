# Repository navigation and gate-adaptation evidence

Frozen: 2026-08-23  
PRGuard: 0.8.1  
Provider: DeepSeek `deepseek-v4-pro`, high reasoning

This case records how a real repository exposed product defects in navigation, provider-failure
artifacts, tool convergence, gate discovery, and runtime adaptation. It is not presented as a blind
semantic benchmark: [PrettyTable #474](https://github.com/prettytable/prettytable/issues/474)
already states the padding-loop root cause.

The frozen Base Commit is `3c80d392d32f48b0ab1e368793ddb751dbe41807`. After the hardening changes,
the live Implementer submitted exact structured edits in one attempt. PRGuard asked Git to produce
the selected [Patch](prettytable-474-v081.patch), then the targeted gate passed 22 tests. A separate
wide regression run of the same Patch passed 339 tests; the Harness-derived changed-test gate also
passed 22 tests, with no policy violations. Both private recursive Manifests verified.

## Why the retained failures matter

| Observed failure | Product correction |
| --- | --- |
| Tool-budget failure reported zero Token/tool evidence | Store non-secret partial provider evidence in JSON, Markdown, and the recursive Manifest |
| The 120 KB primary module was skipped by a 100 KB source cap | Raise the bounded default to 250 KB; keep per-file, total-index, response, and context limits |
| Related-test onboarding passed only the source path | Preserve the fully qualified symbol, selecting `tests/test_html.py` instead of a module-name match |
| A model used all read slots before submission | Reserve one terminal-only slot and report remaining read calls in every tool result |
| Ruff configuration was mistaken for a project gate and could auto-fix | Require explicit lint policy, `check --no-fix`, Base-Commit readiness, and block verification-induced worktree edits |
| A runtime-only VCS version stub broke a wider test | Use the conservative PEP 440 placeholder `0.0.0`, protected and excluded from delivery |

The path-free [run summary](run-summary.json) records the accepted run, wider gate, Token counts,
and hashes of retained private Manifests. The public files are authenticated by
[manifest.json](manifest.json). Verify them with:

```bash
uv run python scripts/verify_public_evidence.py
```
