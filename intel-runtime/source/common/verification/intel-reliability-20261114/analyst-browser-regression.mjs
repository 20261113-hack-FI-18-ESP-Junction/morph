import { chromium } from '../intel-dashboard-bringup/browser-tools/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
assert(process.argv[2], 'Pass the root-owned verification services.json path.');
const settings = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const origin = new URL(settings.uiOrigin).origin;
assert(['127.0.0.1', 'localhost'].includes(new URL(origin).hostname));
const output = path.join(directory, `analyst-regression-${new Date().toISOString().replace(/[:.]/g, '-')}`);
await fs.mkdir(output, { recursive: false });
const executablePath = path.join(directory, '../intel-dashboard-bringup/browser-tools/browsers/chromium_headless_shell-1255/chrome-headless-shell-linux64/chrome-headless-shell');
const browser = await chromium.launch({ headless: true, executablePath, args: ['--disable-dev-shm-usage'] });
const sessionId = 'm16-recovery:session', adaptiveId = 'gemma-eval-classification-mismatch:session';
const g1Id = settings.g1ReportId ?? '561fb240-3ca9-434b-bcef-7bd376b1ed49';
const g2Id = settings.g2ReportId ?? 'ba5d2c29-9477-41d6-8c3e-b39c1a15bd24';
const checks = [], requests = [], pageErrors = [], contexts = [];
const result = { observedAt: new Date().toISOString(), origin, scope: 'Saved simulation UI regression with browser-only fault injection. Every POST is intercepted before the server; no provider job or canonical change is authorized by this harness.', checks };
const clone = value => structuredClone(value);
async function read(context, pathname) {
  const response = await context.request.get(origin + pathname);
  assert(response.ok(), `${pathname}: HTTP ${response.status()}`);
  return response.json();
}
const evidenceContext = await browser.newContext();
contexts.push(evidenceContext);
const original = await read(evidenceContext, '/api/v1/analysis/reports/' + g1Id);
const comparison = await read(evidenceContext, '/api/v1/analysis/reports/' + g2Id);
const savedCycles = await read(evidenceContext, '/api/v1/analysis/reports?sessionId=' + encodeURIComponent(sessionId) + '&cycleId=m16-recovery');
const alternateReportId = savedCycles.reports.find(item => item.reportId !== g1Id && item.context.kind === 'cycle_explanation')?.reportId;
assert(alternateReportId, 'Saved-report switching requires another retained cycle report.');
const baseline = await read(evidenceContext, '/api/v1/station/snapshot');
async function exportHash(id) {
  const data = await read(evidenceContext, '/api/v1/sessions/' + encodeURIComponent(id) + '/export?format=json');
  delete data.exportedAt;
  return createHash('sha256').update(JSON.stringify(data)).digest('hex');
}
const exportBefore = await Promise.all([sessionId, adaptiveId].map(exportHash));
async function start(name) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  contexts.push(context);
  const faults = { list: null, context: null, post: null, read: null };
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.on('pageerror', error => pageErrors.push({ case: name, message: error.message }));
  page.on('request', request => {
    const url = new URL(request.url());
    requests.push({ case: name, method: request.method(), path: url.pathname, sameOrigin: url.origin === origin,
      authorizationPresent: Boolean(request.headers().authorization || request.headers()['x-api-key'] || request.headers()['x-goog-api-key']) });
  });
  await context.route('**/api/**', async route => {
    const request = route.request(), url = new URL(request.url());
    if (request.method() !== 'GET') {
      if (request.method() === 'POST' && url.pathname === '/api/v1/analysis/reports' && faults.post) return faults.post(route);
      return route.fulfill({ status: 503, json: { detail: { code: 'review_intercept', message: 'Write blocked by the browser regression harness.' } } });
    }
    if (url.pathname === '/api/v1/analysis/context' && faults.context) return faults.context(route);
    if (url.pathname === '/api/v1/analysis/reports' && faults.list) return faults.list(route);
    if (url.pathname.startsWith('/api/v1/analysis/reports/') && faults.read) return faults.read(route);
    return route.continue();
  });
  async function selectRecovery() {
    await page.waitForFunction(() => document.body.innerText.includes('Records API connected'));
    if (await page.getByRole('button', { name: 'Simulation', exact: true }).getAttribute('aria-pressed') !== 'true') await page.getByRole('button', { name: 'Simulation', exact: true }).click();
    await page.getByLabel('Selected station session').locator(`option[value="${sessionId}"]`).waitFor({ state: 'attached' });
    await page.getByLabel('Selected station session').selectOption(sessionId);
    await page.getByRole('button', { name: 'Quality and history', exact: true }).click();
  }
  await page.goto(origin);
  await selectRecovery();
  const panel = page.locator('section[aria-label="Gemma evidence analyst"]');
  await panel.getByLabel('Saved reports', { exact: true }).locator(`option[value="${g1Id}"]`).waitFor({ state: 'attached' });
  await panel.getByLabel('Saved reports', { exact: true }).selectOption(g1Id);
  const refresh = async () => { await panel.getByRole('button', { name: 'Refresh saved facts and reports', exact: true }).click(); };
  return { context, page, panel, faults, refresh, selectRecovery, name };
}
async function check(name, action) {
  const test = await start(name);
  try {
    const evidence = await action(test);
    checks.push({ name, status: 'passed', evidence });
  } catch (error) {
    checks.push({ name, status: 'failed', error: String(error) });
    await test.page.screenshot({ path: path.join(output, name + '-failure.png'), fullPage: true }).catch(() => {});
  } finally { await test.context.close(); }
}
try {
  await check('independent-drafts-and-navigation', async ({ page, panel, selectRecovery }) => {
    const question = panel.getByLabel(/Optional evidence question/);
    await question.fill('Cycle question retained across mode changes.');
    await panel.getByRole('button', { name: 'Explain this cycle', exact: true }).click();
    assert.equal(await question.inputValue(), 'Cycle question retained across mode changes.');
    await panel.getByRole('button', { name: 'Compare sessions', exact: true }).click();
    await panel.getByLabel('Adaptive session', { exact: true }).selectOption(adaptiveId);
    await question.fill('Comparison question retained independently.');
    await panel.getByRole('button', { name: 'Explain this cycle', exact: true }).click();
    assert.equal(await question.inputValue(), 'Cycle question retained across mode changes.');
    await page.getByRole('button', { name: 'Robot and system', exact: true }).click();
    await page.getByRole('button', { name: 'Quality and history', exact: true }).click();
    assert.equal(await question.inputValue(), 'Cycle question retained across mode changes.');
    await page.reload();
    await selectRecovery();
    assert.equal(await question.inputValue(), 'Cycle question retained across mode changes.');
    await panel.getByRole('button', { name: 'Compare sessions', exact: true }).click();
    await panel.getByLabel('Adaptive session', { exact: true }).selectOption(adaptiveId);
    assert.equal(await question.inputValue(), 'Comparison question retained independently.');
    await page.screenshot({ path: path.join(output, 'drafts-after-reload.png'), fullPage: true });
    return { activeModeClick: 'preserved', navigation: 'preserved', reload: 'preserved', cycleAndComparison: 'independent' };
  });

  await check('storage-warning-and-read-recovery', async ({ page, panel, faults, refresh }) => {
    const warning = { code: 'analysis_storage_unavailable', message: 'Some saved analysis evidence cannot be read or saved. New analysis is unavailable until storage is repaired and the analysis service is restarted.' };
    faults.list = async route => { const response = await route.fetch(); await route.fulfill({ response, json: { ...await response.json(), warnings: [warning] } }); };
    await refresh();
    await panel.getByRole('alert').filter({ hasText: warning.message }).waitFor();
    assert(await panel.getByRole('button', { name: 'Generate cycle explanation', exact: true }).isDisabled());
    assert.match(await panel.innerText(), /1 \/ 2/);
    await panel.getByLabel('Saved reports', { exact: true }).selectOption(alternateReportId);
    assert(await panel.getByRole('button', { name: 'Generate cycle explanation', exact: true }).isDisabled());
    faults.list = route => route.fulfill({ status: 503, json: { detail: warning } });
    await refresh();
    await panel.getByRole('alert').filter({ hasText: warning.message }).first().waitFor();
    assert(await panel.getByRole('button', { name: 'Generate cycle explanation', exact: true }).isDisabled());
    faults.list = null;
    await refresh();
    await panel.getByRole('button', { name: 'Generate cycle explanation', exact: true }).click({ trial: true });
    assert.equal(await panel.getByRole('alert').count(), 0);
    return { warningVisible: true, failedReadBlocked: true, reportSwitchPreservesFailure: true, healthyRefreshRecovers: true };
  });

  await check('malformed-responses-remain-contained', async ({ page, panel, faults, refresh }) => {
    const malformed = clone(original); malformed.output.interpretations = null;
    faults.list = route => route.fulfill({ json: { reports: [malformed, original, null] } });
    await refresh();
    await panel.getByRole('alert').filter({ hasText: 'Some saved reports have an unreadable format' }).waitFor();
    assert.equal(await panel.count(), 1);
    assert.equal(await panel.getByLabel('Saved reports', { exact: true }).locator('option').count(), 1);
    assert.match(await panel.innerText(), /1 \/ 1/);
    faults.context = route => route.fulfill({ json: { ...clone(original.context), facts: null } });
    await refresh();
    await panel.getByRole('alert').filter({ hasText: 'invalid_response' }).first().waitFor();
    assert.equal(await panel.count(), 1);
    assert(await panel.getByRole('button', { name: 'Generate cycle explanation', exact: true }).isDisabled());
    await page.getByRole('button', { name: 'Robot and system', exact: true }).click();
    await page.getByRole('button', { name: 'Quality and history', exact: true }).click();
    assert.equal(await panel.count(), 1);
    return { malformedReportsSkipped: 2, validReportsRetained: 1, malformedContextContained: true, dashboardNavigationUsable: true };
  });

  await check('saved-report-states-and-safe-prose', async ({ page, panel, faults, refresh }) => {
    const variants = ['rejected', 'failed', 'interrupted'].map(status => ({ ...clone(original), reportId: 'browser-only-' + status, status, output: null,
      validation: { accepted: false, reasons: status === 'rejected' ? ['Unknown source citation in test reply.'] : [] }, error: { code: status === 'failed' ? 'missing_key' : status, message: 'Injected ' + status + ' state.' } }));
    faults.list = route => route.fulfill({ json: { reports: variants } });
    await refresh();
    const reports = panel.getByLabel('Saved reports', { exact: true });
    await reports.locator('option[value="browser-only-rejected"]').waitFor({ state: 'attached' });
    for (const saved of variants) {
      await reports.selectOption(saved.reportId);
      assert.match(await panel.innerText(), /Gemma explanation unavailable/);
      assert.match(await panel.innerText(), /1 \/ 2/);
      if (saved.status === 'failed') assert.match(await panel.innerText(), /Gemma access is not configured/);
    }
    const hostile = clone(original); hostile.reportId = 'browser-only-untrusted';
    hostile.output.headline = '<script>window.untrustedExecuted=true</script>';
    hostile.output.interpretations[0].text = '<img src=x onerror="window.untrustedExecuted=true"> [click](https://invalid.example)';
    faults.list = route => route.fulfill({ json: { reports: [hostile] } });
    await refresh();
    await panel.getByText(hostile.output.headline, { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => window.untrustedExecuted), undefined);
    assert.equal(await panel.locator('a[href="https://invalid.example"]').count(), 0);
    assert.equal(await panel.locator('img[src="x"]').count(), 0);
    return { savedStates: variants.map(item => item.status), factsRetained: true, modelProseEscaped: true };
  });

  await check('lost-response-reload-and-explicit-idempotent-retry', async ({ page, panel, faults, selectRecovery }) => {
    const sent = []; let accepted = null;
    const current = await read(evidenceContext, '/api/v1/analysis/context?kind=cycle_explanation&sessionIds=' + encodeURIComponent(sessionId) + '&cycleId=m16-recovery&sourceMode=simulation');
    faults.post = async route => {
      sent.push(route.request().postDataJSON());
      if (sent.length === 1) return route.abort('failed');
      accepted = { ...clone(original), reportId: 'browser-only-recovered-request', request: sent[1], context: clone(current), status: 'queued', output: null };
      return route.fulfill({ json: accepted });
    };
    faults.read = route => route.fulfill({ json: { ...accepted, status: 'failed', error: { code: 'missing_key', message: 'Browser-only failure after successful persistence.' }, validation: { accepted: false, reasons: [] }, output: null } });
    await panel.getByLabel(/Optional evidence question/).fill('The exact submitted question must survive reload.');
    await panel.getByRole('button', { name: 'Generate cycle explanation', exact: true }).click();
    await panel.getByRole('button', { name: 'Retry the same request', exact: true }).waitFor();
    assert.equal(sent.length, 1);
    await page.reload(); await selectRecovery();
    const retry = panel.getByRole('button', { name: 'Retry the same request', exact: true });
    await retry.waitFor();
    assert.equal(await panel.getByLabel(/Optional evidence question/).inputValue(), sent[0].question);
    assert.equal(sent.length, 1);
    await retry.click();
    await panel.getByText('Gemma access is not configured on this station.', { exact: false }).waitFor();
    assert.equal(sent.length, 2);
    assert.deepEqual(sent[1], sent[0]);
    assert.equal(await panel.getByRole('button', { name: 'Retry the same request', exact: true }).count(), 0);
    return { interceptedPosts: sent.length, requestId: sent[0].requestId, exactPayloadReused: true, reloadPostCount: 0, fakePersistedFailureVisible: true };
  });

  await check('loading-race-and-stale-citation-isolation', async ({ page, panel, faults, refresh }) => {
    const snapshot = clone(original.context);
    snapshot.contentDigest = 'b'.repeat(64);
    snapshot.facts[0].value = { reviewMarker: 'Browser-only updated context' };
    faults.context = async route => {
      const url = new URL(route.request().url());
      if (url.searchParams.get('kind') === 'cycle_explanation') { await new Promise(resolve => setTimeout(resolve, 700)); return route.fulfill({ json: snapshot }); }
      return route.continue();
    };
    await refresh();
    await panel.getByRole('button', { name: 'Compare sessions', exact: true }).click();
    await panel.getByLabel('Adaptive session', { exact: true }).selectOption(adaptiveId);
    await panel.getByLabel('Saved reports', { exact: true }).locator(`option[value="${g2Id}"]`).waitFor({ state: 'attached' });
    await page.waitForTimeout(800);
    assert.match(await panel.innerText(), /Compatibility: unknown/);
    assert.doesNotMatch(await panel.innerText(), /Browser-only updated context/);
    await panel.getByRole('button', { name: 'Explain this cycle', exact: true }).click();
    await panel.getByText('Current facts for explicit regeneration', { exact: true }).waitFor();
    assert.match(await panel.innerText(), /Stale evidence snapshot/);
    const fact = original.context.facts.find(item => item.sourceRefs.some(ref => ref.recordType === 'attempt'));
    const source = fact.sourceRefs[0];
    const facts = panel.locator('section[aria-label="Recorded facts"]').first();
    await facts.locator('summary').filter({ hasText: 'Evidence ledger ·' }).click();
    const summary = facts.locator('summary').filter({ hasText: fact.factId + ' ·' }).first();
    await summary.click();
    await facts.getByRole('button', { name: `Open ${source.recordType} ${source.entityId}, revision ${source.revision}, ${source.fieldPath}`, exact: true }).first().click();
    const dialog = page.getByRole('dialog', { name: 'Cited evidence snapshot' });
    await dialog.waitFor();
    assert.match(await dialog.innerText(), new RegExp('Revision: ' + source.revision));
    await page.keyboard.press('Escape');
    assert.equal(await dialog.count(), 0);
    await panel.getByLabel('Saved reports', { exact: true }).selectOption(alternateReportId);
    assert.match(await panel.locator('section[aria-label="Saved Gemma report"]').innerText(), /Saved question:/);
    return { delayedOldContextDetached: true, staleReportKeepsOriginalFacts: true, sourceRevision: source.revision, keyboardDismissal: true };
  });

  await check('comparison-mobile-keyboard-and-latency', async ({ page, panel }) => {
    const report = panel.locator('section[aria-label="Saved Gemma report"]');
    const measured = original.timings.providerLatencyMs;
    const latency = measured < 1000 ? `${Number(measured.toFixed(1))} ms` : `${(measured / 1000).toFixed(2)} s (${Math.round(measured)} ms)`;
    assert((await report.innerText()).includes(latency));
    assert.match(await report.innerText(), /Saved question:/);
    await panel.getByRole('button', { name: 'Compare sessions', exact: true }).focus();
    await page.keyboard.press('Enter');
    await panel.getByLabel('Adaptive session', { exact: true }).selectOption(adaptiveId);
    await panel.getByLabel('Saved reports', { exact: true }).locator(`option[value="${g2Id}"]`).waitFor({ state: 'attached' });
    await panel.getByLabel('Saved reports', { exact: true }).selectOption(g2Id);
    assert.equal(comparison.output.answerState, 'insufficient_evidence');
    for (const item of comparison.output.interpretations) assert((await report.innerText()).includes(item.text));
    assert.match(await panel.innerText(), /Compatibility: unknown/);
    assert.equal(await panel.getByRole('table').count(), 1);
    const viewports = [];
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
      const dimensions = await page.evaluate(() => ({ width: innerWidth, documentWidth: document.documentElement.scrollWidth }));
      assert.equal(dimensions.width, dimensions.documentWidth);
      await page.screenshot({ path: path.join(output, `comparison-${width}.png`), fullPage: true });
      viewports.push(dimensions);
    }
    return { actualG1Report: g1Id, actualG1LatencyReadable: latency, actualG2Report: g2Id, actualG2Interpretations: comparison.output.interpretations, compatibleClaim: false, viewports, keyboardModeActivation: true };
  });
  const after = await read(evidenceContext, '/api/v1/station/snapshot');
  const exportAfter = await Promise.all([sessionId, adaptiveId].map(exportHash));
  assert.equal(after.lastEventSequence, baseline.lastEventSequence);
  assert.deepEqual(exportAfter, exportBefore);
  assert.equal(requests.filter(item => item.authorizationPresent).length, 0);
  assert.deepEqual(pageErrors, []);
  checks.push({ name: 'read-only-canonical-invariance', status: 'passed', evidence: { sequenceBefore: baseline.lastEventSequence, sequenceAfter: after.lastEventSequence, exportsBefore: exportBefore, exportsAfter: exportAfter, realServerPosts: 0, interceptedPosts: requests.filter(item => item.method === 'POST').length, pageErrors } });
  result.status = checks.every(item => item.status === 'passed') ? 'passed' : 'failed';
  if (result.status !== 'passed') process.exitCode = 1;
} catch (error) { result.status = 'failed'; result.error = String(error); process.exitCode = 1; }
finally {
  Object.assign(result, { finishedAt: new Date().toISOString(), browserVersion: browser.version(), pageErrors });
  await fs.writeFile(path.join(output, 'browser-results.json'), JSON.stringify(result, null, 2) + '\n');
  await fs.writeFile(path.join(output, 'browser-requests.json'), JSON.stringify(requests, null, 2) + '\n');
  console.log(JSON.stringify({ output, ...result }, null, 2));
  await browser.close();
}
