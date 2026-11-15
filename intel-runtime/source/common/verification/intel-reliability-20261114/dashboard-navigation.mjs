import { chromium } from '../intel-dashboard-bringup/browser-tools/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const settings = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const origin = new URL(settings.uiOrigin).origin;
assert(['127.0.0.1', 'localhost'].includes(new URL(origin).hostname));
const output = path.join(directory, `dashboard-navigation-${new Date().toISOString().replace(/[:.]/g, '-')}`);
await fs.mkdir(output, { recursive: false });
const executablePath = path.join(directory, '../intel-dashboard-bringup/browser-tools/browsers/chromium_headless_shell-1255/chrome-headless-shell-linux64/chrome-headless-shell');
const browser = await chromium.launch({ headless: true, executablePath, args: ['--disable-dev-shm-usage'] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
page.setDefaultTimeout(15000);
const requests = [], errors = [], checks = [];
const result = { observedAt: new Date().toISOString(), scope: 'Read-only navigation of the rebuilt dashboard; all writes blocked in this browser context.', origin, checks };
page.on('pageerror', error => errors.push(error.message));
await context.route('**/api/**', route => {
  const request = route.request();
  requests.push({ method: request.method(), path: new URL(request.url()).pathname });
  return request.method() === 'GET' ? route.continue() : route.abort('blockedbyclient');
});
const readSnapshot = () => context.request.get(origin + '/api/v1/station/snapshot').then(response => response.json());
try {
  const before = await readSnapshot();
  await page.goto(origin);
  await page.waitForFunction(() => document.body.innerText.includes('Records API connected'));
  await page.getByRole('button', { name: 'Simulation', exact: true }).click();
  await page.getByLabel('Selected station session').selectOption('m16-recovery:session');
  const visited = [];
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    for (const view of ['Live inspection', 'Robot and system', 'Quality and history']) {
      await page.getByRole('button', { name: view, exact: true }).click();
      await page.locator('#main-content').waitFor();
      assert((await page.locator('#main-content').innerText()).length > 200);
      await page.evaluate(() => window.scrollTo(0, 0));
      const size = await page.evaluate(() => ({ width: innerWidth, documentWidth: document.documentElement.scrollWidth, skipLinkTop: document.querySelector('.skip-link').getBoundingClientRect().top }));
      assert.equal(size.documentWidth, size.width);
      assert(size.skipLinkTop < 0, 'The unfocused skip link remains outside the visible viewport.');
      await page.screenshot({ path: path.join(output, `${width}-${view.replaceAll(' ', '-')}.png`), fullPage: false });
      visited.push({ view, ...size });
    }
  }
  checks.push({ name: 'All three dashboard views render at desktop and mobile widths', status: 'passed', evidence: visited });
  await page.getByRole('button', { name: 'Replay', exact: true }).click();
  await page.getByRole('heading', { name: 'Read-only historical replay', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Next replay event', exact: true }).click();
  await page.getByRole('button', { name: 'Previous replay event', exact: true }).click();
  const analyst = page.locator('section[aria-label="Gemma evidence analyst"]');
  assert.match(await analyst.innerText(), /READ-ONLY REPLAY/);
  assert.equal(await analyst.getByRole('button', { name: 'Generate cycle explanation', exact: true }).count(), 0);
  await page.getByRole('button', { name: 'Robot and system', exact: true }).click();
  await page.getByRole('button', { name: 'Quality and history', exact: true }).click();
  assert.match(await analyst.innerText(), /READ-ONLY REPLAY/);
  await page.getByRole('button', { name: 'Simulation', exact: true }).click();
  await analyst.getByRole('button', { name: 'Generate cycle explanation', exact: true }).waitFor();
  checks.push({ name: 'Replay navigation stays read-only and normal history returns explicitly', status: 'passed' });
  await page.getByRole('button', { name: 'Live', exact: true }).click();
  await page.getByRole('button', { name: 'Live inspection', exact: true }).click();
  await page.waitForTimeout(200);
  assert.equal(await page.locator('#main-content').count(), 1);
  await page.getByRole('button', { name: 'Simulation', exact: true }).click();
  await page.getByLabel('Selected station session').selectOption('m16-recovery:session');
  await page.getByRole('button', { name: 'Quality and history', exact: true }).click();
  await analyst.getByLabel('Saved reports', { exact: true }).waitFor();
  checks.push({ name: 'Live and simulation source navigation recovers the saved analyst history', status: 'passed' });
  const after = await readSnapshot();
  assert.equal(before.lastEventSequence, after.lastEventSequence);
  assert.equal(requests.filter(item => item.method !== 'GET').length, 0);
  assert.deepEqual(errors, []);
  checks.push({ name: 'Navigation creates no requests to mutate data and no canonical events', status: 'passed', evidence: { postCount: 0, sequenceBefore: before.lastEventSequence, sequenceAfter: after.lastEventSequence, errors } });
  result.status = 'passed';
} catch (error) { result.status = 'failed'; result.error = String(error); process.exitCode = 1; await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: false }).catch(() => {}); }
finally {
  Object.assign(result, { finishedAt: new Date().toISOString(), errors });
  await fs.writeFile(path.join(output, 'browser-results.json'), JSON.stringify(result, null, 2) + '\n');
  await fs.writeFile(path.join(output, 'browser-requests.json'), JSON.stringify(requests, null, 2) + '\n');
  console.log(JSON.stringify({ output, ...result }, null, 2));
  await browser.close();
}
