/* Presentation-only translations. Original case data and exported evidence stay unchanged. */
(() => {
  const zh = {
    "PRGuard Studio · Verified coding workflow": "PRGuard Studio · 可验证代码修复流程",
    "PRGuard Studio home": "PRGuard Studio 首页",
    "VERIFIED CODING SYSTEM": "可验证 AI 编程系统",
    "Current environment": "当前环境",
    "Evidence replay": "真实案例回放",
    "LOCAL · READ ONLY": "只读演示",
    "Task setup": "任务设置",
    "WORKSPACE / NEW RUN": "工作区 / 案例任务",
    "Define the task": "任务说明",
    "Reset replay": "重置回放",
    "Workflow mode": "流程选择",
    "Fix": "修复",
    "Review": "审查",
    "Issue → Patch": "需求 → 补丁",
    "PR → Repair": "审查 → 修复",
    "Repository": "代码仓库",
    "Commit verified": "代码版本已核验",
    "Base commit": "基础版本",
    "Boundary": "执行环境",
    "Trusted host": "可信主机",
    "Container · unavailable": "容器 · 未启用",
    "Issue / requirement": "问题 / 需求描述",
    "Frozen verification policy": "已固定的验证规则",
    "Operator-reviewed before execution": "执行前由操作者确认",
    "argv allowlist": "命令白名单",
    "isolated worktree": "隔离工作区",
    "Replay verified run": "开始回放验证过程",
    "Replays frozen public evidence. No provider call or source write.": "回放已保存的公开证据，不调用模型或修改源码。",
    "Run progress": "执行进度",
    "READY": "就绪",
    "RUNNING": "回放中",
    "VERIFIED": "验证完成",
    "Workflow stages": "流程阶段",
    "Implementer is ready": "编程 Agent 已就绪",
    "Reviewer is ready": "审查 Agent 已就绪",
    "Independent tools · bounded context": "独立工具 · 受限上下文",
    "Start the replay to inspect every decision and verification result.": "点击开始回放，查看各步骤的处理过程与验证结果。",
    "PUBLIC GATE": "公开测试",
    "PATCH": "代码补丁",
    "REVIEW": "独立审查",
    "pytest · frozen argv": "pytest · 已固定命令",
    "Git-authored diff": "由 Git 生成差异",
    "Pending": "待执行",
    "independent context": "独立上下文",
    "Run details": "执行详情",
    "Overview": "结果概览",
    "Patch": "代码补丁",
    "Artifacts": "运行产物",
    "DELIVERY BOUNDARY": "交付记录",
    "Evidence chain": "验证证据链",
    "Recursive manifest": "完整性校验清单",
    "Waiting for run": "等待回放",
    "Facts stay separate": "各类证据分别记录",
    "Model proposals, test outcomes, review findings, and evaluator labels are recorded as different evidence.": "模型修改建议、测试结果、审查发现和独立评测结论分别保存，便于核验。",
    "Export delivery bundle": "导出交付摘要",
    "Copy diff": "复制补丁",
    "Copied": "已复制",
    "Copy unavailable": "无法复制",
    "Upstream issue ↗": "查看原始问题 ↗",
    "Public evidence ↗": "查看公开证据 ↗",
    "Review-ready patch delivered": "已交付可审查的补丁",
    "Regression repaired and verified": "回归问题已修复并通过验证",
    "All declared gates and evidence checks complete": "预设验证与证据检查已完成",
    "Accepted": "审查通过",
    "P2 repaired": "P2 问题已修复",
    "Replay again": "再次回放",
    "Replaying evidence…": "正在回放验证过程…",
    "Implementer is tracing the repository": "编程 Agent 正在定位源码",
    "Reviewer is tracing the candidate": "审查 Agent 正在分析候选补丁",
    "LIVE HOLDOUT · ATTRS #1575": "真实留出案例 · ATTRS #1575",
    "Issue to review-ready patch": "从问题描述到可审查补丁",
    "Python 3.14 turns an unimported ClassVar annotation into a ForwardRef. attrs treats it as an instance field and generates an incorrect required constructor argument.": "Python 3.14 将未导入的 ClassVar 类型注解转为 ForwardRef 对象。attrs 误把它识别为实例字段，导致构造函数多出一个不应存在的必填参数。",
    "Freeze": "固定任务",
    "Task + commit": "任务 + 代码版本",
    "Locate": "定位源码",
    "24 tool calls": "24 次工具调用",
    "2 files": "2 个文件",
    "Verify": "执行验证",
    "Accept": "通过",
    "Deliver": "交付结果",
    "Manifest": "校验清单",
    "PREPARE": "准备",
    "SEARCH": "检索",
    "TRACE": "追踪",
    "EDIT": "编辑",
    "BASE": "基础版本",
    "GATE": "验证",
    "EVALUATOR": "独立评测",
    "DELIVER": "交付",
    "Resolved HEAD to 6851ab593cd2 and created a detached worktree.": "将 HEAD 固定为 6851ab593cd2，并创建独立 Git 工作区。",
    "Found ClassVar detection in src/attr/_make.py::_is_class_var.": "在 src/attr/_make.py::_is_class_var 中找到 ClassVar 识别逻辑。",
    "Python 3.14 returns ForwardRef('ClassVar[str]') for the missing runtime import.": "Python 3.14 在运行时缺少导入的情况下返回 ForwardRef('ClassVar[str]')。",
    "Unwrap __forward_arg__ before the existing ClassVar prefix check.": "在原有 ClassVar 前缀判断之前，先提取 __forward_arg__ 的内容。",
    "Agent-authored tests failed as expected · 2 failed, 47 passed.": "Agent 新增的测试在基础版本上按预期失败：2 项失败，47 项通过。",
    "Candidate verification passed · 49 passed in 0.23s.": "候选补丁验证通过：49 项测试通过，用时 0.23 秒。",
    "Independent Reviewer accepted · 0 blocking findings.": "独立审查通过，未发现需要阻止交付的问题。",
    "Precommitted sealed evaluator passed · no new regression.": "预先固定的隐藏评测通过，未发现新增回归。",
    "Review-ready Patch and recursive SHA-256 Manifest frozen.": "保存可审查补丁及递归 SHA-256 校验清单。",
    "Task contract": "任务约定",
    "Issue + Base + policy": "需求 + 基础版本 + 规则",
    "Fix manifest": "修复校验清单",
    "1 attempt · verified": "1 次尝试 · 已验证",
    "Candidate patch": "候选补丁",
    "2 files · source + test": "2 个文件 · 源码与测试",
    "Review manifest": "审查校验清单",
    "fresh context · accept": "独立上下文 · 通过",
    "Sealed evaluator": "隐藏评测",
    "attached after review": "审查结束后执行",
    "Resolved in one attempt": "一次尝试完成修复",
    "The Implementer located the compatibility boundary, added FAIL_TO_PASS coverage, and produced a minimal patch. Independent Review accepted the exact verified diff; the hidden evaluator passed after both agent artifacts were frozen.": "编程 Agent 找到兼容性问题，补充了修复前失败、修复后通过的测试，并生成最小补丁。独立审查通过；两个 Agent 的运行记录保存后，隐藏评测也通过。",
    "Duration": "耗时",
    "136.8s + 190.5s review": "修复 136.8 秒 · 审查 190.5 秒",
    "Tool budget": "工具额度",
    "24 implementer · 12 reviewer": "编程 24 次 · 审查 12 次",
    "Wider suite": "扩大测试范围",
    "1,388 passed · 0 new failures": "1,388 项通过 · 无新增失败",
    "ACCEPT": "通过",
    "No blocking findings": "未发现阻断问题",
    "The change is narrow, preserves ordinary instance attributes, and directly addresses Python 3.14 ForwardRef handling. Public regression tests demonstrate the failure on Base.": "改动范围小，保留了普通实例属性的行为，并直接修复 Python 3.14 的 ForwardRef 处理逻辑。公开回归测试已证实基础版本存在该问题。",
    "DEFECTIVE PR · CLICK #3199": "缺陷 PR 案例 · CLICK #3199",
    "Review, find regression, repair": "审查发现回归，再完成修复",
    "frozen defective candidate": "已固定的缺陷候选版本",
    "Review a candidate refactor of default lookup. Preserve the public Context.lookup_default() extension point and existing callback semantics.": "审查一份重构默认值查询逻辑的候选补丁。需要保留公开的 Context.lookup_default() 扩展入口及原有回调行为。",
    "controlled repair · verified": "受控修复 · 已验证",
    "PR + commit": "PR + 代码版本",
    "P2 finding": "发现 P2 问题",
    "Repair": "受控修复",
    "4 edits": "4 处编辑",
    "Re-verify": "再次验证",
    "P2 FINDING": "P2 问题",
    "REPAIR": "修复",
    "BASE/CANDIDATE": "版本对照",
    "FINAL GATE": "最终验证",
    "Frozen the exact candidate and declared full-suite gate.": "固定候选补丁，并预设全量测试命令。",
    "Candidate passed 1,323 repository tests and 9 changed-test replays.": "候选补丁通过 1,323 项仓库测试及 9 项变更测试复验。",
    "Reviewer followed Context.lookup_default() through the public override path.": "审查 Agent 沿公开方法的重写路径追踪 Context.lookup_default()。",
    "Candidate bypasses the public extension point for Context subclasses.": "发现候选补丁绕过了 Context 子类的公开扩展入口。",
    "Implementer received the frozen finding and submitted 4 structured edits.": "编程 Agent 收到已保存的审查发现，提交 4 处结构化编辑。",
    "Hidden check: Base passes, defective candidate fails.": "隐藏评测对照：基础版本通过，缺陷候选版本失败。",
    "Repaired patch passed 1,324 tests and 10 changed-test replays.": "修复后的补丁通过 1,324 项测试及 10 项变更测试复验。",
    "Repaired candidate restored the public override path.": "修复后的候选版本恢复了公开方法的重写路径。",
    "Controlled repair and nested manifests frozen.": "保存受控修复记录及嵌套校验清单。",
    "Candidate contract": "候选版本约定",
    "defective PR · green gate": "缺陷 PR · 公开测试通过",
    "Review finding": "审查发现",
    "P2 · source linked": "P2 · 已关联源码",
    "Repair summary": "修复摘要",
    "4 structured edits": "4 处结构化编辑",
    "Final patch": "最终补丁",
    "1,324 tests passed": "1,324 项测试通过",
    "Evaluator record": "独立评测记录",
    "base → fail → pass": "基础版通过 → 缺陷版失败 → 修复版通过",
    "Reviewer prevented a regression": "独立审查发现并促成回归修复",
    "The declared test suite was green, but independent source tracing found that the candidate bypassed a public extension point. One controlled repair restored the contract and passed the final gate.": "预设测试全部通过，但独立源码追踪发现候选补丁绕过了公开扩展入口。经过一次受控修复，原有行为恢复，最终验证通过。",
    "Finding": "发现问题",
    "P2 · public extension regression": "P2 · 公开扩展入口回归",
    "1 bounded replacement patch": "1 次受控补丁替换",
    "Final gate": "最终验证",
    "1,324 passed + 10 replays": "1,324 项通过 + 10 项复验",
    "REQUEST CHANGES": "需要修改",
    "P2 · high confidence": "P2 · 高置信度",
    "The refactor bypasses Context.lookup_default(), breaking subclasses that override the documented extension point. Reproduce with a Context subclass and route all lookup paths through the public method.": "重构绕过了 Context.lookup_default()，破坏了重写该公开扩展入口的子类行为。可用 Context 子类复现，并将所有查询路径改为经过该公开方法。"
  };

  let language = "zh";
  try {
    if (localStorage.getItem("prguard-language") === "en") language = "en";
  } catch { /* Storage restrictions must not prevent language switching. */ }
  const originals = new WeakMap();
  const selector = document.querySelector("#language-select");

  function translate(text) {
    if (language === "en") return text;
    const trimmed = text.trim();
    let translated = zh[trimmed];
    if (!translated) {
      const match = trimmed.match(/^([\d,]+) (passed|ready|changed files)$/);
      if (match) translated = `${match[1]} ${ { passed: "项通过", ready: "项待验证", "changed files": "个变更文件" }[match[2]] }`;
    }
    return translated ? text.replace(trimmed, translated) : text;
  }

  // Remember original text per node so switches are reversible, including newly rendered logs.
  function update(node, property, read, write) {
    let entries = originals.get(node);
    if (!entries) { entries = {}; originals.set(node, entries); }
    const current = read();
    const previous = entries[property];
    const source = previous && current === previous.rendered ? previous.source : current;
    const rendered = translate(source);
    entries[property] = { source, rendered };
    if (current !== rendered) write(rendered);
  }

  function renderLanguage() {
    observer.disconnect();
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    selector.value = language;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.parentElement.closest("script, style, code, pre, #language-select")) continue;
      update(node, "text", () => node.nodeValue, value => { node.nodeValue = value; });
    }
    document.querySelectorAll("[aria-label], [title]").forEach(node => {
      for (const attribute of ["aria-label", "title"]) {
        if (node.hasAttribute(attribute)) update(node, attribute, () => node.getAttribute(attribute), value => node.setAttribute(attribute, value));
      }
    });
    for (const id of ["issue", "base-commit"]) {
      const node = document.getElementById(id);
      update(node, "value", () => node.value, value => { node.value = value; });
    }
    document.title = translate("PRGuard Studio · Verified coding workflow");
    observer.observe(document.body, { subtree: true, childList: true, characterData: true });
  }

  const observer = new MutationObserver(renderLanguage);
  selector.addEventListener("change", () => {
    language = selector.value === "en" ? "en" : "zh";
    try { localStorage.setItem("prguard-language", language); } catch { /* In-memory fallback. */ }
    renderLanguage();
  });
  renderLanguage();
})();
