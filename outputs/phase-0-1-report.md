# PRGuard Phase 0/1 stage report

Date: 2026-08-18

## Outcome

Phase 0 (facts/contracts) and Phase 1 (deterministic harness) are complete. The repository is
initialized on Git branch `main`, uses Python 3.12 with a locked minimal dependency set, and can
execute, record, verify, and replay a fixed local PR case without an LLM.

The updated product statement is:

> PRGuard 是一个面向真实代码仓库的可验证 Multi-Agent Coding System：Implementer 根据 Issue
> 生成并修复 Patch，Independent Reviewer 提供独立代码审查，确定性 Harness 负责测试、权限、
> 回归门禁和可审计交付。

The primary future entry is `fix` (Issue to tested patch). `review` is a later quality module, not
the sole product. Evaluation remains compact, credible, and reproducible rather than becoming the
main implementation effort.

## Delivered contracts and documentation

- strict Pydantic v2 schemas for `Task`, `CodingTaskState`, `CommandSpec`, `ReviewFinding`,
  `VerificationResult`, `TraceEvent`, `PatchApplicationResult`, `HarnessReport`, `RunManifest`,
  policy violations, token usage, outcomes, verdicts, severity, and categories;
- evaluator-only fields such as gold patches, hidden tests, defect labels, and validity labels are
  rejected by `Task` and absent from `public_context()`;
- architecture, threat model, case authoring, compact evaluation protocol, coding-first milestones,
  and five ADRs;
- deterministic verdict/outcome vocabulary and explicit worktree-versus-sandbox boundary.

## Delivered harness

- validates the exact local Git toplevel, clean source checkout, and resolved base commit;
- creates a detached worktree and removes/prunes its registration after every run;
- archives the patch bytes and applies them using `git apply --check` then `git apply`;
- accepts argv only, launches with `shell=False`, and globally limits forms to pytest/ruff (direct
  or `python -m`) in addition to an exact per-task allowlist;
- rejects absolute/path-traversing arguments and shell syntax;
- applies per-command deadlines, a total task deadline across Git preflight/patch/verification,
  process-group termination, private HOME/TMPDIR, a minimal environment, and bounded stdout/stderr;
- records pytest and ruff results as structured data;
- detects protected changes, escaping changed symlinks, source-checkout mutation, and writes beside
  the managed worktree; harness-owned escaped files are recorded then removed;
- fails closed on worktree cleanup errors;
- emits canonical `task.json`, `report.json`, `report.md`, archived candidate patch, final binary
  diff, and a SHA-256 manifest with schema/harness/policy versions;
- verifies hashes without code execution and reconstructs replay tasks from the archived patch.

## Fixture cases

| Case | Expected terminal outcome | Covered behavior |
|---|---|---|
| `correct-patch` | `passed` | applies patch, two tests pass |
| `wrong-patch` | `failed_verification` | patch applies but assertion fails |
| `regression` | `failed_verification` | fail-to-pass succeeds, pass-to-pass fails |
| `patch-apply-failure` | `patch_failed` | context mismatch is reported |
| `command-timeout` | `timed_out` | process group exceeds deadline |

Templates contain no gold patch, hidden test, or defect label. The materializer creates disposable,
independent Git repositories and concrete base commits under the ignored `work/` tree.

## Verification evidence

- Ruff: `All checks passed!`
- Pytest: `35 passed in 5.52s`
- Test split by directory: 19 unit, 8 integration, 4 contract, 4 security tests.
- The five fixture outcomes all match their frozen expectations.
- Security coverage includes shell/path traversal rejection, exact allowlisting, protected paths,
  adjacent-worktree writes, source-checkout mutation, output bounding, deadlines, and artifact
  tampering/unlisted-file detection.

The final sample run resolved base commit
`63de346f4e94d2fc745709e9832378be82c06e9f`, applied patch SHA-256
`1b2f66a1ac9c55f617630bdcc6568202ff5722618e3d44cb055379bcb531c2ce`, passed two tests,
and produced final diff SHA-256
`c17ef781fc8513c1586c6181cb9788c6c8bc9f5960cc3ccd447653e2c7b4b029`.

- Original manifest SHA-256 payload: `ae69b1fc3f6134bef58c306c5496097aac57c2e5436900f61751531ef9dc6f33`
- Replay manifest SHA-256 payload: `c94c376935057700e50557aac418e57965d6e8ae8cc4b4501d6124c70fe49a8a`
- Original and replay candidate-patch and final-diff hashes are identical; both manifests pass
  independent verification.

## Honest boundary

Phase 1 is not a hostile-code sandbox. Worktrees isolate Git state, while argv policy, environment
scrubbing, process deadlines, and post-run audits reduce and expose accidental or simple malicious
behavior. Arbitrary pytest/plugin/native code can still use host-user filesystem and network
authority or evade directory snapshots. Public/untrusted repositories require the later container
boundary with network denial, read-only mounts, uid separation, and CPU/memory/pid quotas.

The command grammar intentionally supports only pytest and ruff. Mypy or project-specific tools
must be added as explicit capabilities with argument grammars and tests—not by introducing a free
shell. The source checkout must be clean. Artifact hashes provide integrity, not signatures or
remote attestation.

## Next phase: single Implementer MVP

The next work should build `prguard fix` in this order:

1. bounded repository search and source-reading capabilities inside the detached worktree;
2. an Implementer-internal structured plan (not a separate Planner Agent);
3. restricted patch-based edits for source and necessary public tests, with path and diff budgets;
4. provider-neutral model adapter plus a deterministic fake for contract tests;
5. initial implementation -> existing Harness -> one repair using only structured failure evidence;
6. final gate and review-ready patch/artifacts through a usable `fix` CLI;
7. two or three manually checked repository-level Demo A cases.

Only after that path is demonstrably useful should the read-only Independent Reviewer and
`review` CLI be implemented. A Diagnostician remains evidence-driven and optional.

