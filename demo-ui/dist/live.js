/*
 * Local Studio adapter. This module owns network state only; app.js owns the
 * view. Keeping the two separate prevents a hidden screen from mutating a
 * second page or translating recorded evidence by accident.
 */
(() => {
  const listeners = new Set();
  const storageTokenKey = "prguard-live-token";
  const storageRunKey = "prguard-live-run";
  let pollTimer = null;
  let pollInFlight = null;
  let generation = 0;

  const state = {
    availability: "static",
    connection: "idle",
    token: "",
    session: null,
    runId: null,
    snapshot: null,
    action: null,
    error: null,
    retryCount: 0,
    runs: [],
    activeRunId: null,
  };

  function snapshotState() {
    return {
      ...state,
      session: state.session ? { ...state.session } : null,
      snapshot: state.snapshot ? { ...state.snapshot } : null,
      runs: state.runs.map(run => ({ ...run })),
    };
  }

  function emit() {
    const value = snapshotState();
    listeners.forEach(listener => listener(value));
  }

  function sameValue(current, next) {
    if (Object.is(current, next)) return true;
    if (!current || !next || typeof current !== "object" || typeof next !== "object") {
      return false;
    }
    // API snapshots are JSON values. Avoid replacing the whole view when a poll
    // returns the same run again with a new object identity.
    return JSON.stringify(current) === JSON.stringify(next);
  }

  function update(next) {
    let visibleChange = false;
    for (const [key, value] of Object.entries(next)) {
      if (sameValue(state[key], value)) continue;
      state[key] = value;
      // These values affect retries and authentication, but never alter the
      // visible workspace by themselves.
      if (key !== "retryCount" && key !== "token") visibleChange = true;
    }
    if (visibleChange) emit();
  }

  function clearPoll() {
    if (pollTimer) window.clearTimeout(pollTimer);
    pollTimer = null;
  }

  function localStudioPage() {
    return window.location.hostname === "127.0.0.1";
  }

  function needsPolling(run) {
    // A contract is intentionally stable while it awaits human approval. Keep
    // polling only while preparation/execution can make observable progress.
    return !run || run.state === "preparing" || run.state === "running";
  }

  function resetRequests() {
    generation += 1;
    pollInFlight = null;
    clearPoll();
    return generation;
  }

  function requestFailed(error) {
    const expired = error?.status === 401 || error?.status === 403 || error?.status === 404;
    update({
      connection: expired ? "expired" : "degraded",
      error: error instanceof Error ? error.message : "Local connection failed",
      retryCount: state.retryCount + 1,
      action: null,
    });
    if (expired) clearPoll();
  }

  async function api(path, body) {
    if (!state.token) throw new Error("Missing local Studio session token");
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(path, {
        method: body === undefined ? "GET" : "POST",
        headers: {
          Authorization: "Bearer " + state.token,
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
        cache: "no-store",
        credentials: "omit",
        redirect: "error",
      });
      if (!response.ok) {
        let message = "Local request failed";
        try {
          const payload = await response.json();
          message = payload.error || message;
        } catch { /* Keep the safe generic message. */ }
        const error = new Error(message);
        error.status = response.status;
        throw error;
      }
      return response;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function schedulePoll() {
    clearPoll();
    if (state.connection === "expired") return;
    const selectedIsRunning = state.runId && needsPolling(state.snapshot);
    if (!selectedIsRunning && !state.activeRunId) return;
    const delay = state.connection === "degraded"
      ? Math.min(8000, 900 * (2 ** Math.min(state.retryCount, 3)))
      : selectedIsRunning ? 750 : 2000;
    pollTimer = window.setTimeout(refresh, delay);
  }

  async function refresh() {
    if (pollInFlight !== null || !state.session || state.connection === "expired") return;
    const version = generation;
    const runId = state.runId;
    pollInFlight = version;
    try {
      const [history, run] = await Promise.all([
        api("/api/runs").then(response => response.json()),
        runId ? api("/api/runs/" + runId).then(response => response.json()) : null,
      ]);
      if (version !== generation || runId !== state.runId) return;
      update({
        snapshot: run,
        runs: history.runs,
        activeRunId: history.active_run_id,
        connection: "connected",
        error: null,
        retryCount: 0,
        action: needsPolling(run) ? state.action : null,
      });
      schedulePoll();
    } catch (error) {
      if (version !== generation) return;
      requestFailed(error);
      schedulePoll();
    } finally {
      if (pollInFlight === version) pollInFlight = null;
    }
  }

  async function connect() {
    const version = resetRequests();
    if (!localStudioPage()) {
      update({ availability: "static", connection: "idle" });
      return;
    }
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    let token = fragment.get("token") || "";
    try {
      if (token) window.sessionStorage.setItem(storageTokenKey, token);
      if (!token) token = window.sessionStorage.getItem(storageTokenKey) || "";
    } catch { /* The current page can still show the local-start guide. */ }
    if (!token) {
      // A bare loopback URL is also how the static walkthrough is commonly served.
      // The CLI always supplies a fragment token, so do not turn a static preview
      // into a misleading half-connected local workspace merely because it uses 127.0.0.1.
      update({ availability: "static", connection: "idle" });
      return;
    }
    if (fragment.has("token")) {
      window.history.replaceState(null, "", window.location.pathname);
    }
    update({ availability: "local", connection: "connecting", token, error: null });
    try {
      const [session, history] = await Promise.all([
        api("/api/session").then(response => response.json()),
        api("/api/runs").then(response => response.json()),
      ]);
      if (version !== generation) return;
      let runId = state.runId || session.latest_run_id || null;
      try {
        runId = window.sessionStorage.getItem(storageRunKey) || runId;
      } catch { /* Run recovery is optional. */ }
      if (!history.runs.some(run => run.id === runId)) runId = session.latest_run_id || null;
      update({
        availability: "local",
        connection: "connected",
        session,
        runId,
        runs: history.runs,
        activeRunId: history.active_run_id,
        snapshot: state.snapshot?.id === runId ? state.snapshot : null,
        action: null,
        error: null,
        retryCount: 0,
      });
      if (runId || history.active_run_id) await refresh();
    } catch (error) {
      if (version === generation) requestFailed(error);
    }
  }

  async function prepare({ issue, baseCommit, workflow = "fix", demoCase = "clamp" }) {
    if (!state.session || state.action || state.activeRunId || state.connection !== "connected") return;
    const version = resetRequests();
    const mode = state.session.repository ? "local" : "demo";
    update({ action: "prepare", error: null });
    try {
      const response = await api("/api/prepare", {
        mode,
        issue: mode === "demo"
          ? state.session.demo_cases?.find(item => item.id === demoCase)?.issue || state.session.demo_issue
          : issue,
        base_commit: baseCommit,
        workflow,
        ...(mode === "demo" ? { demo_case: demoCase } : {}),
      });
      const payload = await response.json();
      if (version !== generation) return;
      try { window.sessionStorage.setItem(storageRunKey, payload.id); } catch { /* Optional. */ }
      update({ runId: payload.id, snapshot: null, action: null });
      await refresh();
    } catch (error) {
      if (version !== generation) return;
      update({
        action: null,
        error: error instanceof Error ? error.message : "Could not prepare the task",
      });
      // The server may have prepared a task even when its response was lost.
      // Recover its identifier before allowing a second submission.
      if (!error?.status || error.status >= 500) await connect();
      else if ([401, 403, 404].includes(error.status)) requestFailed(error);
    }
  }

  async function approve() {
    if (!state.runId || state.action || state.connection !== "connected") return;
    const runId = state.runId;
    const version = generation;
    update({ action: "approve", error: null });
    try {
      await api("/api/runs/" + runId + "/start", { confirmed: true });
      if (version !== generation) return;
      update({ action: null });
      await refresh();
    } catch (error) {
      if (version !== generation) return;
      update({
        action: null,
        error: error instanceof Error ? error.message : "Could not start the task",
      });
      if ([401, 403, 404].includes(error?.status)) requestFailed(error);
      else await refresh();
    }
  }

  function newTask() {
    if (state.action) return;
    resetRequests();
    try { window.sessionStorage.removeItem(storageRunKey); } catch { /* Optional. */ }
    update({ runId: null, snapshot: null, action: null, error: null, retryCount: 0 });
    schedulePoll();
  }

  async function selectRun(runId) {
    if (state.action || !state.runs.some(run => run.id === runId)) return;
    resetRequests();
    try { window.sessionStorage.setItem(storageRunKey, runId); } catch { /* Optional. */ }
    update({ runId, snapshot: null, error: null, retryCount: 0 });
    await refresh();
  }

  async function download(name) {
    if (!state.runId || !/^[a-z.-]+$/.test(name)) throw new Error("Artifact is not available");
    const response = await api("/api/runs/" + state.runId + "/artifacts/" + name);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  window.PRGuardLive = {
    getState: snapshotState,
    subscribe(listener) {
      listeners.add(listener);
      listener(snapshotState());
      return () => listeners.delete(listener);
    },
    connect,
    refresh,
    prepare,
    approve,
    newTask,
    selectRun,
    download,
  };

  connect();
})();
