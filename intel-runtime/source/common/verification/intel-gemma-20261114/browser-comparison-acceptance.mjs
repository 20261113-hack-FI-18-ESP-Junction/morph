import { chromium } from '../intel-dashboard-bringup/browser-tools/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const settingsPath = path.resolve(process.argv[2] ?? path.join(directory, 'runs/hosted-03/services.json'));
const settings = JSON.parse(await fs.readFile(settingsPath, 'utf8'));
const origin = new URL(settings.uiOrigin).origin;
assert(['127.0.0.1', 'localhost'].includes(new URL(origin).hostname));
const runStamp = new Date().toISOString().replace(/[:.]/g, '-');
const output = path.join(path.dirname(settingsPath), `browser-g2-v8-${runStamp}`);
await fs.mkdir(output, { recursive: false });
const reportId = 'ba5d2c29-9477-41d6-8c3e-b39c1a15bd24';
const baselineId = 'm16-recovery:session';
const adaptiveId = 'gemma-eval-classification-mismatch:session';
const expectedSentence = 'Configuration identifiers alone do not establish reviewed matching protocol, population, settings and timing boundaries.';
const requests = [], pageErrors = [], checks = [];
const result = {
  observedAt: new Date().toISOString(), status: 'running', reportId, uiOrigin: origin,
  scope: 'Read-only Chromium verification of the already persisted hosted Gemma v8 session comparison. No inference or physical control.',
  checks,
};
const executablePath = path.resolve(directory, '../intel-dashboard-bringup/browser-tools/browsers/chromium_headless_shell-1255/chrome-headless-shell-linux64/chrome-headless-shell');
const browser = await chromium.launch({ headless: true, executablePath, args: ['--disable-dev-shm-usage'] });
const browserContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await browserContext.newPage();
page.setDefaultTimeout(20000);
page.on('pageerror', error => pageErrors.push(error.message));
page.on('request', request => {
  const url = new URL(request.url());
  const headers = request.headers();
  requests.push({ method: request.method(), path: url.pathname, sameOrigin: url.origin === origin,
    authorizationPresent: Boolean(headers.authorization || headers['x-goog-api-key'] || headers['x-api-key']) });
});
const read = async pathname => {
  const response = await browserContext.request.get(origin + pathname);
  assert(response.ok(), `Read ${pathname} returned HTTP ${response.status()}`);
  return response.json();
};
const panel = () => page.locator('section[aria-label="Gemma evidence analyst"]');
try {
  const before = await read('/api/v1/station/snapshot');
  assert.equal(before.lastEventSequence, 126);
  const saved = await read(`/api/v1/analysis/reports/${reportId}`);
  assert.equal(saved.status, 'ready');
  assert.equal(saved.validation.accepted, true);
  assert.equal(saved.output.answerState, 'insufficient_evidence');
  assert.equal(saved.context.kind, 'session_comparison');
  assert.equal(saved.context.sourceMode, 'simulation');
  assert.equal(saved.context.compatibility.state, 'unknown');
  assert.deepEqual(saved.context.descriptiveDeltas, []);
  assert.deepEqual(saved.context.comparisonRoles, { baselineSessionId: baselineId, adaptiveSessionId: adaptiveId });
  assert(saved.output.interpretations.some(item => item.text === expectedSentence));
  checks.push({ name: 'Actual persisted v8 comparison is ready and explicitly insufficient', status: 'passed',
    evidence: { reportId, answerState: saved.output.answerState, compatibility: saved.context.compatibility.state, descriptiveDeltas: [], provenance: saved.provenance, timings: saved.timings } });

  await page.goto(origin);
  await page.waitForFunction(() => document.body.innerText.includes('Records API connected'));
  await page.getByRole('button', { name: 'Simulation', exact: true }).click();
  await page.getByLabel('Selected station session').locator(`option[value="${baselineId}"]`).waitFor({ state: 'attached' });
  await page.getByLabel('Selected station session').selectOption(baselineId);
  await page.getByRole('button', { name: 'Quality and history', exact: true }).click();
  await panel().getByRole('button', { name: 'Compare sessions', exact: true }).click();
  await panel().getByLabel('Baseline session', { exact: true }).selectOption(baselineId);
  await panel().getByLabel('Adaptive session', { exact: true }).selectOption(adaptiveId);
  const reports = panel().getByLabel('Saved reports', { exact: true });
  await reports.locator(`option[value="${reportId}"]`).waitFor({ state: 'attached' });
  await reports.selectOption(reportId);
  const interpretation = panel().locator('section[aria-label="Saved Gemma report"]');
  await interpretation.getByText(expectedSentence, { exact: true }).waitFor();
  assert.match(await interpretation.innerText(), /Insufficient evidence to answer the full question/);
  assert.match(await panel().innerText(), /Compatibility: unknown/);
  assert.equal(await panel().getByRole('table').count(), 1);
  const table = await panel().getByRole('table').innerText();
  assert(table.includes('Baseline') && table.includes('Adaptive'));
  assert(table.includes(baselineId) && table.includes(adaptiveId));
  assert.match(table, /Correct finished cycles/);
  assert.match(table, /1 \/ 1/);
  assert.match(table, /0 \/ 1/);
  assert.doesNotMatch(await panel().innerText(), /percentage points/);
  assert.match(await panel().innerText(), /PERSISTED SIMULATION/);
  assert.match(await interpretation.innerText(), /gemma-4-26b-a4b-it/);
  checks.push({ name: 'UI shows the actual insufficient-evidence paragraph and descriptive tables without deltas', status: 'passed',
    evidence: { selectedReportId: await reports.inputValue(), expectedSentence, comparisonTable: table } });

  const viewports = [];
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    const dimensions = await page.evaluate(() => ({ innerWidth, scrollWidth: document.documentElement.scrollWidth }));
    assert.equal(dimensions.scrollWidth, dimensions.innerWidth);
    const label = width === 390 ? 'mobile' : 'desktop';
    await page.screenshot({ path: path.join(output, `${label}-comparison.png`), fullPage: true });
    await interpretation.screenshot({ path: path.join(output, `${label}-actual-gemma-comparison.png`) });
    viewports.push(dimensions);
  }
  checks.push({ name: 'Actual comparison renders at desktop and mobile widths without document overflow', status: 'passed', evidence: viewports });
  const after = await read('/api/v1/station/snapshot');
  assert.equal(after.lastEventSequence, before.lastEventSequence);
  assert(requests.every(request => request.method === 'GET' && request.sameOrigin && !request.authorizationPresent));
  assert.deepEqual(pageErrors, []);
  checks.push({ name: 'No new inference request, browser credential or canonical event', status: 'passed',
    evidence: { postCount: requests.filter(request => request.method === 'POST').length, sequenceBefore: before.lastEventSequence, sequenceAfter: after.lastEventSequence, pageErrors } });
  result.status = 'passed';
} catch (error) {
  result.status = 'failed';
  result.error = String(error);
  await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {});
  process.exitCode = 1;
} finally {
  Object.assign(result, { finishedAt: new Date().toISOString(), browserVersion: browser.version(), requestCount: requests.length, pageErrors });
  await fs.writeFile(path.join(output, 'browser-results.json'), JSON.stringify(result, null, 2) + '\n');
  await fs.writeFile(path.join(output, 'browser-requests.json'), JSON.stringify(requests, null, 2) + '\n');
  console.log(JSON.stringify({ status: result.status, output, checks, error: result.error ?? null }, null, 2));
  await browser.close();
}
