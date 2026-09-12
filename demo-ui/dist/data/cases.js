/*
 * Public, frozen case summaries. They are deliberately separate from the
 * local Studio API: opening an example never starts a provider call or writes
 * to a repository.
 */
window.PRGuardCases = {
  attrs: {
    id: "attrs",
    kind: "fix",
    repository: "python-attrs/attrs",
    issueUrl: "https://github.com/python-attrs/attrs/issues/1575",
    evidenceUrl: "https://github.com/Suxingyeme1/prguard/tree/main/evidence/attrs-1575-holdout",
    baseCommit: "6851ab593cd2",
    runtime: "CPython 3.14.2 · Linux x86_64",
    title: {
      zh: "从兼容性问题到已验证补丁",
      en: "A verified patch for a compatibility issue",
    },
    card: {
      zh: "attrs 在 Python 3.14 中错误识别 ForwardRef 形式的 ClassVar。实现端补充回归测试，独立审查后通过扩大测试。",
      en: "attrs misclassified a ForwardRef ClassVar on Python 3.14. The run added regression coverage, then passed independent review and wider tests.",
    },
    issue: {
      zh: "Python 3.14 会将未导入的 ClassVar 注解变成 ForwardRef。attrs 将它误作实例字段，从而生成了不正确的必填构造参数。",
      en: "Python 3.14 turns an unimported ClassVar annotation into a ForwardRef. attrs treats it as an instance field and creates an incorrect required constructor argument.",
    },
    outcome: {
      zh: "一次尝试完成修复",
      en: "Resolved in one attempt",
    },
    outcomeDetail: {
      zh: "实现端定位到类型注解兼容边界，先添加基础版本会失败的测试，再提交最小修改。独立 Reviewer 接受了经验证的差异，冻结运行后隐藏评测也通过。",
      en: "The Implementer located the annotation compatibility boundary, added a test that fails on Base, and submitted a minimal change. An independent Reviewer accepted the verified diff; the sealed evaluator then passed.",
    },
    stats: [
      { label: { zh: "修改文件", en: "Files changed" }, value: { zh: "2 个", en: "2" } },
      { label: { zh: "最终测试", en: "Final tests" }, value: { zh: "1,388 项通过", en: "1,388 passed" } },
      { label: { zh: "审查结论", en: "Review decision" }, value: { zh: "通过", en: "Accept" } },
      { label: { zh: "总耗时", en: "Total time" }, value: { zh: "327.3 秒", en: "327.3s" } },
    ],
    milestones: [
      {
        label: { zh: "固定任务", en: "Freeze task" },
        detail: { zh: "将 HEAD 固定为 6851ab593cd2，并创建独立 Git 工作区。", en: "Resolved HEAD to 6851ab593cd2 and created a detached Git worktree." },
      },
      {
        label: { zh: "定位源码", en: "Locate source" },
        detail: { zh: "在 src/attr/_make.py::_is_class_var 中找到 ClassVar 的识别逻辑。", en: "Located ClassVar handling in src/attr/_make.py::_is_class_var." },
      },
      {
        label: { zh: "确认根因", en: "Confirm root cause" },
        detail: { zh: "Python 3.14 会返回 ForwardRef('ClassVar[str]')，而现有逻辑没有展开它。", en: "Python 3.14 returned ForwardRef('ClassVar[str]'), which existing detection did not unwrap." },
      },
      {
        label: { zh: "补充回归测试", en: "Add regression coverage" },
        detail: { zh: "新增测试在基础版本按预期失败：2 项失败、47 项通过。", en: "The new coverage failed on Base as expected: 2 failed, 47 passed." },
      },
      {
        label: { zh: "验证候选补丁", en: "Verify patch" },
        detail: { zh: "候选补丁测试通过：49 项通过，用时 0.23 秒。", en: "The candidate gate passed: 49 tests passed in 0.23s." },
      },
      {
        label: { zh: "独立审查", en: "Independent review" },
        detail: { zh: "独立 Reviewer 未发现阻断问题；扩大测试 1,388 项通过。", en: "The independent Reviewer found no blocking issue; 1,388 wider tests passed." },
      },
    ],
    review: {
      verdict: "ACCEPT",
      title: { zh: "没有阻断问题", en: "No blocking findings" },
      body: {
        zh: "改动范围小，保留普通实例属性的行为，并且直接处理 Python 3.14 的 ForwardRef 场景。公开回归测试能够证明基础版本存在该问题。",
        en: "The change is narrow, preserves ordinary instance attributes, and directly handles Python 3.14 ForwardRef values. Public regression tests demonstrate the Base failure.",
      },
    },
    evidence: [
      { name: "Task contract", meta: { zh: "需求、基础版本与策略", en: "Issue, base, and policy" }, hash: "6851ab59…2a074" },
      { name: "Fix manifest", meta: { zh: "1 次尝试，已验证", en: "1 attempt, verified" }, hash: "4df8656d…e8545ab" },
      { name: "Candidate patch", meta: { zh: "源码与测试，共 2 个文件", en: "source and test, 2 files" }, hash: "ea56a09d…ed9a" },
      { name: "Review manifest", meta: { zh: "新上下文，审查通过", en: "fresh context, accepted" }, hash: "672e8368…19ac76" },
      { name: "Sealed evaluator", meta: { zh: "审查后附加的评测", en: "attached after review" }, hash: "2aaaea18…7222e56" },
    ],
    patchText: [
      "diff --git a/src/attr/_make.py b/src/attr/_make.py",
      "@@ -297,7 +297,11 @@ def _is_class_var(annot):",
      "-    annot = str(annot)",
      "+    forward_arg = getattr(annot, \"__forward_arg__\", None)",
      "+    if forward_arg is not None:",
      "+        annot = forward_arg",
      "+    else:",
      "+        annot = str(annot)",
      "",
      "diff --git a/tests/test_annotations.py b/tests/test_annotations.py",
      "@@ -688,6 +688,7 @@",
      "+        typing.ForwardRef(\"ClassVar[int]\")",
      "@@ -698,3 +699,25 @@",
      "+def test_classvar_forward_ref_py_314():",
      "+    ...",
    ].join("\n"),
  },
  click: {
    id: "click",
    kind: "review",
    repository: "pallets/click",
    issueUrl: "https://github.com/pallets/click/issues/3145",
    evidenceUrl: "https://github.com/Suxingyeme1/prguard/tree/main/evidence/click-controlled-repair",
    baseCommit: "frozen defective candidate",
    runtime: "CPython 3.12 · Linux x86_64",
    title: {
      zh: "在绿灯测试下发现一次公共扩展点回归",
      en: "Finding a public extension regression behind green tests",
    },
    card: {
      zh: "Click 的候选重构已经通过仓库测试，但独立 Reviewer 沿调用路径发现它绕过了公开扩展点；受控修复后全量通过。",
      en: "A Click refactor passed repository tests, but an independent Reviewer traced a bypassed public extension point. A controlled repair then passed the full gate.",
    },
    issue: {
      zh: "审查默认值查询相关的候选重构。必须保留公开的 Context.lookup_default() 扩展点和现有回调语义。",
      en: "Review a candidate refactor of default lookup. Preserve the public Context.lookup_default() extension point and existing callback semantics.",
    },
    outcome: {
      zh: "Reviewer 阻止了一次回归",
      en: "Reviewer prevented a regression",
    },
    outcomeDetail: {
      zh: "预先声明的测试套件是绿的，但独立源码追踪发现候选补丁绕过了公共扩展点。一次受控修复恢复了原有契约，最终门禁通过。",
      en: "The declared suite was green, but independent source tracing found that the candidate bypassed a public extension point. One controlled repair restored the contract and passed the final gate.",
    },
    stats: [
      { label: { zh: "审查发现", en: "Review finding" }, value: { zh: "P2", en: "P2" } },
      { label: { zh: "最终测试", en: "Final tests" }, value: { zh: "1,324 项通过", en: "1,324 passed" } },
      { label: { zh: "受控修复", en: "Controlled repair" }, value: { zh: "1 次", en: "1" } },
      { label: { zh: "验证重放", en: "Test replays" }, value: { zh: "10 次", en: "10" } },
    ],
    milestones: [
      {
        label: { zh: "固定候选补丁", en: "Freeze candidate" },
        detail: { zh: "固定缺陷候选版本，并声明运行全量测试。", en: "Froze the defective candidate and declared the full-suite gate." },
      },
      {
        label: { zh: "通过初始门禁", en: "Pass initial gate" },
        detail: { zh: "候选补丁通过 1,323 项仓库测试和 9 次已变测试重放。", en: "The candidate passed 1,323 repository tests and 9 changed-test replays." },
      },
      {
        label: { zh: "定位公共路径", en: "Trace public path" },
        detail: { zh: "Reviewer 沿着 Context.lookup_default() 追踪到了公开覆写路径。", en: "The Reviewer traced Context.lookup_default() through the public override path." },
      },
      {
        label: { zh: "给出 P2 发现", en: "Report P2 finding" },
        detail: { zh: "候选补丁绕过 Context 子类的公共扩展点。", en: "The candidate bypassed the public extension point for Context subclasses." },
      },
      {
        label: { zh: "受控修复", en: "Controlled repair" },
        detail: { zh: "实现端依据冻结的发现提交了 4 处结构化修改。", en: "The Implementer received the frozen finding and submitted 4 structured edits." },
      },
      {
        label: { zh: "最终验证", en: "Final verification" },
        detail: { zh: "修复后通过 1,324 项测试和 10 次重放，恢复公开覆写路径。", en: "The repaired patch passed 1,324 tests and 10 replays, restoring the public override path." },
      },
    ],
    review: {
      verdict: "REQUEST CHANGES",
      title: { zh: "P2 · 高置信度", en: "P2 · high confidence" },
      body: {
        zh: "该重构绕过了 Context.lookup_default()，会破坏覆写该文档化扩展点的子类。可通过一个 Context 子类复现；所有默认值查询路径都应经过公开方法。",
        en: "The refactor bypasses Context.lookup_default(), breaking subclasses that override the documented extension point. Reproduce with a Context subclass and route all lookup paths through the public method.",
      },
    },
    evidence: [
      { name: "Candidate contract", meta: { zh: "缺陷 PR，初始门禁为绿", en: "defective PR, green gate" }, hash: "d35bad3b…c6d7bb" },
      { name: "Review finding", meta: { zh: "P2，已定位到源码", en: "P2, source-linked" }, hash: "1945a757…7970" },
      { name: "Repair summary", meta: { zh: "4 处结构化编辑", en: "4 structured edits" }, hash: "35b94527…a770bd" },
      { name: "Final patch", meta: { zh: "1,324 项测试通过", en: "1,324 tests passed" }, hash: "222d00a8…501c" },
      { name: "Evaluator record", meta: { zh: "基础版 → 失败 → 通过", en: "base → fail → pass" }, hash: "6d4e4e96…31a0a" },
    ],
    patchText: [
      "diff --git a/src/click/core.py b/src/click/core.py",
      "@@ public default lookup path",
      "-    value = self.default_map.get(param.name)",
      "+    value = ctx.lookup_default(param.name, call=False)",
      "",
      "diff --git a/tests/test_arguments.py b/tests/test_arguments.py",
      "+def test_context_lookup_default_override():",
      "+    \"\"\"Public Context overrides remain observable.\"\"\"",
      "+    ...",
    ].join("\n"),
  },
};
