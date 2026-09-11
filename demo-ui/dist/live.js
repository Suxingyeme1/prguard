/* Local adapter: same-origin authenticated requests; every event comes from FixRunner. */
(() => {
  const el = id => document.getElementById(id);
  const escape = value => String(value ?? "").replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
  let token = "";
  let currentRun = null;
  let session = null;
  let seenEvents = 0;
  let polling = false;
  let submitting = false;
  let preparedReady = false;
  let replayRuntime = el("header-runtime").textContent;

  el("live-workspace").innerHTML = `
    <div class="live-heading"><div><p class="eyebrow">LOCAL CODING SESSION</p>
      <h1>Run a real coding task</h1><p>Prepare the task, confirm the test policy, then watch execution.</p></div>
      <span class="local-pill" id="live-connection">Not connected</span></div>
    <section class="live-setup" id="live-setup">
      <h2>Start the local workspace</h2>
      <p>Run this command in the PRGuard repository. It opens a browser connected to your local Harness.</p>
      <pre><code>uv run --no-editable --extra demo prguard studio</code></pre>
      <p>The offline demo runs Git and pytest with scripted model responses. No API key is needed.</p>
      <details><summary>Use your own repository</summary>
        <pre><code>uv run --no-editable --extra agent --extra demo prguard studio \
  --repository /path/to/project \
  --workspace /path/to/prguard-runs \
  --trust-host --provider deepseek</code></pre>
        <p>Use a clean repository and configure your model key in the terminal environment.</p>
      </details>
    </section>
    <div id="live-controls" class="live-grid" hidden>
      <section class="live-form-card">
        <form id="live-task-form">
          <h2>New task</h2>
          <label class="field-label" for="live-mode">Task type</label>
          <select id="live-mode"><option value="demo">Offline execution demo</option>
            <option value="local" disabled>Configured repository</option></select>
          <p id="live-repository" class="live-secondary"></p>
          <label class="field-label" for="live-issue">Issue / requirement</label>
          <textarea id="live-issue" rows="5" maxlength="50000" required></textarea>
          <label class="field-label" for="live-base">Base commit</label>
          <input id="live-base" value="HEAD" maxlength="128" required />
          <button id="live-prepare" type="submit" class="primary-button">Prepare task</button>
        </form>
        <div id="live-preview"></div>
      </section>
      <section class="live-execution">
        <div class="live-section-heading"><h2>Execution events</h2><span id="live-status">Ready</span></div>
        <p class="live-secondary">These events come from the local Harness as it runs.</p>
        <div id="live-log" class="live-log" role="log" aria-live="polite"></div>
        <div id="live-result"></div>
      </section>
    </div>
    <p id="live-error" role="alert" class="live-error" hidden></p>`;

  function showView(name) {
    if (name === "live" && !el("replay-workspace").hidden) {
      replayRuntime = el("header-runtime").textContent;
    }
    el("replay-workspace").hidden = name !== "replay";
    el("live-workspace").hidden = name !== "live";
    el("header-view").textContent = name === "replay" ? "Evidence replay" : "Local workspace";
    el("header-access").textContent = name === "live" && session ? "LOCAL · LIVE" : "LOCAL · READ ONLY";
    el("header-runtime").textContent = name === "replay" ? replayRuntime : session ? `Adapter · ${session.runtime}` : "Local setup";
    document.querySelectorAll("[data-surface]").forEach(button => {
      const active = button.dataset.surface === name;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }
  document.querySelectorAll("[data-surface]").forEach(button => {
    button.addEventListener("click", () => showView(button.dataset.surface));
  });

  function error(message) {
    el("live-error").textContent = message;
    el("live-error").hidden = !message;
  }

  async function api(path, body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(path, {
        method: body === undefined ? "GET" : "POST",
        headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
        body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal,
        cache: "no-store", credentials: "omit", redirect: "error",
      });
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload.error || "Local request failed");
      }
      return response;
    } finally { clearTimeout(timeout); }
  }

  function selectMode() {
    const demo = el("live-mode").value === "demo";
    el("live-issue").readOnly = demo;
    el("live-base").readOnly = demo;
    el("live-issue").value = demo ? session.demo_issue : "";
    el("live-base").value = "HEAD";
    el("live-repository").textContent = demo ? "Disposable fixture repository · scripted provider" : session.repository;
  }

  function setBusy(busy) {
    for (const id of ["live-prepare", "live-mode", "live-issue", "live-base"]) el(id).disabled = busy;
  }

  const eventLabels = {
    "preparation.started": "Freezing task and repository",
    "preparation.completed": "Task ready for confirmation",
    "run.started": "Execution started",
    "preflight.started": "Checking the frozen commit",
    "preflight.completed": "Isolated worktree ready",
    "readiness.started": "Checking test collection",
    "readiness.completed": "Test collection checked",
    "attempt.started": "Implementer attempt started",
    "proposal.completed": "Candidate patch generated",
    "verification.started": "Running declared test commands",
    "verification.completed": "Verification completed",
    "repair.requested": "Failure evidence returned for one repair",
    "attempt.failed": "Implementer attempt failed",
    "run.completed": "Fix pipeline finished",
    "delivery.completed": "Artifacts verified and ready",
    "adapter.failed": "Execution could not finish",
  };

  function renderPreview(preview, allowApproval) {
    const list = values => values.map(value => `<code>${escape(value)}</code>`).join(" ");
    el("live-preview").innerHTML = `<div class="live-policy"><h3>Confirm this task</h3>
      <dl><dt>Base commit</dt><dd><code>${escape(preview.base_commit)}</code></dd>
        <dt>Issue / requirement</dt><dd class="live-issue-summary">${escape(preview.issue)}</dd>
        <dt>Execution environment</dt><dd>${escape(preview.boundary === "host" ? "Trusted host" : "Container")}</dd>
        <dt>Model provider</dt><dd><code>${escape(preview.provider)}</code></dd>
        <dt>Verification commands</dt><dd>${preview.commands.map(argv => `<pre><code>${escape(JSON.stringify(argv))}</code></pre>`).join("")}</dd>
        <dt>Writable paths</dt><dd>${list(preview.writable_paths)}</dd>
        <dt>Protected paths</dt><dd>${list(preview.protected_paths)}</dd>
        <dt>Time limit (seconds)</dt><dd>${escape(preview.task_timeout_seconds)}</dd>
        <dt>Maximum repair attempts</dt><dd>${escape(preview.max_repair_attempts)}</dd>
        <dt>Task SHA-256</dt><dd><code>${escape(preview.task_sha256)}</code></dd></dl>
        ${allowApproval ? `<form id="live-approval-form"><label class="live-confirm"><input type="checkbox" required />
          <span>I approve this task and execution environment.</span></label>
          <p class="live-secondary">Host mode runs repository tests with your account. A live provider sends allowed source to the model and uses API credits.</p>
          <button id="live-start" class="primary-button" type="submit">Confirm and run</button></form>` : ""}</div>`;
    el("live-approval-form")?.addEventListener("submit", async event => {
      event.preventDefault();
      if (submitting) return;
      submitting = true;
      el("live-start").disabled = true;
      error("");
      try {
        await api(`/api/runs/${currentRun}/start`, { confirmed: true });
        preparedReady = false;
        el("live-approval-form").remove();
        setBusy(true);
        poll();
      } catch (err) {
        error(err.message);
        if (el("live-start")) el("live-start").disabled = false;
      } finally { submitting = false; }
    });
  }

  function renderResult(result) {
    el("live-result").innerHTML = `<div class="live-result-heading ${result.outcome === "accepted" ? "success" : "failure"}">
      <h2>${result.outcome === "accepted" ? "Patch accepted" : "Task not accepted"}</h2>
      <p><span>Duration</span>: ${Number(result.duration_seconds).toFixed(1)}s · <span>Manifest verified</span></p>
      <p class="live-secondary">Independent Review was not run in this local Fix session.</p></div>
      ${result.attempts.map(attempt => `<article class="live-attempt"><h3><span>Attempt</span> ${attempt.attempt} ·
        <span>${attempt.outcome === "passed" ? "Passed" : "Failed"}</span></h3>
        <p>${escape(attempt.summary || attempt.error || "")}</p>
        <ol>${attempt.plan.map(step => `<li>${escape(step)}</li>`).join("")}</ol>
        ${attempt.commands.map(command => `<details ${command.passed ? "" : "open"}><summary><code>${escape(command.argv.join(" "))}</code>
          · exit ${escape(command.exit_code)}${command.timed_out ? " · timeout" : ""}</summary>
          <pre><code>${escape(command.stdout)}\n${escape(command.stderr)}</code></pre></details>`).join("")}</article>`).join("")}
      <h3>Final patch</h3><pre class="live-patch"><code>${escape(result.patch || "No patch delivered")}</code></pre>
      <h3>Download artifacts</h3><div class="live-downloads">${result.artifacts.map(file =>
        `<button type="button" class="export-button" data-file="${escape(file.name)}">${escape(file.name)} ⇩</button>`).join("")}</div>
      <p class="live-secondary">Artifact directory</p><pre><code>${escape(result.artifact_directory)}</code></pre>`;
    el("live-result").querySelectorAll("[data-file]").forEach(button => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const response = await api(`/api/runs/${currentRun}/artifacts/${button.dataset.file}`);
          const url = URL.createObjectURL(await response.blob());
          const link = document.createElement("a");
          link.href = url; link.download = button.dataset.file; link.click();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (err) { error(err.message); }
        finally { button.disabled = false; }
      });
    });
  }

  async function poll() {
    if (polling) return;
    polling = true;
    try {
      while (currentRun) {
        const snapshot = await (await api(`/api/runs/${currentRun}`)).json();
        el("live-status").textContent = {
          preparing: "Preparing", ready: "Awaiting confirmation", running: "Running",
          completed: "Completed", error: "Failed",
        }[snapshot.state];
        for (const event of snapshot.events.slice(seenEvents)) {
          const row = document.createElement("article");
          row.className = "live-event";
          row.innerHTML = `<span class="live-event-time">${Number(event.elapsed).toFixed(1)}s</span>
            <div><strong>${escape(eventLabels[event.event] || event.event)}</strong>
            <code>${escape(JSON.stringify(event.data))}</code></div>`;
          el("live-log").append(row);
        }
        seenEvents = snapshot.events.length;
        el("live-log").scrollTop = el("live-log").scrollHeight;
        if (snapshot.state === "ready") {
          renderPreview(snapshot.preview, true);
          preparedReady = true;
          setBusy(true);
          el("live-prepare").disabled = false;
          el("live-prepare").textContent = "New task";
          break;
        }
        if (snapshot.state === "completed" || snapshot.state === "error") {
          if (snapshot.result) renderResult(snapshot.result);
          if (snapshot.error) error(snapshot.error);
          preparedReady = false;
          el("live-prepare").textContent = "Prepare task";
          setBusy(false); break;
        }
        await new Promise(resolve => setTimeout(resolve, 750));
      }
    } catch (err) {
      error(`${err.message}. Reload the local page to reconnect to the same run.`);
      // Keep start/prepare disabled: a network error does not mean execution stopped.
    } finally { polling = false; }
  }

  el("live-task-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (submitting || polling) return;
    if (preparedReady) {
      preparedReady = false;
      currentRun = null;
      el("live-preview").innerHTML = "";
      el("live-prepare").textContent = "Prepare task";
      setBusy(false);
      return;
    }
    submitting = true; setBusy(true); error("");
    el("live-preview").innerHTML = "";
    el("live-result").innerHTML = "";
    el("live-log").innerHTML = "";
    seenEvents = 0;
    try {
      const response = await api("/api/prepare", {
        mode: el("live-mode").value, issue: el("live-issue").value, base_commit: el("live-base").value,
      });
      currentRun = (await response.json()).id;
      try { sessionStorage.setItem("prguard-live-run", currentRun); } catch { /* Optional. */ }
      poll();
    } catch (err) { error(err.message); setBusy(false); }
    finally { submitting = false; }
  });

  async function connect() {
    if (location.hostname !== "127.0.0.1") return;
    const fragment = new URLSearchParams(location.hash.slice(1));
    token = fragment.get("token") || "";
    try {
      if (token) sessionStorage.setItem("prguard-live-token", token);
      else token = sessionStorage.getItem("prguard-live-token") || "";
    } catch { /* The current page can still work without storage. */ }
    if (!token) return;
    history.replaceState(null, "", location.pathname);
    showView("live");
    try {
      session = await (await api("/api/session")).json();
      showView("live");
      el("live-setup").hidden = true;
      el("live-controls").hidden = false;
      el("live-connection").textContent = "Local Harness connected";
      el("live-mode").querySelector('[value="local"]').disabled = !session.repository;
      if (session.repository) el("live-mode").value = "local";
      selectMode();
      el("live-mode").addEventListener("change", selectMode);
      currentRun = session.latest_run_id;
      if (currentRun) {
        const response = await api(`/api/runs/${currentRun}`);
        const snapshot = await response.json();
        el("live-mode").value = snapshot.mode;
        selectMode();
        if (snapshot.preview) {
          el("live-issue").value = snapshot.preview.issue;
          el("live-base").value = snapshot.preview.base_commit;
        }
        if (snapshot.preview) renderPreview(snapshot.preview, false);
        setBusy(true); poll();
      }
    } catch (err) {
      error(err.message);
      // A stale run belongs to a previous server session; preparation remains available.
      try { sessionStorage.removeItem("prguard-live-run"); } catch { /* Optional. */ }
    }
  }
  connect();
})();
