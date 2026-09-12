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
  let pollInFlight = false;

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
  };

  function snapshotState() {
    return {
      ...state,
      session: state.session ? { ...state.session } : null,
      snapshot: state.snapshot ? { ...state.snapshot } : null,
    };
  }

  function emit() {
    const value = snapshotState();
    listeners.forEach(listener => listener(value));
  }

  function update(next) {
    Object.assign(state, next);
    emit();
  }

  function clearPoll() {
    if (pollTimer) window.clearTimeout(pollTimer);
    pollTimer = null;
  }

  function localStudioPage() {
    return window.location.hostname === "127.0.0.1";
  }

  function isTerminal(run) {
    return run && (run.state === "completed" || run.state === "error");
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
        throw new Error(message);
      }
      return response;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function schedulePoll() {
    clearPoll();
    if (!state.runId || isTerminal(state.snapshot)) return;
    const delay = state.connection === "degraded"
      ? Math.min(8000, 900 * (2 ** Math.min(state.retryCount, 3)))
      : 750;
    pollTimer = window.setTimeout(refresh, delay);
  }

  async function refresh() {
    if (pollInFlight || !state.runId) return;
    pollInFlight = true;
    try {
      const response = await api("/api/runs/" + state.runId);
      const run = await response.json();
      update({
        snapshot: run,
        connection: "connected",
        error: null,
        retryCount: 0,
        action: isTerminal(run) ? null : state.action,
      });
      schedulePoll();
    } catch (error) {
      const retryCount = state.retryCount + 1;
      update({
        connection: "degraded",
        error: error instanceof Error ? error.message : "Local connection failed",
        retryCount,
      });
      schedulePoll();
    } finally {
      pollInFlight = false;
    }
  }

  async function connect() {
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
      const response = await api("/api/session");
      const session = await response.json();
      let runId = session.latest_run_id || null;
      try {
        runId = window.sessionStorage.getItem(storageRunKey) || runId;
      } catch { /* Run recovery is optional. */ }
      update({
        availability: "local",
        connection: "connected",
        session,
        runId,
        snapshot: null,
        action: null,
        error: null,
        retryCount: 0,
      });
      if (runId) await refresh();
    } catch (error) {
      update({
        availability: "local",
        connection: "degraded",
        error: error instanceof Error ? error.message : "Could not connect to local Studio",
        retryCount: 1,
      });
    }
  }

  async function prepare({ issue, baseCommit }) {
    if (!state.session || state.action) return;
    const mode = state.session.repository ? "local" : "demo";
    update({ action: "prepare", error: null });
    try {
      const response = await api("/api/prepare", {
        mode,
        issue: mode === "demo" ? state.session.demo_issue : issue,
        base_commit: baseCommit,
      });
      const payload = await response.json();
      try { window.sessionStorage.setItem(storageRunKey, payload.id); } catch { /* Optional. */ }
      update({ runId: payload.id, snapshot: null, action: null });
      await refresh();
    } catch (error) {
      update({
        action: null,
        error: error instanceof Error ? error.message : "Could not prepare the task",
      });
    }
  }

  async function approve() {
    if (!state.runId || state.action) return;
    update({ action: "approve", error: null });
    try {
      await api("/api/runs/" + state.runId + "/start", { confirmed: true });
      update({ action: null });
      await refresh();
    } catch (error) {
      update({
        action: null,
        error: error instanceof Error ? error.message : "Could not start the task",
      });
    }
  }

  function newTask() {
    clearPoll();
    try { window.sessionStorage.removeItem(storageRunKey); } catch { /* Optional. */ }
    update({ runId: null, snapshot: null, action: null, error: null, retryCount: 0 });
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
    download,
  };

  connect();
})();
