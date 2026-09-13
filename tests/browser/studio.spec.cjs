const { test: base, expect } = require('@playwright/test');
const { spawn } = require('node:child_process');
const { createHash } = require('node:crypto');
const { readFile } = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const test = base.extend({
  localMode: [false, { option: true }],
  reviewUnavailable: [false, { option: true }],
  studio: async ({ localMode, reviewUnavailable }, use) => {
    const python = process.env.PRGUARD_TEST_PYTHON || path.join(root, '.venv/bin/python');
    const child = spawn(python, [path.join(__dirname, 'serve_fixture.py'), ...(localMode ? ['--local'] : []), ...(reviewUnavailable ? ['--review-unavailable'] : [])], {
      cwd: root,
      env: { ...process.env, PYTHONPATH: path.join(root, 'src'), DEEPSEEK_API_KEY: '', OPENAI_API_KEY: '' },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    const exited = new Promise(resolve => child.once('close', resolve));
    let stderr = '';
    child.stderr.on('data', chunk => { stderr = (stderr + chunk).slice(-4000); });
    let startupTimer;
    try {
      const url = await new Promise((resolve, reject) => {
        let output = '';
        startupTimer = setTimeout(() => reject(new Error('Fixture startup timed out: ' + stderr)), 15000);
        child.once('error', reject);
        child.once('exit', () => reject(new Error('Fixture exited before startup: ' + stderr)));
        child.stdout.on('data', chunk => {
          output += chunk;
          if (output.includes('\n')) {
            try { resolve(JSON.parse(output.split('\n')[0]).url); } catch (error) { reject(error); }
          }
        });
      });
      clearTimeout(startupTimer);
      const parsed = new URL(url);
      await use({ url, origin: parsed.origin, token: new URLSearchParams(parsed.hash.slice(1)).get('token') });
    } finally {
      clearTimeout(startupTimer);
      if (child.exitCode === null) child.kill('SIGTERM');
      await exited;
    }
  },
  errorCheck: [async ({ page }, use) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await use();
    expect(errors).toEqual([]);
  }, { auto: true }],
});

async function open(page, studio) {
  await page.goto(studio.url);
  await expect(page.getByRole('heading', { name: '新建代码任务' })).toBeVisible();
  await expect(page).toHaveURL(studio.origin + '/');
}

async function approve(page) {
  await expect(page.getByRole('heading', { name: '确认这次运行会做什么' })).toBeVisible();
  await page.getByRole('checkbox', { name: '我已核对任务和执行环境' }).check();
  await page.getByRole('button', { name: '确认并开始执行', exact: true }).click();
  await expect(page.getByRole('heading', { name: '补丁已通过本次验证' })).toBeVisible();
}

test('reviewed flow: approval, keyboard tabs, exact patch download, refresh and history', async ({ page, studio }) => {
  const starts = [];
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/start')) starts.push(request);
  });
  await open(page, studio);
  await page.getByRole('radio', { name: /^修改、验证并审查/ }).check();
  await page.getByRole('button', { name: '查看执行计划', exact: true }).click();
  await expect(page.getByText('固定演示用例', { exact: true })).toBeVisible();
  await expect(page.getByRole('checkbox')).not.toBeChecked();
  expect(starts).toHaveLength(0);
  await approve(page);
  await expect(page.getByText('独立审查已完成', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: '补丁', exact: true }).click();
  await expect(page.locator('.diff-add')).toContainText('return max(lower, min(value, upper))');
  await page.getByRole('tab', { name: '补丁', exact: true }).press('ArrowRight');
  await expect(page.getByRole('tab', { name: '测试', exact: true })).toBeFocused();
  await expect(page.getByRole('tab', { name: '测试', exact: true })).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('tab', { name: '证据文件', exact: true }).click();
  const file = page.locator('.artifact-list article').filter({ hasText: 'final.patch' });
  const expectedHash = await file.locator('code').textContent();
  const downloadEvent = page.waitForEvent('download');
  await file.getByRole('button', { name: '下载', exact: true }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe('final.patch');
  const payload = await readFile(await download.path());
  expect(createHash('sha256').update(payload).digest('hex')).toBe(expectedHash);
  await page.reload();
  await expect(page.getByText('独立审查已完成', { exact: true })).toBeVisible();
  await expect(page.locator('.history-item')).toHaveCount(1);
  await page.getByRole('button', { name: '+ 新建任务', exact: true }).click();
  await expect(page.getByRole('heading', { name: '新建代码任务' })).toBeVisible();
  await page.locator('.history-item').click();
  await expect(page.getByRole('heading', { name: '补丁已通过本次验证' })).toBeVisible();
  expect(starts).toHaveLength(1);
});

