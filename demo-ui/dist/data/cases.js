window.PRGuardCases = {
  attrs: {
    mode: "fix",
    kicker: "LIVE HOLDOUT · ATTRS #1575",
    title: "Issue to review-ready patch",
    repository: "python-attrs/attrs",
    issueUrl: "https://github.com/python-attrs/attrs/issues/1575",
    evidenceUrl: "https://github.com/Suxingyeme1/prguard/tree/main/evidence/attrs-1575-holdout",
    commit: "6851ab593cd2",
    runtime: "CPython 3.14.2 · Linux x86_64",
    issue: "Python 3.14 turns an unimported ClassVar annotation into a ForwardRef. attrs treats it as an instance field and generates an incorrect required constructor argument.",
    gate: "pytest -q tests/test_annotations.py",
    manifest: "4df8656d…e8545ab",
    patch: { files: 2, additions: 27, deletions: 1, hash: "ea56a09d…ed9a" },
    stages: [
      { name: "Freeze", detail: "Task + commit" },
      { name: "Locate", detail: "24 tool calls" },
      { name: "Patch", detail: "2 files" },
      { name: "Verify", detail: "49 passed" },
      { name: "Review", detail: "Accept" },
      { name: "Deliver", detail: "Manifest" }
    ],
    events: [
      { tone: "info", label: "PREPARE", text: "Resolved HEAD to 6851ab593cd2 and created a detached worktree." },
      { tone: "tool", label: "SEARCH", text: "Found ClassVar detection in src/attr/_make.py::_is_class_var." },
      { tone: "tool", label: "TRACE", text: "Python 3.14 returns ForwardRef('ClassVar[str]') for the missing runtime import." },
      { tone: "patch", label: "EDIT", text: "Unwrap __forward_arg__ before the existing ClassVar prefix check." },
      { tone: "expected", label: "BASE", text: "Agent-authored tests failed as expected · 2 failed, 47 passed." },
      { tone: "pass", label: "GATE", text: "Candidate verification passed · 49 passed in 0.23s." },
      { tone: "review", label: "REVIEW", text: "Independent Reviewer accepted · 0 blocking findings." },
      { tone: "pass", label: "EVALUATOR", text: "Precommitted sealed evaluator passed · no new regression." },
      { tone: "pass", label: "DELIVER", text: "Review-ready Patch and recursive SHA-256 Manifest frozen." }
    ],
    evidence: [
      { name: "Task contract", meta: "Issue + Base + policy", hash: "6851ab59…2a074" },
      { name: "Fix manifest", meta: "1 attempt · verified", hash: "4df8656d…e8545ab" },
      { name: "Candidate patch", meta: "2 files · source + test", hash: "ea56a09d…ed9a" },
      { name: "Review manifest", meta: "fresh context · accept", hash: "672e8368…19ac76" },
      { name: "Sealed evaluator", meta: "attached after review", hash: "2aaaea18…7222e56" }
    ],
    overview: {
      verdict: "Resolved in one attempt",
      copy: "The Implementer located the compatibility boundary, added FAIL_TO_PASS coverage, and produced a minimal patch. Independent Review accepted the exact verified diff; the hidden evaluator passed after both agent artifacts were frozen.",
      facts: [["Duration", "136.8s + 190.5s review"], ["Tool budget", "24 implementer · 12 reviewer"], ["Wider suite", "1,388 passed · 0 new failures"]]
    },
    review: { verdict: "ACCEPT", severity: "No blocking findings", body: "The change is narrow, preserves ordinary instance attributes, and directly addresses Python 3.14 ForwardRef handling. Public regression tests demonstrate the failure on Base." },
    patchText: `diff --git a/src/attr/_make.py b/src/attr/_make.py
@@ -297,7 +297,11 @@ def _is_class_var(annot):
-    annot = str(annot)
+    forward_arg = getattr(annot, "__forward_arg__", None)
+    if forward_arg is not None:
+        annot = forward_arg
+    else:
+        annot = str(annot)

diff --git a/tests/test_annotations.py b/tests/test_annotations.py
@@ -688,6 +688,7 @@
+        typing.ForwardRef("ClassVar[int]"),
@@ -698,3 +699,25 @@
+def test_classvar_forward_ref_py_314():
+    ...`
  },
  click: {
    mode: "review",
    kicker: "DEFECTIVE PR · CLICK #3199",
    title: "Review, find regression, repair",
    repository: "pallets/click",
    issueUrl: "https://github.com/pallets/click/issues/3145",
    evidenceUrl: "https://github.com/Suxingyeme1/prguard/tree/main/evidence/click-controlled-repair",
    commit: "frozen defective candidate",
    runtime: "CPython 3.12 · Linux x86_64",
    issue: "Review a candidate refactor of default lookup. Preserve the public Context.lookup_default() extension point and existing callback semantics.",
    gate: "pytest -q",
    manifest: "controlled repair · verified",
    patch: { files: 4, additions: 31, deletions: 7, hash: "222d00a8…501c" },
    stages: [
      { name: "Freeze", detail: "PR + commit" },
      { name: "Verify", detail: "1323 passed" },
      { name: "Review", detail: "P2 finding" },
      { name: "Repair", detail: "4 edits" },
      { name: "Re-verify", detail: "1324 passed" },
      { name: "Deliver", detail: "Manifest" }
    ],
    events: [
      { tone: "info", label: "PREPARE", text: "Frozen the exact candidate and declared full-suite gate." },
      { tone: "pass", label: "GATE", text: "Candidate passed 1,323 repository tests and 9 changed-test replays." },
      { tone: "tool", label: "TRACE", text: "Reviewer followed Context.lookup_default() through the public override path." },
      { tone: "danger", label: "P2 FINDING", text: "Candidate bypasses the public extension point for Context subclasses." },
      { tone: "review", label: "REPAIR", text: "Implementer received the frozen finding and submitted 4 structured edits." },
      { tone: "expected", label: "BASE/CANDIDATE", text: "Hidden check: Base passes, defective candidate fails." },
      { tone: "pass", label: "FINAL GATE", text: "Repaired patch passed 1,324 tests and 10 changed-test replays." },
      { tone: "pass", label: "EVALUATOR", text: "Repaired candidate restored the public override path." },
      { tone: "pass", label: "DELIVER", text: "Controlled repair and nested manifests frozen." }
    ],
    evidence: [
      { name: "Candidate contract", meta: "defective PR · green gate", hash: "d35bad3b…c6d7bb" },
      { name: "Review finding", meta: "P2 · source linked", hash: "1945a757…7970" },
      { name: "Repair summary", meta: "4 structured edits", hash: "35b94527…a770bd" },
      { name: "Final patch", meta: "1,324 tests passed", hash: "222d00a8…501c" },
      { name: "Evaluator record", meta: "base → fail → pass", hash: "6d4e4e96…31a0a" }
    ],
    overview: {
      verdict: "Reviewer prevented a regression",
      copy: "The declared test suite was green, but independent source tracing found that the candidate bypassed a public extension point. One controlled repair restored the contract and passed the final gate.",
      facts: [["Finding", "P2 · public extension regression"], ["Repair", "1 bounded replacement patch"], ["Final gate", "1,324 passed + 10 replays"]]
    },
    review: { verdict: "REQUEST CHANGES", severity: "P2 · high confidence", body: "The refactor bypasses Context.lookup_default(), breaking subclasses that override the documented extension point. Reproduce with a Context subclass and route all lookup paths through the public method." },
    patchText: `diff --git a/src/click/core.py b/src/click/core.py
@@ public default lookup path
-    value = self.default_map.get(param.name)
+    value = ctx.lookup_default(param.name, call=False)

diff --git a/tests/test_arguments.py b/tests/test_arguments.py
+def test_context_lookup_default_override():
+    """Public Context overrides remain observable."""
+    ...`
  }
};
