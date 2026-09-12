(() => {
  const root = document.getElementById("app");
  const locale = window.PRGuardLocale;
  const recordedCases = window.PRGuardCases;
  const live = window.PRGuardLive;
  const t = (...args) => locale.t(...args);

  const state = {
    view: "workspace",
    exampleId: null,
    exampleTab: "summary",
    resultTab: "summary",
    contractExpanded: false,
    contractConfirmed: false,
    copyStatus: null,
    draft: { issue: "", baseCommit: "HEAD" },
    live: live.getState(),
  };

  const eventLabels = {
    "preparation.started": "eventPreparationStarted",
    "preparation.completed": "eventPreparationCompleted",
    "run.started": "eventRunStarted",
    "preflight.started": "eventPreflightStarted",
    "preflight.completed": "eventPreflightCompleted",
    "readiness.started": "eventReadinessStarted",
    "readiness.completed": "eventReadinessCompleted",
    "attempt.started": "eventAttemptStarted",
    "proposal.completed": "eventProposalCompleted",
    "verification.started": "eventVerificationStarted",
    "verification.completed": "eventVerificationCompleted",
    "repair.requested": "eventRepairRequested",
    "attempt.failed": "eventAttemptFailed",
    "run.completed": "eventRunCompleted",
    "delivery.completed": "eventDeliveryCompleted",
    "adapter.failed": "eventAdapterFailed",
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function localized(value) {
    if (!value || typeof value !== "object") return String(value ?? "");
    return value[locale.language] || value.en || value.zh || "";
  }

  function externalUrl(value) {
    try {
      const url = new URL(value);
      return url.protocol === "https:" ? url.href : "#";
    } catch {
      return "#";
    }
  }

  function statusLabel(value) {
    return t({
      preparing: "statusPreparing",
      ready: "statusReady",
      running: "statusRunning",
      completed: "statusCompleted",
      error: "statusError",
    }[value] || "unknown");
  }

  function formatDuration(value) {
    const seconds = Number(value);
    if (!Number.isFinite(seconds)) return t("unknown");
    if (seconds >= 60) return t("minutes", { value: (seconds / 60).toFixed(1) });
    return t("seconds", { value: seconds.toFixed(1) });
  }

  function command(argv) {
    return Array.isArray(argv) ? argv.join(" ") : "";
  }

  function classForOutcome(outcome) {
    return outcome === "accepted" || outcome === "passed" ? "is-success" : "is-danger";
  }

  function renderShell(content) {
    const connected = state.live.availability === "local" && state.live.connection === "connected";
    document.title = t("pageTitle");
    root.innerHTML = `
      <header class="app-header">
        <a class="brand" href="#" data-action="home" aria-label="PRGuard Studio">
          <span class="brand-mark" aria-hidden="true">P</span>
          <span class="brand-name">PRGuard</span>
          <span class="brand-tagline">${escapeHtml(t("brandTagline"))}</span>
        </a>
        <nav class="primary-nav" aria-label="Primary navigation">
          <button class="nav-link ${state.view === "workspace" ? "is-active" : ""}" type="button" data-view="workspace" aria-current="${state.view === "workspace" ? "page" : "false"}">${escapeHtml(t("navWorkspace"))}</button>
          <button class="nav-link ${state.view === "examples" ? "is-active" : ""}" type="button" data-view="examples" aria-current="${state.view === "examples" ? "page" : "false"}">${escapeHtml(t("navExamples"))}</button>
        </nav>
        <div class="header-actions">
          <span class="connection-status ${connected ? "is-live" : ""}">
            <span aria-hidden="true"></span>${escapeHtml(connected ? t("connectionLive") : t("connectionStatic"))}
          </span>
          <label class="language-control">
            <span class="sr-only">${escapeHtml(t("language"))}</span>
            <select data-action="language" aria-label="${escapeHtml(t("language"))}">
              <option value="zh" ${locale.language === "zh" ? "selected" : ""}>中文</option>
              <option value="en" ${locale.language === "en" ? "selected" : ""}>English</option>
            </select>
          </label>
          <a class="header-link" href="https://github.com/Suxingyeme1/prguard" target="_blank" rel="noreferrer">${escapeHtml(t("navGitHub"))}<span aria-hidden="true">↗</span></a>
        </div>
      </header>
      <main class="app-main">${content}</main>
    `;
  }

  function renderWelcome() {
    const steps = [
      ["01", "homeStepOneTitle", "homeStepOneCopy"],
      ["02", "homeStepTwoTitle", "homeStepTwoCopy"],
      ["03", "homeStepThreeTitle", "homeStepThreeCopy"],
      ["04", "homeStepFourTitle", "homeStepFourCopy"],
    ];
    return `
      <section class="home-hero">
        <div class="hero-copy">
          <p class="eyebrow">${escapeHtml(t("homeEyebrow"))}</p>
          <h1>${escapeHtml(t("homeTitle"))}</h1>
          <p class="hero-lead">${escapeHtml(t("homeLead"))}</p>
          <div class="hero-actions">
            <button class="button button-primary" type="button" data-action="copy-start">${escapeHtml(state.copyStatus === "start" ? t("copied") : t("copyStart"))}</button>
            <button class="button button-secondary" type="button" data-view="examples">${escapeHtml(t("viewExamples"))}</button>
          </div>
          <p class="hero-note"><span aria-hidden="true">•</span>${escapeHtml(t("homeNote"))}</p>
        </div>
        <aside class="start-card" aria-label="Local Studio command">
          <p class="card-kicker">${escapeHtml(t("liveStartTitle"))}</p>
          <p>${escapeHtml(t("liveStartCopy"))}</p>
          <div class="command-box"><code>uv run --no-editable --extra demo prguard studio</code><button type="button" data-action="copy-start" aria-label="${escapeHtml(t("copyStart"))}">⧉</button></div>
          <p class="start-card-note">${escapeHtml(t("homeDemoCopy"))}</p>
        </aside>
      </section>
      <section class="home-section">
        <div class="section-heading">
          <h2>${escapeHtml(t("homeHowTitle"))}</h2>
        </div>
        <ol class="step-grid">
          ${steps.map(([index, title, body]) => `
            <li>
              <span class="step-number">${index}</span>
              <h3>${escapeHtml(t(title))}</h3>
              <p>${escapeHtml(t(body))}</p>
            </li>
          `).join("")}
        </ol>
      </section>
      <section class="boundary-card">
        <div class="boundary-icon" aria-hidden="true">✓</div>
        <div>
          <h2>${escapeHtml(t("homeBoundaryTitle"))}</h2>
          <p>${escapeHtml(t("homeBoundaryCopy"))}</p>
        </div>
      </section>
    `;
  }

  function renderLocalStart() {
    return `
      <section class="connection-empty">
        <p class="eyebrow">${escapeHtml(t("taskEyebrow"))}</p>
        <h1>${escapeHtml(t("liveStartTitle"))}</h1>
        <p>${escapeHtml(t("liveStartCopy"))}</p>
        <div class="command-box command-box-large"><code>uv run --no-editable --extra demo prguard studio</code><button type="button" data-action="copy-start" aria-label="${escapeHtml(t("copyStart"))}">⧉</button></div>
        <p class="muted">${escapeHtml(t("liveStartOwn"))}</p>
      </section>
    `;
  }

  function renderTaskForm(session) {
    const localRepository = Boolean(session.repository);
    const repository = localRepository ? session.repository : t("taskDemoLabel");
    const boundary = localRepository ? session.boundary : "fixture";
    const provider = localRepository ? session.provider : "scripted";
    const actionPending = state.live.action === "prepare";
    return `
      <section class="task-layout">
        <div class="task-main">
          <div class="page-heading">
            <div>
              <p class="eyebrow">${escapeHtml(t("taskEyebrow"))}</p>
              <h1>${escapeHtml(t("taskTitle"))}</h1>
              <p>${escapeHtml(t("taskLead"))}</p>
            </div>
          </div>
          <form class="task-form card" data-form="prepare">
            <label for="task-issue">${escapeHtml(t("taskIssue"))}</label>
            <textarea id="task-issue" name="issue" rows="8" maxlength="50000" required placeholder="${escapeHtml(t("taskIssueHint"))}">${escapeHtml(localRepository ? state.draft.issue : session.demo_issue || "")}</textarea>
            <p class="field-hint">${escapeHtml(localRepository ? t("taskIssueHint") : t("taskDemoCopy"))}</p>
            <div class="field-row">
              <div>
                <label for="task-base">${escapeHtml(t("taskBase"))}</label>
                <input id="task-base" name="baseCommit" value="${escapeHtml(state.draft.baseCommit || "HEAD")}" maxlength="128" required />
                <p class="field-hint">${escapeHtml(t("taskBaseHint"))}</p>
              </div>
            </div>
            <button class="button button-primary" type="submit" ${actionPending ? "disabled" : ""}>
              ${escapeHtml(actionPending ? t("taskPreparing") : t("taskPrepare"))}
            </button>
          </form>
          ${state.live.error ? renderInlineError(state.live.error) : ""}
        </div>
        <aside class="workspace-receipt card">
          <p class="card-kicker">${escapeHtml(t("details"))}</p>
          <dl>
            <div><dt>${escapeHtml(t("taskRepository"))}</dt><dd><code>${escapeHtml(repository)}</code></dd></div>
            <div><dt>${escapeHtml(t("taskEnvironment"))}</dt><dd>${escapeHtml(boundary)}</dd></div>
            <div><dt>${escapeHtml(t("taskProvider"))}</dt><dd><code>${escapeHtml(provider)}</code></dd></div>
          </dl>
          <p>${escapeHtml(t("homeBoundaryCopy"))}</p>
        </aside>
      </section>
    `;
  }

  function pillList(paths) {
    return paths.map(path => `<code class="path-pill">${escapeHtml(path)}</code>`).join("");
  }

  function renderContract(preview) {
    const actionPending = state.live.action === "approve";
    const compactDetails = [
      [t("contractIssue"), preview.issue],
      [t("contractBase"), preview.base_commit],
      [t("taskEnvironment"), preview.boundary],
      [t("taskProvider"), preview.provider],
    ];
    return `
      <section class="contract-layout">
        <div class="task-main">
          <div class="page-heading">
            <div>
              <p class="eyebrow">${escapeHtml(t("taskContractEyebrow"))}</p>
              <h1>${escapeHtml(t("taskContractTitle"))}</h1>
              <p>${escapeHtml(t("taskContractLead"))}</p>
            </div>
            <span class="status-badge is-ready">${escapeHtml(t("statusReady"))}</span>
          </div>
          <section class="card contract-card">
            <dl class="contract-summary">
              ${compactDetails.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}
            </dl>
            <div class="contract-policy-grid">
              <article><span>${escapeHtml(t("contractCommands"))}</span><div>${preview.commands.map(argv => `<code>${escapeHtml(command(argv))}</code>`).join("")}</div></article>
              <article><span>${escapeHtml(t("contractWritable"))}</span><div class="pill-list">${pillList(preview.writable_paths)}</div></article>
              <article><span>${escapeHtml(t("contractProtected"))}</span><div class="pill-list">${pillList(preview.protected_paths)}</div></article>
            </div>
            <button class="text-button" type="button" data-action="toggle-contract" aria-expanded="${state.contractExpanded}">
              ${escapeHtml(state.contractExpanded ? t("contractHideAll") : t("contractShowAll"))} <span aria-hidden="true">⌄</span>
            </button>
            ${state.contractExpanded ? `
              <dl class="contract-full">
                <div><dt>${escapeHtml(t("contractLimit"))}</dt><dd>${escapeHtml(t("seconds", { value: preview.task_timeout_seconds }))}</dd></div>
                <div><dt>${escapeHtml(t("contractAttempts"))}</dt><dd>${escapeHtml(String(preview.max_repair_attempts))}</dd></div>
                <div><dt>Task SHA-256</dt><dd><code>${escapeHtml(preview.task_sha256)}</code></dd></div>
              </dl>
            ` : ""}
          </section>
          <form class="approval-form" data-form="approve">
            <label class="checkbox-line"><input id="contract-confirm" type="checkbox" required ${state.contractConfirmed ? "checked" : ""}/><span>${escapeHtml(t("contractConfirm"))}</span></label>
            <p class="field-hint">${escapeHtml(t("contractSafety"))}</p>
            <button class="button button-primary" type="submit" ${actionPending ? "disabled" : ""}>${escapeHtml(actionPending ? t("contractRunning") : t("contractRun"))}</button>
          </form>
          ${state.live.error ? renderInlineError(state.live.error) : ""}
        </div>
      </section>
    `;
  }

  function eventDescription(event) {
    return t(eventLabels[event.event] || "unknownEvent");
  }

  function eventData(event) {
    const entries = Object.entries(event.data || {});
    if (!entries.length) return "";
    return `<details class="event-details"><summary>${escapeHtml(t("runRawEvent"))}</summary><pre>${escapeHtml(JSON.stringify(event.data, null, 2))}</pre></details>`;
  }

  function renderRunning(run) {
    const events = run.events || [];
    const latest = events.at(-1);
    return `
      <section class="run-layout">
        <div class="page-heading run-heading">
          <div>
            <p class="eyebrow">${escapeHtml(t("runEyebrow"))}</p>
            <h1>${escapeHtml(t("runTitle"))}</h1>
            <p>${escapeHtml(t("runLead"))}</p>
          </div>
          <span class="status-badge is-running"><span class="status-spinner" aria-hidden="true"></span>${escapeHtml(t("statusRunning"))}</span>
        </div>
        <section class="current-stage card">
          <span class="card-kicker">${escapeHtml(t("runCurrent"))}</span>
          <strong>${escapeHtml(latest ? eventDescription(latest) : t("runWaiting"))}</strong>
          <span>${escapeHtml(latest ? formatDuration(latest.elapsed) : t("runNoEvents"))}</span>
        </section>
        ${state.live.connection === "degraded" ? renderConnectionWarning() : ""}
        <section class="event-panel card">
          <div class="section-heading"><h2>${escapeHtml(t("runEvents"))}</h2><span>${events.length}</span></div>
          ${events.length ? `<ol class="event-list">${events.map(event => `
            <li>
              <span class="event-dot" aria-hidden="true"></span>
              <div><strong>${escapeHtml(eventDescription(event))}</strong><small>${escapeHtml(formatDuration(event.elapsed))}</small>${eventData(event)}</div>
            </li>
          `).join("")}</ol>` : `<p class="empty-copy">${escapeHtml(t("runNoEvents"))}</p>`}
        </section>
      </section>
    `;
  }

  function extractCommands(result) {
    return (result.attempts || []).flatMap(attempt => (attempt.commands || []).map(commandResult => ({
      ...commandResult,
      attempt: attempt.attempt,
    })));
  }

  function renderAttemptSummary(attempt) {
    const passed = attempt.outcome === "passed";
    return `
      <article class="attempt-card">
        <div><h3>${escapeHtml(t("resultAttempt", { number: attempt.attempt }))}</h3><span class="outcome-pill ${passed ? "is-success" : "is-danger"}">${escapeHtml(passed ? t("resultPassed") : t("resultFailed"))}</span></div>
        <p>${escapeHtml(attempt.summary || attempt.error || t("unknown"))}</p>
        ${attempt.plan?.length ? `<ol>${attempt.plan.map(step => `<li>${escapeHtml(step)}</li>`).join("")}</ol>` : ""}
      </article>
    `;
  }

  function renderResultTab(result) {
    const tab = state.resultTab;
    const commands = extractCommands(result);
    if (tab === "changes") {
      return result.patch
        ? `<div class="code-card"><div class="code-toolbar"><span>diff</span><button class="text-button" type="button" data-action="copy-live-patch">${escapeHtml(state.copyStatus === "patch" ? t("patchCopied") : t("copyPatch"))}</button></div><pre><code>${escapeHtml(result.patch)}</code></pre></div>`
        : `<p class="empty-copy">${escapeHtml(t("resultNoPatch"))}</p>`;
    }
    if (tab === "verification") {
      return `<div class="verification-list">${commands.map(item => `
        <article class="verification-item">
          <div><strong><code>${escapeHtml(command(item.argv))}</code></strong><span class="outcome-pill ${item.passed ? "is-success" : "is-danger"}">${escapeHtml(item.timed_out ? t("resultTimeout") : item.passed ? t("resultCommandPassed") : t("resultCommandFailed"))}</span></div>
          <p>${escapeHtml(t("resultAttempt", { number: item.attempt }))} · exit ${escapeHtml(item.exit_code)} · ${escapeHtml(formatDuration(item.duration_seconds))}</p>
          <details ${item.passed ? "" : "open"}><summary>${escapeHtml(t("details"))}</summary><pre>${escapeHtml([item.stdout, item.stderr].filter(Boolean).join("\n"))}</pre></details>
        </article>
      `).join("")}</div>`;
    }
    if (tab === "evidence") {
      return `
        <div class="artifact-list">
          ${(result.artifacts || []).map(file => `
            <article><div><strong>${escapeHtml(file.name)}</strong><code>${escapeHtml(file.sha256)}</code></div><button class="button button-secondary button-small" type="button" data-artifact="${escapeHtml(file.name)}">${escapeHtml(t("resultDownload"))}</button></article>
          `).join("")}
        </div>
        <div class="artifact-path"><span>${escapeHtml(t("resultArtifactPath"))}</span><code>${escapeHtml(result.artifact_directory)}</code></div>
      `;
    }
    return `
      <div class="result-summary">
        <div class="result-boundary"><div class="boundary-icon" aria-hidden="true">i</div><div><strong>${escapeHtml(t("resultReviewBoundaryTitle"))}</strong><p>${escapeHtml(t("resultReviewBoundaryCopy"))}</p></div></div>
        <div class="attempt-list">${(result.attempts || []).map(renderAttemptSummary).join("")}</div>
      </div>
    `;
  }

  function renderResult(run) {
    const result = run.result || {};
    const success = result.outcome === "accepted";
    const commands = extractCommands(result);
    const tabs = [
      ["summary", "resultSummary"],
      ["changes", "resultChanges"],
      ["verification", "resultVerification"],
      ["evidence", "resultEvidence"],
    ];
    return `
      <section class="result-layout">
        <div class="result-banner ${success ? "is-success" : "is-danger"}">
          <div>
            <p class="eyebrow">${escapeHtml(t(success ? "resultSuccessEyebrow" : "resultFailureEyebrow"))}</p>
            <h1>${escapeHtml(t(success ? "resultSuccessTitle" : "resultFailureTitle"))}</h1>
            <p>${escapeHtml(t("resultLead"))}</p>
          </div>
          <button class="button button-secondary" type="button" data-action="new-task">${escapeHtml(t("resultNewTask"))}</button>
        </div>
        <section class="result-stats">
          <article><span>${escapeHtml(t("resultAttempts"))}</span><strong>${escapeHtml(String((result.attempts || []).length))}</strong></article>
          <article><span>${escapeHtml(t("resultDuration"))}</span><strong>${escapeHtml(formatDuration(result.duration_seconds))}</strong></article>
          <article><span>${escapeHtml(t("resultCommands"))}</span><strong>${escapeHtml(String(commands.length))}</strong></article>
          <article><span>${escapeHtml(t("resultManifest"))}</span><strong>${escapeHtml(String((result.artifacts || []).length))}</strong></article>
        </section>
        <section class="result-detail card">
          <div class="tabs" role="tablist" aria-label="Run result">
            ${tabs.map(([key, label]) => `<button class="tab ${state.resultTab === key ? "is-active" : ""}" role="tab" type="button" data-result-tab="${key}" aria-selected="${state.resultTab === key}">${escapeHtml(t(label))}</button>`).join("")}
          </div>
          <div class="tab-panel">${renderResultTab(result)}</div>
        </section>
        ${state.live.error ? renderInlineError(state.live.error) : ""}
      </section>
    `;
  }

  function renderError(run) {
    return `
      <section class="error-layout">
        <div class="error-card card">
          <p class="eyebrow">${escapeHtml(t("errorEyebrow"))}</p>
          <h1>${escapeHtml(t("errorTitle"))}</h1>
          <p>${escapeHtml(t("errorLead"))}</p>
          <pre class="error-message">${escapeHtml(run.error || state.live.error || t("unknown"))}</pre>
          <div class="hero-actions">
            <button class="button button-primary" type="button" data-action="new-task">${escapeHtml(t("errorTryAgain"))}</button>
            <button class="button button-secondary" type="button" data-action="reconnect">${escapeHtml(t("errorReconnect"))}</button>
          </div>
        </div>
      </section>
    `;
  }

  function renderConnectionWarning() {
    return `<div class="connection-warning" role="status"><div><strong>${escapeHtml(t("runReconnect"))}</strong><p>${escapeHtml(state.live.error || t("unknown"))}</p></div><button class="button button-secondary button-small" type="button" data-action="reconnect">${escapeHtml(t("runReconnect"))}</button></div>`;
  }

  function renderInlineError(message) {
    return `<div class="inline-error" role="alert">${escapeHtml(message)}</div>`;
  }

  function renderLiveWorkspace() {
    if (state.live.availability === "static") return renderWelcome();
    if (!state.live.session) return renderLocalStart();
    const run = state.live.snapshot;
    if (!run) return renderTaskForm(state.live.session);
    if (run.state === "ready") return renderContract(run.preview);
    if (run.state === "preparing" || run.state === "running") return renderRunning(run);
    if (run.state === "completed") return renderResult(run);
    return renderError(run);
  }

  function renderExampleCard(item) {
    const type = item.kind === "review" ? t("exampleTypeReview") : t("exampleTypeFix");
    return `
      <article class="example-card">
        <div class="example-card-top"><span class="recorded-pill">${escapeHtml(t("exampleRecorded"))}</span><code>${escapeHtml(type)}</code></div>
        <h2>${escapeHtml(localized(item.title))}</h2>
        <p>${escapeHtml(localized(item.card))}</p>
        <div class="example-repository"><span aria-hidden="true">⌘</span><code>${escapeHtml(item.repository)}</code></div>
        <div class="example-card-footer"><span>${escapeHtml(localized(item.outcome))}</span><button class="text-button" type="button" data-action="open-example" data-case="${escapeHtml(item.id)}">${escapeHtml(t("openExample"))} <span aria-hidden="true">→</span></button></div>
      </article>
    `;
  }

  function renderExamplesList() {
    return `
      <section class="examples-page">
        <div class="page-heading narrow-heading">
          <p class="eyebrow">${escapeHtml(t("exampleEyebrow"))}</p>
          <h1>${escapeHtml(t("examplesTitle"))}</h1>
          <p>${escapeHtml(t("examplesLead"))}</p>
        </div>
        <div class="example-grid">${Object.values(recordedCases).map(renderExampleCard).join("")}</div>
      </section>
    `;
  }

  function renderCaseTabs(item) {
    const tab = state.exampleTab;
    if (tab === "trace") {
      return `
        <section><h2 class="detail-title">${escapeHtml(t("exampleRecordedSteps"))}</h2>
          <ol class="recorded-timeline">${item.milestones.map((step, index) => `
            <li><span>${String(index + 1).padStart(2, "0")}</span><div><strong>${escapeHtml(localized(step.label))}</strong><p>${escapeHtml(localized(step.detail))}</p></div></li>
          `).join("")}</ol>
        </section>
      `;
    }
    if (tab === "patch") {
      return `<div class="code-card"><div class="code-toolbar"><span>diff</span><button class="text-button" type="button" data-action="copy-example-patch">${escapeHtml(state.copyStatus === "example-patch" ? t("patchCopied") : t("copyPatch"))}</button></div><pre><code>${escapeHtml(item.patchText)}</code></pre></div>`;
    }
    if (tab === "review") {
      const needsChange = item.review.verdict !== "ACCEPT";
      return `<section class="review-card ${needsChange ? "is-request" : "is-accept"}"><span class="outcome-pill ${needsChange ? "is-danger" : "is-success"}">${escapeHtml(item.review.verdict)}</span><h2>${escapeHtml(localized(item.review.title))}</h2><p>${escapeHtml(localized(item.review.body))}</p></section>`;
    }
    if (tab === "evidence") {
      return `<section><p class="tab-intro">${escapeHtml(t("exampleEvidenceIntro"))}</p><div class="evidence-file-list">${item.evidence.map(file => `<article><div><strong>${escapeHtml(file.name)}</strong><p>${escapeHtml(localized(file.meta))}</p></div><code>${escapeHtml(file.hash)}</code></article>`).join("")}</div></section>`;
    }
    return `
      <section class="example-summary">
        <div><h2>${escapeHtml(t("exampleWhatHappened"))}</h2><p>${escapeHtml(localized(item.outcomeDetail))}</p><p class="case-issue">${escapeHtml(localized(item.issue))}</p></div>
        <dl><div><dt>Base</dt><dd><code>${escapeHtml(item.baseCommit)}</code></dd></div><div><dt>Runtime</dt><dd>${escapeHtml(item.runtime)}</dd></div><div><dt>Repository</dt><dd><code>${escapeHtml(item.repository)}</code></dd></div></dl>
      </section>
    `;
  }

  function renderExampleDetail(item) {
    const tabs = [
      ["summary", "exampleSummary"],
      ["trace", "exampleTrace"],
      ["patch", "examplePatch"],
      ["review", "exampleReview"],
      ["evidence", "exampleEvidence"],
    ];
    return `
      <section class="example-detail">
        <button class="back-link" type="button" data-action="close-example">← ${escapeHtml(t("exampleBack"))}</button>
        <div class="case-heading">
          <div><p class="eyebrow">${escapeHtml(t("exampleRecorded"))}</p><h1>${escapeHtml(localized(item.title))}</h1><p>${escapeHtml(localized(item.card))}</p></div>
          <span class="recorded-pill">${escapeHtml(t("exampleRecorded"))}</span>
        </div>
        <div class="case-fact-bar">${item.stats.map(stat => `<article><span>${escapeHtml(localized(stat.label))}</span><strong>${escapeHtml(localized(stat.value))}</strong></article>`).join("")}</div>
        <div class="recording-notice"><span aria-hidden="true">i</span>${escapeHtml(t("exampleNoModel"))}</div>
        <section class="case-detail-card card">
          <div class="tabs" role="tablist" aria-label="Recorded run">
            ${tabs.map(([key, label]) => `<button class="tab ${state.exampleTab === key ? "is-active" : ""}" type="button" role="tab" data-example-tab="${key}" aria-selected="${state.exampleTab === key}">${escapeHtml(t(label))}</button>`).join("")}
          </div>
          <div class="tab-panel">${renderCaseTabs(item)}</div>
        </section>
        <div class="case-actions">
          <a class="button button-secondary" href="${escapeHtml(externalUrl(item.issueUrl))}" target="_blank" rel="noreferrer">${escapeHtml(t("exampleSourceIssue"))} ↗</a>
          <a class="button button-secondary" href="${escapeHtml(externalUrl(item.evidenceUrl))}" target="_blank" rel="noreferrer">${escapeHtml(t("examplePublicEvidence"))} ↗</a>
          <button class="button button-secondary" type="button" data-action="download-example">${escapeHtml(t("exampleDownload"))}</button>
        </div>
      </section>
    `;
  }

  function renderExamples() {
    const item = state.exampleId ? recordedCases[state.exampleId] : null;
    return item ? renderExampleDetail(item) : renderExamplesList();
  }

  function render() {
    const content = state.view === "examples" ? renderExamples() : renderLiveWorkspace();
    renderShell(content);
  }

  async function copy(value, status) {
    try {
      await navigator.clipboard.writeText(value);
      state.copyStatus = status;
    } catch {
      state.copyStatus = "failed";
    }
    render();
    window.setTimeout(() => {
      if (state.copyStatus === status || state.copyStatus === "failed") {
        state.copyStatus = null;
        render();
      }
    }, 1700);
  }

  function downloadExample(item) {
    const payload = {
      case: item.id,
      repository: item.repository,
      base_commit: item.baseCommit,
      issue_url: item.issueUrl,
      evidence_url: item.evidenceUrl,
      evidence: item.evidence,
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "prguard-" + item.id + "-record.json";
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  root.addEventListener("click", async event => {
    const target = event.target instanceof Element ? event.target.closest("button, a") : null;
    if (!target) return;
    const view = target.getAttribute("data-view");
    if (view) {
      event.preventDefault();
      state.view = view;
      state.exampleId = null;
      render();
      return;
    }
    const action = target.getAttribute("data-action");
    if (!action && target.hasAttribute("data-artifact")) {
      event.preventDefault();
      try {
        await live.download(target.getAttribute("data-artifact"));
      } catch (error) {
        state.live = { ...state.live, error: error instanceof Error ? error.message : t("unknown") };
        render();
      }
      return;
    }
    if (!action) return;
    event.preventDefault();
    if (action === "home") {
      state.view = "workspace";
      state.exampleId = null;
      render();
    } else if (action === "copy-start") {
      copy("uv run --no-editable --extra demo prguard studio", "start");
    } else if (action === "toggle-contract") {
      state.contractExpanded = !state.contractExpanded;
      render();
    } else if (action === "new-task") {
      state.contractConfirmed = false;
      state.contractExpanded = false;
      state.resultTab = "summary";
      live.newTask();
    } else if (action === "reconnect") {
      await live.connect();
      await live.refresh();
    } else if (action === "open-example") {
      state.exampleId = target.getAttribute("data-case");
      state.exampleTab = "summary";
      render();
    } else if (action === "close-example") {
      state.exampleId = null;
      render();
    } else if (action === "copy-example-patch") {
      const item = recordedCases[state.exampleId];
      if (item) copy(item.patchText, "example-patch");
    } else if (action === "copy-live-patch") {
      copy(state.live.snapshot?.result?.patch || "", "patch");
    } else if (action === "download-example") {
      const item = recordedCases[state.exampleId];
      if (item) downloadExample(item);
    }
  });

  root.addEventListener("change", event => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement || input instanceof HTMLSelectElement)) return;
    if (input.matches("[data-action='language']")) {
      locale.setLanguage(input.value);
    } else if (input.id === "contract-confirm") {
      state.contractConfirmed = input.checked;
    }
  });

  root.addEventListener("input", event => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement)) return;
    if (input.id === "task-issue") state.draft.issue = input.value;
    if (input.id === "task-base") state.draft.baseCommit = input.value;
  });

  root.addEventListener("submit", async event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    event.preventDefault();
    if (form.dataset.form === "prepare") {
      const issue = state.draft.issue || form.elements.issue?.value || "";
      const baseCommit = state.draft.baseCommit || form.elements.baseCommit?.value || "HEAD";
      await live.prepare({ issue, baseCommit });
    }
    if (form.dataset.form === "approve") {
      const check = form.querySelector("#contract-confirm");
      if (!(check instanceof HTMLInputElement) || !check.checked) {
        check?.focus();
        return;
      }
      await live.approve();
    }
  });

  root.addEventListener("click", event => {
    const target = event.target instanceof Element ? event.target.closest("[data-example-tab], [data-result-tab]") : null;
    if (!target) return;
    if (target.hasAttribute("data-example-tab")) {
      state.exampleTab = target.getAttribute("data-example-tab") || "summary";
      render();
    }
    if (target.hasAttribute("data-result-tab")) {
      state.resultTab = target.getAttribute("data-result-tab") || "summary";
      render();
    }
  });

  locale.subscribe(() => render());
  live.subscribe(next => {
    state.live = next;
    if (next.snapshot?.state === "ready") state.contractConfirmed = false;
    render();
  });
})();
