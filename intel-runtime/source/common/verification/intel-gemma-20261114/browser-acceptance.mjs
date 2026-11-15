import { chromium } from '../intel-dashboard-bringup/browser-tools/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const settingsPath = path.resolve(process.argv[2] ?? path.join(directory, 'services.json'));
const settings = JSON.parse(await fs.readFile(settingsPath, 'utf8'));
const reuseIndex = process.argv.indexOf('--reuse-report');
const reuseReportId = reuseIndex >= 0 ? process.argv[reuseIndex + 1] : null;
if (reuseIndex >= 0) assert(reuseReportId, '--reuse-report requires a saved report identifier.');
const expectedPosts = reuseReportId ? 0 : 1;
const origin = new URL(settings.uiOrigin).origin;
assert(['127.0.0.1', 'localhost'].includes(new URL(origin).hostname), 'Acceptance must target the isolated local application.');
const output = path.resolve(settings.output ?? path.join(directory, 'browser'));
await fs.mkdir(output, { recursive: true });
process.env.PLAYWRIGHT_BROWSERS_PATH ??= path.resolve(directory, '../intel-dashboard-bringup/browser-tools/browsers');

const checks = [], requests = [], pageErrors = [];
const recoveryId = 'm16-recovery:session';
const comparisonId = 'gemma-eval-classification-mismatch:session';
const result = {
  observedAt: new Date().toISOString(), status: 'running',
  evidenceType: reuseReportId ? 'Actual Chromium UI against isolated saved simulation and a previously persisted hosted Gemma report; no new inference or physical control.' : 'Actual Chromium UI against isolated saved simulation; one explicit hosted Gemma cycle action, read-only comparison/replay, no physical control.',
  reusedReportId: reuseReportId,
  services: { uiOrigin: origin, dataDirectory: settings.dataDirectory ?? null }, checks,
  hostedResponse: null,
};
const browserExecutable = path.resolve(directory, '../intel-dashboard-bringup/browser-tools/browsers/chromium_headless_shell-1255/chrome-headless-shell-linux64/chrome-headless-shell');
const browser = await chromium.launch({ headless: true, executablePath: browserExecutable, args: ['--disable-dev-shm-usage'] }).catch(async error => {
  Object.assign(result, { status: 'failed', error: String(error), stage: 'browser_launch' });
  await fs.writeFile(path.join(output, 'browser-results.json'), JSON.stringify(result, null, 2) + '\n');
  throw error;
});
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
page.setDefaultTimeout(25000);
page.on('pageerror', error => pageErrors.push(error.message));
page.on('request', request => {
  const url = new URL(request.url());
  const headers = request.headers();
  requests.push({ method: request.method(), path: url.pathname, sameOrigin: url.origin === origin,
    authorizationPresent: Boolean(headers.authorization || headers['x-goog-api-key'] || headers['x-api-key']),
    analysisIntent: headers['x-morph-intent'] === 'evidence-analysis' });
});
const postCount = () => requests.filter(request => request.method === 'POST').length;
const panel = () => page.locator('section[aria-label="Gemma evidence analyst"]');
const factsPanel = () => panel().locator('section[aria-label="Recorded facts"]').first();
const reportPanel = () => panel().locator('section[aria-label="Saved Gemma report"]');
const text = () => page.locator('body').innerText();
const waitBody = needle => page.waitForFunction(needle => document.body.innerText.includes(needle), needle);
const read = async pathname => {
  requests.push({ method: 'GET', path: pathname.split('?')[0], sameOrigin: true, authorizationPresent: false, harnessRead: true });
  const response = await context.request.get(origin + pathname);
  assert(response.ok(), `Read ${pathname.split('?')[0]} failed with HTTP ${response.status()}`);
  return response.json();
};
function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, stable(value[key])]));
  return value;
}
function digestExport(value) {
  const { exportedAt, ...saved } = value;
  return createHash('sha256').update(JSON.stringify(stable(saved))).digest('hex');
}
const readExport = id => read(`/api/v1/sessions/${encodeURIComponent(id)}/export?format=json`);
const check = async (name, fn) => {
  const startedAt = new Date().toISOString();
  try { const evidence = await fn(); checks.push({ name, status: 'passed', startedAt, evidence: evidence ?? null }); return true; }
  catch (error) { checks.push({ name, status: 'failed', startedAt, error: String(error) }); return false; }
};
async function selectRecovery() {
  await page.getByRole('button', { name: 'Simulation', exact: true }).click();
  await page.getByLabel('Selected station session').locator(`option[value="${recoveryId}"]`).waitFor({ state: 'attached' });
  await page.getByLabel('Selected station session').selectOption(recoveryId);
  await waitBody('Records API connected');
  await page.getByRole('button', { name: 'Quality and history', exact: true }).click();
  await panel().waitFor();
  await factsPanel().getByText('Correct finished cycles', { exact: true }).first().waitFor();
  assert.equal(await page.getByLabel('Selected station session').inputValue(), recoveryId);
}
async function metricValue(label) {
  return (await factsPanel().getByText(label, { exact: true }).first().locator('xpath=following-sibling::div[1]').innerText()).trim();
}
async function assertRecoveryFacts() {
  const values = {};
  for (const [label, expected] of [['Correct finished cycles', '1 / 1'], ['Successful finished attempts', '1 / 2'], ['Retries', '1'], ['Recovered cycles', '1'], ['First-attempt successes', '0']]) {
    values[label] = await metricValue(label);
    assert.equal(values[label], expected, label);
  }
  assert.match(await panel().innerText(), /Persisted simulation/i);
  return values;
}
async function screenshot(name) {
  const filename = name + '.png';
  await page.screenshot({ path: path.join(output, filename), fullPage: !name.includes('citation') && !name.includes('audit') });
  return filename;
}
async function openCitedFact(container, fact, source) {
  await container.locator('summary').filter({ hasText: `${fact.factId} ·` }).first().click();
  const button = container.getByRole('button', { name: `Open ${source.recordType} ${source.entityId}, revision ${source.revision}, ${source.fieldPath}`, exact: true }).first();
  await button.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: 'Cited evidence snapshot', exact: true });
  await dialog.waitFor();
  assert.match(await dialog.innerText(), new RegExp(source.entityId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert((await dialog.innerText()).includes(`Revision: ${source.revision}`));
  assert(await dialog.evaluate(element => element.contains(document.activeElement)));
  await page.keyboard.press('Shift+Tab');
  assert(await dialog.evaluate(element => element.contains(document.activeElement)));
  await page.keyboard.press('Tab');
  assert(await dialog.evaluate(element => element.contains(document.activeElement)));
  return dialog;
}

let beforeSnapshot, beforeRecovery, beforeComparison, actualReport;
try {
  beforeSnapshot = await read('/api/v1/station/snapshot');
  beforeRecovery = await readExport(recoveryId);
  beforeComparison = await readExport(comparisonId);
  await page.goto(origin);
  await waitBody('Records API connected');
  await selectRecovery();
  await check('Opening and navigating to saved recovery fetches facts without inference', async () => {
    assert.equal(postCount(), 0);
    await page.getByRole('button', { name: 'Robot and system', exact: true }).click();
    await page.getByRole('button', { name: 'Quality and history', exact: true }).click();
    await panel().getByRole('button', { name: 'Refresh saved facts and reports', exact: true }).click();
    await page.waitForTimeout(300);
    assert.equal(postCount(), 0);
    return assertRecoveryFacts();
  });
  await screenshot('desktop-recorded-facts');
  await check(reuseReportId ? 'A previously persisted hosted result renders without a new inference request' : 'An explicit cycle action produces one persisted hosted Gemma result', async () => {
    let queued;
    if (reuseReportId) {
      queued = await read(`/api/v1/analysis/reports/${encodeURIComponent(reuseReportId)}`);
      await panel().getByLabel('Saved reports', { exact: true }).selectOption(reuseReportId);
    } else {
      await panel().getByLabel(/Optional evidence question/).fill('Explain how correct-cycle and successful-attempt denominators coexist. Cite the failed first attempt, successful retry, late confirmation, and the missing independent failure cause.');
      const responsePromise = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/v1/analysis/reports');
      await panel().getByRole('button', { name: 'Generate cycle explanation', exact: true }).click();
      const response = await responsePromise;
      assert(response.ok(), `Explicit analysis returned HTTP ${response.status()}`);
      queued = await response.json();
    }
    assert(queued.reportId, 'A persisted report identifier is required.');
    const deadline = Date.now() + 65000;
    do {
      actualReport = await read(`/api/v1/analysis/reports/${encodeURIComponent(queued.reportId)}`);
      if (!['queued', 'running'].includes(actualReport.status)) break;
      await page.waitForTimeout(500);
    } while (Date.now() < deadline);
    result.hostedResponse = { reportId: actualReport.reportId, status: actualReport.status, freshness: actualReport.freshness,
      validation: actualReport.validation, provenance: actualReport.provenance, timings: actualReport.timings,
      error: actualReport.error, cacheReused: queued.cacheReused ?? false };
    assert.equal(postCount(), expectedPosts, 'Only the explicit action may submit an analysis.');
    assert(!['queued', 'running'].includes(actualReport.status), 'The hosted job did not reach a terminal state.');
    await page.waitForFunction(status => [...document.querySelectorAll('section[aria-label="Saved Gemma report"]')].some(element => element.innerText.includes(status.toUpperCase())), actualReport.status);
    await assertRecoveryFacts();
    await screenshot('desktop-hosted-report');
    if (actualReport.status !== 'ready') {
      assert.match(await reportPanel().innerText(), /Gemma explanation unavailable/);
      throw new Error(`Actual hosted reply was ${actualReport.status}: ${actualReport.error?.code ?? 'unknown'}. UI retained facts; useful hosted acceptance is not established.`);
    }
    assert.equal(actualReport.validation.accepted, true);
    assert.equal(actualReport.provenance.requestedModel, 'gemma-4-26b-a4b-it');
    assert.equal(typeof actualReport.timings.providerLatencyMs, 'number');
    assert.match(await reportPanel().innerText(), /gemma-4-26b-a4b-it/);
    assert.match(await reportPanel().innerText(), /Measured provider latency:/);
    const cited = new Set(actualReport.output.interpretations.flatMap(item => item.factIds));
    const citedFacts = actualReport.context.facts.filter(fact => cited.has(fact.factId));
    const coverage = {
      failedAttempt: citedFacts.some(fact => fact.sourceRefs.some(source => source.recordType === 'attempt') && fact.value.outcome === 'failed'),
      successfulRetry: citedFacts.some(fact => fact.sourceRefs.some(source => source.recordType === 'attempt') && fact.value.outcome === 'successful'),
      confirmation: citedFacts.some(fact => fact.sourceRefs.some(source => source.recordType === 'confirmation')),
    };
    result.citationCoverage = coverage;
    assert(Object.values(coverage).every(Boolean), 'Recovery synthesis must cite failure, successful retry and confirmation.');
    return { reportId: actualReport.reportId, status: actualReport.status, coverage, measuredProviderLatencyMs: actualReport.timings.providerLatencyMs };
  });

  if (actualReport?.status === 'ready') await check('Accepted explanation citations open their captured revision with keyboard focus', async () => {
    const cited = new Set(actualReport.output.interpretations.flatMap(item => item.factIds));
    const fact = actualReport.context.facts.find(item => cited.has(item.factId) && item.value.outcome === 'failed' && item.sourceRefs.some(source => source.recordType === 'attempt'));
    assert(fact, 'An actual cited failed attempt is required.');
    const source = fact.sourceRefs.find(item => item.recordType === 'attempt');
    const dialog = await openCitedFact(reportPanel(), fact, source);
    assert.match(await dialog.innerText(), /failed/);
    assert.match(await dialog.innerText(), /Captured evidence values/);
    assert.match(await dialog.innerText(), /Open current cycle trace/);
    await screenshot('desktop-failed-attempt-citation');
    await page.keyboard.press('Escape');
    assert.equal(await page.getByRole('dialog').count(), 0);
    assert.match(await page.locator(':focus').getAttribute('aria-label'), /^Open attempt /);
    return { factId: fact.factId, entityId: source.entityId, revision: source.revision };
  });

  if (actualReport?.context) await check('Late-confirmation audit retains old/new values, author and untrusted reason', async () => {
    const fact = actualReport.context.facts.find(item => item.sourceRefs.some(source => source.recordType === 'correction'));
    assert(fact, 'Saved recovery must contain its correction audit.');
    await factsPanel().locator('summary').filter({ hasText: 'Evidence ledger' }).click();
    const source = fact.sourceRefs.find(item => item.recordType === 'correction');
    const dialog = await openCitedFact(factsPanel(), fact, source);
    const content = await dialog.innerText();
    for (const field of ['previousValue', 'newValue', 'authorId', 'createdAt']) assert(content.includes(field), `Audit is missing ${field}`);
    const note = actualReport.context.untrustedExcerpts?.find(item => item.sourceRef.recordType === 'correction' && item.sourceRef.entityId === source.entityId && item.sourceRef.revision === source.revision);
    if (note) { assert(content.includes(note.text)); assert(content.includes('untrusted explanatory text')); }
    await screenshot('desktop-late-confirmation-audit');
    await page.keyboard.press('Escape');
    return { entityId: source.entityId, revision: source.revision, notePresent: Boolean(note) };
  });

  await check('Reload, saved-report selection, replay and refresh do not add requests or change counters', async () => {
    const count = postCount();
    await page.reload();
    await waitBody('Records API connected');
    await selectRecovery();
    await assertRecoveryFacts();
    await page.getByRole('button', { name: 'Replay', exact: true }).click();
    await page.getByRole('heading', { name: 'Read-only historical replay', exact: true }).waitFor();
    await panel().getByText('No saved report with a verified matching historical digest is available.').waitFor({ state: 'hidden', timeout: 4000 }).catch(() => {});
    const next = page.getByRole('button', { name: 'Next replay event', exact: true });
    if (await next.isEnabled()) await next.click();
    await panel().getByRole('button', { name: 'Refresh saved facts and reports', exact: true }).click();
    await page.waitForTimeout(300);
    assert.equal(await panel().getByRole('button', { name: /Generate .*explanation|Generate session comparison/ }).count(), 0);
    assert.equal(postCount(), count);
    assert.match(await panel().innerText(), /READ-ONLY REPLAY/);
    const matchedReport = await reportPanel().count() > 0;
    if (matchedReport) await assertRecoveryFacts();
    else assert.match(await panel().innerText(), /No saved report with a verified matching historical digest/);
    assert.match(await text(), /1 correct \/ 1 finished cycles/);
    await screenshot('desktop-replay');
    return { postCount: count, exactHistoricalReportAvailable: matchedReport };
  });

  await check('Comparison shows descriptive baseline/adaptive evidence and missing compatibility', async () => {
    await selectRecovery();
    await panel().getByRole('button', { name: 'Compare sessions', exact: true }).click();
    await panel().getByLabel('Baseline session', { exact: true }).selectOption(recoveryId);
    await panel().getByLabel('Adaptive session', { exact: true }).selectOption(comparisonId);
    await panel().getByText('Insufficient comparison evidence', { exact: true }).first().waitFor();
    assert.match(await panel().innerText(), /Compatibility: unknown/);
    assert.match(await panel().innerText(), /descriptive session results/);
    assert.equal(await panel().getByRole('table').count(), 1);
    assert.match(await panel().getByRole('table').innerText(), /Baseline/);
    assert.match(await panel().getByRole('table').innerText(), /Adaptive/);
    await screenshot('desktop-insufficient-comparison');
    return { sourceMode: 'simulation', baselineSessionId: recoveryId, adaptiveSessionId: comparisonId, inferenceTriggered: false };
  });

  await check('Analyst and comparison fit desktop and mobile widths without document overflow', async () => {
    const layouts = [];
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
      const dimensions = await page.evaluate(() => ({ innerWidth, scrollWidth: document.documentElement.scrollWidth }));
      layouts.push(dimensions);
      assert(dimensions.scrollWidth <= dimensions.innerWidth, `Document overflow at ${width}px: ${dimensions.scrollWidth}`);
      await screenshot(width === 390 ? 'mobile-insufficient-comparison' : 'desktop-comparison-layout');
      await panel().getByRole('button', { name: 'Explain this cycle', exact: true }).click();
      await factsPanel().getByText('Correct finished cycles', { exact: true }).first().waitFor();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Cycle panel overflows at ${width}px`);
      await screenshot(width === 390 ? 'mobile-cycle-report' : 'desktop-cycle-layout');
      if (width === 1440) {
        await panel().getByRole('button', { name: 'Compare sessions', exact: true }).click();
        await panel().getByText('Insufficient comparison evidence', { exact: true }).first().waitFor();
      }
    }
    return layouts;
  });

  await check('Canonical exports and event sequence remain unchanged; browser has no authorization credentials', async () => {
    const afterSnapshot = await read('/api/v1/station/snapshot');
    const afterRecovery = await readExport(recoveryId);
    const afterComparison = await readExport(comparisonId);
    assert.equal(afterSnapshot.lastEventSequence, beforeSnapshot.lastEventSequence);
    assert.equal(digestExport(afterRecovery), digestExport(beforeRecovery));
    assert.equal(digestExport(afterComparison), digestExport(beforeComparison));
    assert(requests.every(request => !request.authorizationPresent));
    assert(requests.every(request => request.sameOrigin));
    assert(requests.filter(request => request.method === 'POST').every(request => request.path === '/api/v1/analysis/reports' && request.analysisIntent));
    assert.equal(postCount(), expectedPosts);
    assert.deepEqual(pageErrors, []);
    return { beforeEventSequence: beforeSnapshot.lastEventSequence, afterEventSequence: afterSnapshot.lastEventSequence,
      recoveryExportSha256: digestExport(afterRecovery), comparisonExportSha256: digestExport(afterComparison), postCount: postCount() };
  });
  result.status = checks.every(item => item.status === 'passed') ? 'passed' : 'failed';
} catch (error) {
  result.status = 'failed';
  result.error = String(error);
  await screenshot('browser-failure').catch(() => {});
} finally {
  Object.assign(result, { finishedAt: new Date().toISOString(), browserVersion: browser.version(), pageErrors, requestCount: requests.length });
  await fs.writeFile(path.join(output, 'browser-results.json'), JSON.stringify(result, null, 2) + '\n');
  await fs.writeFile(path.join(output, 'browser-requests.json'), JSON.stringify(requests, null, 2) + '\n');
  console.log(JSON.stringify({ status: result.status, checks: checks.map(item => ({ name: item.name, status: item.status })), hostedStatus: result.hostedResponse?.status ?? null, output }, null, 2));
  await browser.close();
  if (result.status !== 'passed') process.exitCode = 1;
}
