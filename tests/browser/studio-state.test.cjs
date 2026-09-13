/* Network lifecycle regressions. No browser dependencies or model calls required. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../../demo-ui/dist/live.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));

function boot({ savedRun = null, initialState = 'ready' } = {}) {
  const storage = new Map([['prguard-live-token', 'test-session']]);
  if (savedRun) storage.set('prguard-live-run', savedRun);
  const timers = new Map();
  const requests = [];
  const records = new Map([['first', { id: 'first', state: initialState, events: [] }]]);
  const env = {
    current: 'first', override: null, requests, timers, records,
  };
  let timerId = 0;
  const window = {
    location: { hostname: '127.0.0.1', hash: '', pathname: '/' },
    sessionStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
    history: { replaceState() {} },
    setTimeout(fn, delay) { const id = ++timerId; timers.set(id, { fn, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
  };
  const response = (value, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => JSON.parse(JSON.stringify(value)) });
  const fetch = async (url, options) => {
    requests.push({ url, ...options });
    if (env.override) {
      const result = env.override(url, options, response);
      if (result !== undefined) return result;
    }
    if (url === '/api/session') return response({ repository: '/repo', latest_run_id: env.current, review_available: true });
    if (url === '/api/runs') return response({
      runs: [...records.values()].map(run => ({ id: run.id, state: run.state })),
      active_run_id: [...records.values()].find(run => ['preparing', 'running'].includes(run.state))?.id || null,
    });
    const run = records.get(url.slice('/api/runs/'.length));
    return run ? response(run) : response({ error: 'Not found' }, 404);
  };
  const context = vm.createContext({ window, fetch, AbortController, URLSearchParams, URL, Error, console });
  vm.runInContext(source, context);
  env.api = window.PRGuardLive;
  return env;
}

test('ready contracts stop polling and unchanged snapshots do not redraw', async () => {
  const env = boot();
  await tick();
  assert.equal(env.api.getState().snapshot.state, 'ready');
  assert.equal(env.timers.size, 0);
  let changes = 0;
  env.api.subscribe(() => changes++);
  await env.api.refresh();
  assert.equal(changes, 1, 'only the initial subscription should emit');
});

test('a stored run from a previous service falls back to the current session', async () => {
  const env = boot({ savedRun: 'expired-run' });
  await tick();
  assert.equal(env.api.getState().runId, 'first');
  assert.equal(env.requests.some(request => request.url.endsWith('expired-run')), false);
});

test('a late snapshot cannot replace a newly selected task', async () => {
  const env = boot();
  env.records.set('second', { id: 'second', state: 'completed', events: [] });
  await tick();
  let resolveOld;
  env.override = (url, _options, response) => {
    if (url === '/api/runs/first') return new Promise(resolve => { resolveOld = () => resolve(response({ id: 'first', state: 'running' })); });
  };
  const oldRefresh = env.api.refresh();
  await tick();
  await env.api.selectRun('second');
  resolveOld();
  await oldRefresh;
  assert.equal(env.api.getState().runId, 'second');
  assert.equal(env.api.getState().snapshot.id, 'second');
  assert.equal(env.api.getState().snapshot.state, 'completed');
});

test('authentication expiry ends retries without implying task cancellation', async () => {
  const env = boot({ initialState: 'running' });
  await tick();
  env.override = (_url, _options, response) => response({ error: 'Session ended' }, 401);
  await env.api.refresh();
  assert.equal(env.api.getState().connection, 'expired');
  assert.equal(env.api.getState().snapshot.state, 'running');
  assert.equal(env.timers.size, 0);
});

test('transient network failures retain the run and schedule bounded retries', async () => {
  const env = boot({ initialState: 'running' });
  await tick();
  env.override = () => { throw new Error('offline'); };
  await env.api.refresh();
  assert.equal(env.api.getState().connection, 'degraded');
  assert.equal(env.api.getState().runId, 'first');
  assert.equal([...env.timers.values()].some(timer => timer.delay > 0 && timer.delay <= 8000), true);
});

test('workflow is supplied at preparation, not at approval', async () => {
  const env = boot();
  await tick();
  env.api.newTask();
  env.override = (url, options, response) => {
    if (url === '/api/prepare') {
      assert.equal(JSON.parse(options.body).workflow, 'reviewed_fix');
      env.records.set('new', { id: 'new', state: 'ready', events: [] });
      return response({ id: 'new' }, 202);
    }
    if (url === '/api/runs/new/start') {
      assert.deepEqual(JSON.parse(options.body), { confirmed: true });
      env.records.get('new').state = 'running';
      return response({ id: 'new' }, 202);
    }
  };
  await env.api.prepare({ issue: 'Fix this', baseCommit: 'HEAD', workflow: 'reviewed_fix' });
  assert.equal(env.api.getState().snapshot.state, 'ready');
  await env.api.approve();
  assert.equal(env.api.getState().snapshot.state, 'running');
});

test('a lost start response recovers execution without starting it twice', async () => {
  const env = boot();
  await tick();
  let starts = 0;
  env.override = url => {
    if (url.endsWith('/start')) {
      starts++;
      env.records.get('first').state = 'running';
      throw new Error('Response lost');
    }
  };
  await env.api.approve();
  assert.equal(starts, 1);
  assert.equal(env.api.getState().snapshot.state, 'running');
});