test('language and narrow layout preserve evidence and do not overflow', async ({ page, studio }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, studio);
  await page.getByRole('button', { name: '查看执行计划', exact: true }).click();
  await approve(page);
  await page.getByRole('tab', { name: '补丁', exact: true }).click();
  const source = await page.locator('.diff-source').allTextContents();
  await page.getByLabel('语言', { exact: true }).selectOption('en');
  await expect(page.getByRole('heading', { name: 'The patch passed this verification' })).toBeVisible();
  expect(await page.locator('.diff-source').allTextContents()).toEqual(source);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('tab', { name: 'Summary', exact: true }).click();
  await expect(page.getByText('Independent review was not included', { exact: true })).toBeVisible();
});

test.describe('configured local repository', () => {
  test.use({ localMode: true });
  test('invalid version is actionable and editing preserves the request before recovery', async ({ page, studio }) => {
    await open(page, studio);
    const issue = "Enforce both clamp bounds. <img src=x onerror=alert('unsafe')>";
    await page.getByLabel('问题或需求', { exact: true }).fill(issue);
    await page.getByLabel('基础版本', { exact: true }).fill('version-not-present');
    await page.getByRole('button', { name: '查看执行计划', exact: true }).click();
    await expect(page.getByRole('heading', { name: '找不到填写的代码版本' })).toBeVisible();
    await expect(page.getByText('任务停在准备阶段，尚未调用模型或运行仓库测试。')).toBeVisible();
    await page.getByRole('button', { name: '保留需求，返回修改' }).click();
    await expect(page.getByLabel('问题或需求', { exact: true })).toHaveValue(issue);
    await expect(page.getByLabel('基础版本', { exact: true })).toHaveValue('version-not-present');
    await page.getByLabel('基础版本', { exact: true }).fill('HEAD');
    await page.getByRole('button', { name: '查看执行计划', exact: true }).click();
    await expect(page.getByText('根据仓库结构自动识别', { exact: true })).toBeVisible();
    await approve(page);
    await expect(page.locator('.history-item')).toHaveCount(2);
    await expect(page.locator('img')).toHaveCount(0);
  });
});

test('static start guide does not create a backend task', async ({ page, studio }) => {
  const posts = [];
  page.on('request', request => { if (request.method() === 'POST') posts.push(request); });
  await page.goto(studio.origin);
  await page.getByText('接入你自己的代码仓库', { exact: true }).click();
  await expect(page.getByText('准备本地仓库', { exact: true })).toBeVisible();
  await page.getByText('如果没有识别到测试怎么办？', { exact: true }).click();
  await expect(page.locator('.setup-policy pre')).toContainText('verification_commands');
  expect(posts).toHaveLength(0);
});

test('regression demo shows a review finding, controlled repair and the new regression test', async ({ page, studio }) => {
  await open(page, studio);
  await page.getByLabel('选择演示流程', { exact: true }).selectOption('review_regression');
  await expect(page.getByRole('radio', { name: /^修改、验证并审查/ })).toBeChecked();
  await expect(page.getByRole('radio', { name: /^修改并验证/ })).toBeDisabled();
  await expect(page.getByLabel('问题或需求', { exact: true })).toHaveValue(/normalize/);
  await page.getByRole('button', { name: '查看执行计划', exact: true }).click();
  await approve(page);
  await expect(page.locator('.result-stats')).toContainText('实现阶段尝试');
  await expect(page.locator('.result-summary .review-repair-card')).toContainText('Restore lowercase conversion');
  await page.getByRole('tab', { name: '审查', exact: true }).click();
  await expect(page.locator('.finding-card')).toHaveCount(1);
  await expect(page.locator('.finding-card')).toContainText('normalizer.py');
  await expect(page.locator('.review-repair-card')).toContainText('本轮未进行第二次 Reviewer 审查');
  await page.getByText('新增测试的复现记录', { exact: true }).click();
  await expect(page.locator('.review-repro')).toContainText('1 failed');
  await page.getByRole('tab', { name: '补丁', exact: true }).click();
  await expect(page.locator('.patch-file')).toHaveCount(2);
  await expect(page.locator('.patch-file')).toContainText(['normalizer.py', 'tests/test_regression.py']);
});

test.describe('review service failure', () => {
  test.use({ reviewUnavailable: true });
  test('initial green verification does not become accepted delivery', async ({ page, studio }) => {
    await open(page, studio);
    await page.getByRole('radio', { name: /^修改、验证并审查/ }).check();
    await page.getByRole('button', { name: '查看执行计划', exact: true }).click();
    await page.getByRole('checkbox', { name: '我已核对任务和执行环境' }).check();
    await page.getByRole('button', { name: '确认并开始执行', exact: true }).click();
    await expect(page.getByText('独立审查未完成', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: '补丁已通过本次验证' })).toHaveCount(0);
    await page.getByRole('tab', { name: '证据文件', exact: true }).click();
    await expect(page.locator('.artifact-list article')).toHaveCount(4);
    await expect(page.locator('.artifact-list')).not.toContainText('final.patch');
    const run = await page.locator('.history-item').getAttribute('data-run');
    const denied = await page.request.get(`${studio.origin}/api/runs/${run}/artifacts/final.patch`, {
      headers: { Authorization: 'Bearer ' + studio.token },
    });
    expect(denied.status()).toBe(404);
  });
});
