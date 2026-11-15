import { chromium } from '../intel-dashboard-bringup/browser-tools/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const settings = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const expectedPromptVersion = process.argv[3] ?? settings.expectedPromptVersion ?? 'gemma-evidence-v9';
const origin = new URL(settings.uiOrigin).origin;
assert.equal(origin, 'http://127.0.0.1:50139', 'This single explicitly authorized hosted action targets the promoted owner preview only.');
const output = path.join(directory, `deployed-browser-inference-${new Date().toISOString().replace(/[:.]/g, '-')}`);
await fs.mkdir(output, { recursive: false });
await fs.copyFile(fileURLToPath(import.meta.url), path.join(output, 'harness.mjs'));
const executablePath = path.join(directory, '../intel-dashboard-bringup/browser-tools/browsers/chromium_headless_shell-1255/chrome-headless-shell-linux64/chrome-headless-shell');
const browser = await chromium.launch({ headless: true, executablePath, args: ['--disable-dev-shm-usage'] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
page.setDefaultTimeout(20000);
const requests = [], errors = [], checks = [];
let sent = null, reportId = null, postCount = 0;
const result = { observedAt: new Date().toISOString(), origin, expectedPromptVersion, scope: 'One root-authorized explicit hosted Gemma G1 action on the promoted dashboard, followed only by read-only navigation, reload and result recovery.', checks };
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => {
  const url = new URL(request.url());
  requests.push({ method: request.method(), path: url.pathname, sameOrigin: url.origin === origin, authorizationPresent: Boolean(request.headers().authorization || request.headers()['x-goog-api-key'] || request.headers()['x-api-key']) });
});
await context.route('**/api/**', route => {
  const request = route.request(), url = new URL(request.url());
  if (request.method() === 'GET') return route.continue();
  if (request.method() === 'POST' && url.pathname === '/api/v1/analysis/reports' && postCount === 0) {
    postCount++;
    sent = request.postDataJSON();
    return route.continue();
  }
  return route.abort('blockedbyclient');
});
async function read(pathname) {
  const response = await context.request.get(origin + pathname);
  assert(response.ok(), pathname + ' HTTP ' + response.status());
  return response.json();
}
async function exportHash() {
  const value = await read('/api/v1/sessions/m16-recovery%3Asession/export?format=json');
  delete value.exportedAt;
  return createHash('sha256').update(JSON.stringify(value)).digest('hex');
}
async function selectRecovery() {
  await page.waitForFunction(() => document.body.innerText.includes('Records API connected'));
  if (await page.getByRole('button', { name: 'Simulation', exact: true }).getAttribute('aria-pressed') !== 'true') await page.getByRole('button', { name: 'Simulation', exact: true }).click();
  await page.getByLabel('Selected station session').locator('option[value="m16-recovery:session"]').waitFor({ state: 'attached' });
  await page.getByLabel('Selected station session').selectOption('m16-recovery:session');
  await page.getByRole('button', { name: 'Quality and history', exact: true }).click();
}
try {
  const before = await read('/api/v1/station/snapshot');
  const beforeHash = await exportHash();
  await page.goto(origin); await selectRecovery();
  const panel = page.locator('section[aria-label="Gemma evidence analyst"]');
  const generate = panel.getByRole('button', { name: 'Generate cycle explanation', exact: true });
  await generate.click({ trial: true });
  assert.equal(postCount, 0);
  const question = expectedPromptVersion === 'gemma-evidence-v9'
    ? 'Explain this saved recovery cycle using the separate finished-cycle and finished-attempt denominators. Preserve the earlier failed attempt, retry, historical unverified outcome and late-confirmation audit. Cite the evidence and state what the records cannot establish about physical cause.'
    : 'Explain how the correct finished-cycle result coexists with the failed and successful physical attempts. Cite both attempts and preserve the retry, historical unverified outcome and late-confirmation audit. State what evidence is missing to establish a physical cause.';
  await panel.getByLabel(/Optional evidence question/).fill(question);
  const responsePromise = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/v1/analysis/reports');
  const clickedAt = new Date().toISOString();
  await generate.click();
  const response = await responsePromise;
  const submitted = await response.json();
  assert(response.ok(), 'Explicit submission HTTP ' + response.status());
  reportId = submitted.reportId;
  assert.equal(sent.question, question);
  assert.equal(submitted.request.requestId, sent.requestId);
  await fs.writeFile(path.join(output, 'actual-request.json'), JSON.stringify(sent, null, 2) + '\n');
  await fs.writeFile(path.join(output, 'submission-response.json'), JSON.stringify(submitted, null, 2) + '\n');
  checks.push({ name: 'One explicit browser action created the actual analysis job', status: 'passed', evidence: { clickedAt, requestId: sent.requestId, reportId, httpStatus: response.status(), initialStatus: submitted.status, cacheReused: submitted.cacheReused ?? false } });
  await page.getByRole('button', { name: 'Robot and system', exact: true }).click();
  await page.reload();
  await selectRecovery();
  const reports = panel.getByLabel('Saved reports', { exact: true });
  await reports.locator(`option[value="${reportId}"]`).waitFor({ state: 'attached' });
  await reports.selectOption(reportId);
  const deadline = Date.now() + 90000;
  let completed = await read('/api/v1/analysis/reports/' + reportId);
  while (['queued', 'running'].includes(completed.status) && Date.now() < deadline) {
    await page.waitForTimeout(1000);
    completed = await read('/api/v1/analysis/reports/' + reportId);
  }
  await fs.writeFile(path.join(output, 'actual-report.json'), JSON.stringify(completed, null, 2) + '\n');
  await panel.getByRole('button', { name: 'Refresh saved facts and reports', exact: true }).click();
  await reports.locator(`option[value="${reportId}"]`).waitFor({ state: 'attached' });
  await reports.selectOption(reportId);
  const displayed = panel.locator('section[aria-label="Saved Gemma report"]');
  await displayed.getByText(completed.status.toUpperCase(), { exact: true }).waitFor();
  await displayed.screenshot({ path: path.join(output, 'actual-report-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await displayed.screenshot({ path: path.join(output, 'actual-report-mobile.png') });
  const after = await read('/api/v1/station/snapshot');
  const afterHash = await exportHash();
  assert.equal(after.lastEventSequence, before.lastEventSequence);
  assert.equal(afterHash, beforeHash);
  assert.equal(postCount, 1);
  assert.equal(requests.filter(item => item.method === 'POST').length, 1);
  assert.equal(requests.filter(item => item.authorizationPresent).length, 0);
  assert.deepEqual(errors, []);
  checks.push({ name: 'Navigation and reload recover the persisted job without resubmission or canonical changes', status: 'passed', evidence: { postCount, sequenceBefore: before.lastEventSequence, sequenceAfter: after.lastEventSequence, exportBefore: beforeHash, exportAfter: afterHash, errors } });
  Object.assign(result, { reportId, terminalStatus: completed.status, provenance: completed.provenance, timings: completed.timings, output: completed.output, validation: completed.validation, error: completed.error });
  assert.equal(completed.status, 'ready', 'Actual reply was not accepted; preserve the terminal result without another cloud call.');
  assert.equal(completed.validation.accepted, true);
  assert.equal(completed.provenance.requestedModel, 'gemma-4-26b-a4b-it');
  assert.equal(completed.provenance.returnedModel, 'gemma-4-26b-a4b-it');
  assert.equal(completed.provenance.promptVersion, expectedPromptVersion);
  assert.equal(completed.cacheReused ?? false, false);
  for (const item of completed.output.interpretations) assert((await displayed.innerText()).includes(item.text));
  assert.match(await panel.innerText(), /1 \/ 1/);
  assert.match(await panel.innerText(), /1 \/ 2/);
  checks.push({ name: 'Actual hosted Gemma reply is accepted and rendered with its recorded provenance', status: 'passed', evidence: { reportId, model: completed.provenance.returnedModel, promptVersion: completed.provenance.promptVersion, providerLatencyMs: completed.timings.providerLatencyMs, reportTotalMs: completed.timings.reportTotalMs } });
  if (expectedPromptVersion !== 'gemma-evidence-v9') {
    const rejectedId = '9b0f843b-c75d-41b3-b3f1-26877d4bae41';
    await reports.selectOption(rejectedId);
    await displayed.getByText("Gemma's reply did not pass the evidence checks. The saved facts remain available.", { exact: false }).waitFor();
    await displayed.getByText('Validation result', { exact: true }).click();
    assert.match(await displayed.innerText(), /unsupported_cycle_headline/);
    await displayed.screenshot({ path: path.join(output, 'retained-v9-rejection-plain-language.png') });
    await reports.selectOption(reportId);
    checks.push({ name: 'The retained rejected report uses plain language while preserving its exact validation code', status: 'passed', evidence: { rejectedReportId: rejectedId, validationCode: 'unsupported_cycle_headline' } });
  }
  result.status = 'passed';
} catch (error) { result.status = 'failed'; result.failure = String(error); process.exitCode = 1; await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: false }).catch(() => {}); }
finally {
  Object.assign(result, { finishedAt: new Date().toISOString(), postCount, reportId, errors });
  await fs.writeFile(path.join(output, 'browser-results.json'), JSON.stringify(result, null, 2) + '\n');
  await fs.writeFile(path.join(output, 'browser-requests.json'), JSON.stringify(requests, null, 2) + '\n');
  console.log(JSON.stringify({ ...result, outputDirectory: output }, null, 2));
  await browser.close();
}
