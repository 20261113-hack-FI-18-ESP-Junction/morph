import { chromium } from '../intel-dashboard-bringup/browser-tools/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const settings = JSON.parse(await fs.readFile(process.argv[2] ?? path.join(directory, '../intel-gemma-20261114/runs/hosted-03/services.json'), 'utf8'));
const origin = new URL(settings.uiOrigin).origin;
assert(['localhost', '127.0.0.1'].includes(new URL(origin).hostname));
const output = path.join(directory, `analyst-review-${new Date().toISOString().replace(/[:.]/g, '-')}`);
await fs.mkdir(output, { recursive: false });
const executablePath = path.join(directory, '../intel-dashboard-bringup/browser-tools/browsers/chromium_headless_shell-1255/chrome-headless-shell-linux64/chrome-headless-shell');
const browser = await chromium.launch({ headless: true, executablePath, args: ['--disable-dev-shm-usage'] });
const observations = [], requests = [], errors = [];
const result = { observedAt: new Date().toISOString(), scope: 'Read-only analyst exploration; all browser POST requests are intercepted and never forwarded.', origin, observations };
const contexts = [];
async function start(name) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  contexts.push(context);
  await context.route('**/api/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    requests.push({ case: name, method: request.method(), path: url.pathname, authorizationPresent: Boolean(request.headers().authorization) });
    if (request.method() !== 'GET') return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: { code: 'review_intercept', message: 'This request was intercepted by the read-only browser review.' } }) });
    return route.continue();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.on('pageerror', error => errors.push({ case: name, message: error.message }));
  await page.goto(origin);
  await page.waitForFunction(() => document.body.innerText.includes('Records API connected'));
  await page.getByRole('button', { name: 'Simulation', exact: true }).click();
  await page.getByLabel('Selected station session').locator('option[value="m16-recovery:session"]').waitFor({ state: 'attached' });
  await page.getByLabel('Selected station session').selectOption('m16-recovery:session');
  await page.getByRole('button', { name: 'Quality and history', exact: true }).click();
  const panel = page.locator('section[aria-label="Gemma evidence analyst"]');
  await panel.locator('section[aria-label="Saved Gemma report"]').waitFor();
  return { context, page, panel };
}
try {
  const first = await start('drafts');
  const before = await first.context.request.get(origin + '/api/v1/station/snapshot').then(response => response.json());
  result.sequenceBefore = before.lastEventSequence;
  const question = first.panel.getByLabel(/Optional evidence question/);
  await question.fill('Cycle question that must survive switching modes.');
  await first.panel.getByRole('button', { name: 'Explain this cycle', exact: true }).click();
  observations.push({ case: 'active mode preserves its draft', observed: await question.inputValue(), expected: 'Cycle question that must survive switching modes.' });
  await question.fill('Cycle draft');
  await first.panel.getByRole('button', { name: 'Compare sessions', exact: true }).click();
  await first.panel.getByLabel('Adaptive session', { exact: true }).selectOption('gemma-eval-classification-mismatch:session');
  await question.fill('Comparison draft');
  await first.panel.getByRole('button', { name: 'Explain this cycle', exact: true }).click();
  observations.push({ case: 'cycle draft is independent of comparison draft', observed: await question.inputValue(), expected: 'Cycle draft' });
  await first.panel.getByRole('button', { name: 'Compare sessions', exact: true }).click();
  observations.push({ case: 'comparison draft is retained', observed: await question.inputValue(), expected: 'Comparison draft' });
  await first.page.screenshot({ path: path.join(output, 'draft-switch.png'), fullPage: true });

  const warning = await start('storage-warning');
  await warning.page.route('**/api/v1/analysis/reports?*', async route => {
    const response = await route.fetch();
    const data = await response.json();
    await route.fulfill({ response, json: { ...data, warnings: [{ code: 'analysis_storage_unavailable', message: 'Some saved analysis evidence cannot be read. New analysis is unavailable until storage is repaired.' }] } });
  });
  await warning.panel.getByRole('button', { name: 'Refresh saved facts and reports', exact: true }).click();
  await warning.page.waitForTimeout(600);
  observations.push({ case: 'storage warning prevents a new analysis', warningVisible: (await warning.panel.innerText()).includes('Some saved analysis evidence cannot be read'), generateDisabled: await warning.panel.getByRole('button', { name: 'Generate cycle explanation', exact: true }).isDisabled(), expected: { warningVisible: true, generateDisabled: true } });
  await warning.page.screenshot({ path: path.join(output, 'storage-warning.png'), fullPage: true });

  const unavailable = await start('read-failure');
  await unavailable.page.route('**/api/v1/analysis/reports?*', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: { code: 'analysis_storage_unavailable', message: 'Some saved analysis evidence cannot be read. New analysis is unavailable until storage is repaired.' } }) }));
  await unavailable.panel.getByRole('button', { name: 'Refresh saved facts and reports', exact: true }).click();
  await unavailable.panel.getByRole('alert').waitFor();
  observations.push({ case: 'failed report refresh prevents a new analysis', alert: await unavailable.panel.getByRole('alert').innerText(), generateDisabled: await unavailable.panel.getByRole('button', { name: 'Generate cycle explanation', exact: true }).isDisabled(), expected: { generateDisabled: true } });
  await unavailable.page.screenshot({ path: path.join(output, 'read-failure.png'), fullPage: true });

  const malformed = await start('malformed-report');
  await malformed.page.route('**/api/v1/analysis/reports?*', async route => {
    const response = await route.fetch();
    const data = await response.json();
    const report = data.reports.find(item => item.status === 'ready');
    report.output.interpretations = null;
    await route.fulfill({ response, json: { reports: [report] } });
  });
  await malformed.panel.getByRole('button', { name: 'Refresh saved facts and reports', exact: true }).click();
  await malformed.page.waitForTimeout(600);
  observations.push({ case: 'malformed report leaves dashboard usable', analystCount: await malformed.panel.count(), bodyTextLength: (await malformed.page.locator('body').innerText()).length, errors: errors.filter(item => item.case === 'malformed-report'), expected: { analystCount: 1, errors: [] } });
  await malformed.page.screenshot({ path: path.join(output, 'malformed-report.png'), fullPage: true });
  const after = await first.context.request.get(origin + '/api/v1/station/snapshot').then(response => response.json());
  result.sequenceAfter = after.lastEventSequence;
  assert.equal(after.lastEventSequence, before.lastEventSequence);
  assert.equal(requests.filter(item => item.method !== 'GET').length, 0);
  result.status = 'observations_saved';
} catch (error) { result.status = 'harness_failed'; result.error = String(error); process.exitCode = 1; }
finally {
  Object.assign(result, { finishedAt: new Date().toISOString(), errors, postCount: requests.filter(item => item.method === 'POST').length });
  await fs.writeFile(path.join(output, 'observations.json'), JSON.stringify(result, null, 2) + '\n');
  await fs.writeFile(path.join(output, 'requests.json'), JSON.stringify(requests, null, 2) + '\n');
  console.log(JSON.stringify({ output, ...result }, null, 2));
  await browser.close();
}
