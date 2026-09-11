const cases = window.PRGuardCases;
let activeKey = "attrs";
let activeTab = "overview";
let replayTimer = null;
let eventIndex = 0;
let startedAt = 0;

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderStages(completed = 0, running = false) {
  const item = cases[activeKey];
  $("#stage-rail").innerHTML = item.stages.map((stage, index) => {
    const state = index < completed ? "done" : index === completed && running ? "running" : "";
    const glyph = index < completed ? "✓" : String(index + 1).padStart(2, "0");
    return `<li class="${state}"><span>${glyph}</span><div><strong>${escapeHtml(stage.name)}</strong><small>${escapeHtml(stage.detail)}</small></div></li>`;
  }).join("");
}

function renderEvidence(completed = 0) {
  const item = cases[activeKey];
  $("#chain-count").textContent = `${completed}/${item.evidence.length}`;
  $("#evidence-list").innerHTML = item.evidence.map((entry, index) => `
    <li class="${index < completed ? "verified" : ""}">
      <span class="evidence-status">${index < completed ? "✓" : ""}</span>
      <div><strong>${escapeHtml(entry.name)}</strong><small>${escapeHtml(entry.meta)}</small><code>${escapeHtml(entry.hash)}</code></div>
    </li>`).join("");
}

function renderTab() {
  const item = cases[activeKey];
  if (activeTab === "patch") {
    $("#tab-content").innerHTML = `<div class="code-toolbar"><span>${item.patch.files} changed files</span><button type="button" id="copy-patch">Copy diff</button></div><pre class="diff"><code>${escapeHtml(item.patchText)}</code></pre>`;
    $("#copy-patch").addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(item.patchText);
        $("#copy-patch").textContent = "Copied";
      } catch {
        $("#copy-patch").textContent = "Copy unavailable";
      }
    });
    return;
  }
  if (activeTab === "review") {
    const request = item.review.verdict !== "ACCEPT";
    $("#tab-content").innerHTML = `<div class="review-detail"><div class="verdict ${request ? "request" : "accept"}">${escapeHtml(item.review.verdict)}</div><div><strong>${escapeHtml(item.review.severity)}</strong><p>${escapeHtml(item.review.body)}</p></div></div>`;
    return;
  }
  if (activeTab === "artifacts") {
    $("#tab-content").innerHTML = `<div class="artifact-grid">${item.evidence.map(entry => `<div><span>JSON</span><strong>${escapeHtml(entry.name)}</strong><code>${escapeHtml(entry.hash)}</code></div>`).join("")}</div>`;
    return;
  }
  $("#tab-content").innerHTML = `<div class="overview-grid"><div><span class="outcome-mark">✓</span><div><strong>${escapeHtml(item.overview.verdict)}</strong><p>${escapeHtml(item.overview.copy)}</p><div class="source-links"><a href="${escapeHtml(item.issueUrl)}" target="_blank" rel="noreferrer">Upstream issue ↗</a><a href="${escapeHtml(item.evidenceUrl)}" target="_blank" rel="noreferrer">Public evidence ↗</a></div></div></div><dl>${item.overview.facts.map(([name, value]) => `<div><dt>${escapeHtml(name)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl></div>`;
}

function applyCase(key) {
  stopReplay();
  activeKey = key;
  const item = cases[key];
  $$(".mode-button").forEach(button => button.classList.toggle("active", button.dataset.case === key));
  $("#repository").value = item.repository;
  $("#base-commit").value = item.commit;
  $("#issue").value = item.issue;
  $("#gate-command").textContent = `$ ${item.gate}`;
  $("#case-kicker").textContent = item.kicker;
  $("#run-title").textContent = item.title;
  $("#header-runtime").textContent = item.runtime;
  $("#metric-tests").textContent = key === "attrs" ? "47 ready" : "1,323 passed";
  $("#metric-patch").textContent = "—";
  $("#metric-review").textContent = "Pending";
  $("#manifest-hash").textContent = "Waiting for run";
  $("#run-state").className = "run-state ready";
  $("#run-state").innerHTML = "<span></span><strong>READY</strong>";
  $("#activity-title").textContent = key === "attrs" ? "Implementer is ready" : "Reviewer is ready";
  $("#activity-subtitle").textContent = "Independent tools · bounded context";
  $("#agent-avatar").textContent = key === "attrs" ? "IM" : "RV";
  $("#elapsed").textContent = "00:00.0";
  $("#terminal").innerHTML = `<div class="terminal-empty"><span class="prompt">›</span><p>Start the replay to inspect every decision and verification result.</p></div>`;
  $("#run-button").disabled = false;
  $("#run-button .button-label").textContent = "Replay verified run";
  $("#export-button").disabled = true;
  renderStages();
  renderEvidence();
  renderTab();
}

function appendEvent(event) {
  if ($(".terminal-empty")) $("#terminal").innerHTML = "";
  const row = document.createElement("div");
  row.className = `terminal-row ${event.tone}`;
  row.innerHTML = `<span>${String(eventIndex + 1).padStart(2, "0")}</span><strong>${escapeHtml(event.label)}</strong><p>${escapeHtml(event.text)}</p>`;
  $("#terminal").append(row);
  row.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function finishReplay() {
  const item = cases[activeKey];
  stopReplay(false);
  renderStages(item.stages.length);
  renderEvidence(item.evidence.length);
  $("#run-state").className = "run-state passed";
  $("#run-state").innerHTML = "<span></span><strong>VERIFIED</strong>";
  $("#activity-title").textContent = activeKey === "attrs" ? "Review-ready patch delivered" : "Regression repaired and verified";
  $("#activity-subtitle").textContent = "All declared gates and evidence checks complete";
  $("#metric-tests").textContent = activeKey === "attrs" ? "49 passed" : "1,324 passed";
  $("#metric-patch").textContent = `+${item.patch.additions} −${item.patch.deletions}`;
  $("#metric-review").textContent = activeKey === "attrs" ? "Accepted" : "P2 repaired";
  $("#manifest-hash").textContent = item.manifest;
  $("#run-button").disabled = false;
  $("#run-button .button-label").textContent = "Replay again";
  $("#export-button").disabled = false;
}

function startReplay(event) {
  event?.preventDefault();
  stopReplay();
  eventIndex = 0;
  startedAt = performance.now();
  $("#terminal").innerHTML = "";
  $("#run-button").disabled = true;
  $("#run-button .button-label").textContent = "Replaying evidence…";
  $("#run-state").className = "run-state running";
  $("#run-state").innerHTML = "<span></span><strong>RUNNING</strong>";
  $("#activity-title").textContent = activeKey === "attrs" ? "Implementer is tracing the repository" : "Reviewer is tracing the candidate";
  renderStages(0, true);
  renderEvidence(0);
  const events = cases[activeKey].events;
  replayTimer = window.setInterval(() => {
    const elapsed = (performance.now() - startedAt) / 1000;
    $("#elapsed").textContent = `00:${elapsed.toFixed(1).padStart(4, "0")}`;
    appendEvent(events[eventIndex]);
    eventIndex += 1;
    const stage = Math.min(cases[activeKey].stages.length - 1, Math.floor(eventIndex / (events.length / cases[activeKey].stages.length)));
    renderStages(stage, true);
    renderEvidence(Math.min(cases[activeKey].evidence.length, Math.max(0, eventIndex - 3)));
    if (eventIndex >= events.length) finishReplay();
  }, 680);
}

function stopReplay(resetButton = true) {
  if (replayTimer) window.clearInterval(replayTimer);
  replayTimer = null;
  if (resetButton) $("#run-button")?.removeAttribute("disabled");
}

$$(".mode-button").forEach(button => button.addEventListener("click", () => applyCase(button.dataset.case)));
$("#task-form").addEventListener("submit", startReplay);
$("#reset-button").addEventListener("click", () => applyCase(activeKey));
$$(".tab").forEach(button => button.addEventListener("click", () => {
  activeTab = button.dataset.tab;
  $$(".tab").forEach(tab => {
    const selected = tab === button;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
  renderTab();
}));
$("#export-button").addEventListener("click", () => {
  const item = cases[activeKey];
  const payload = JSON.stringify({ case: activeKey, manifest: item.manifest, evidence: item.evidence }, null, 2);
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
  link.download = `prguard-${activeKey}-delivery.json`;
  link.click();
  URL.revokeObjectURL(link.href);
});

applyCase(activeKey);
