import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdir, readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require(process.env.SYNCOPS_PLAYWRIGHT_MODULE || 'playwright');
const base = new URL(process.env.SYNCOPS_E2E_URL || 'http://127.0.0.1:5173/');
assert(base.protocol === 'http:' && ['127.0.0.1', 'localhost'].includes(base.hostname),
  'Browser acceptance requires an isolated loopback lab');
const credentialsPath = process.env.SYNCOPS_E2E_CREDENTIALS
  || new URL('../.syncops/credentials.json', import.meta.url);
const password = process.env.SYNCOPS_E2E_ADMIN_PASSWORD
  || JSON.parse(await readFile(credentialsPath, 'utf8')).admin;
assert(typeof password === 'string' && password.length > 0, 'A local admin credential is required');
const screenshots = process.env.SYNCOPS_E2E_SCREENSHOTS;
if (screenshots) await mkdir(screenshots, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.SYNCOPS_CHROMIUM_PATH || undefined });
const browserErrors = [];

async function screenshot(page, filename) {
  if (screenshots) await page.screenshot({ path: join(screenshots, filename), animations: 'disabled' });
}

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1024 } });
  page.on('pageerror', error => browserErrors.push(error.message));
  page.on('console', message => {
    if (message.type() === 'error' || message.type() === 'warning') browserErrors.push(message.text());
  });
  page.on('response', response => {
    if (response.url().startsWith(base.origin + '/api/') && response.status() >= 500) {
      browserErrors.push(`HTTP ${response.status()} on ${new URL(response.url()).pathname}`);
    }
  });

  await page.goto(base.href);
  assert.match(await page.title(), /^SyncOps/);
  await page.getByRole('heading', { name: 'Sign in to SyncOps' }).waitFor();
  await page.getByLabel('Username').fill('admin');
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('heading', { name: 'Integration overview' }).waitFor();
  await page.getByRole('heading', { name: 'Recent events' }).waitFor();

  await page.getByRole('link', { name: 'Failure Simulation', exact: true }).click();
  await page.getByLabel('Delivery scenario').selectOption('http_422');
  await page.getByLabel('Idempotency key').fill(`browser-${randomUUID()}`);
  await page.getByRole('button', { name: 'Run simulation', exact: true }).click();
  await page.waitForURL('**/#/events/*');
  const eventUrl = page.url();
  const eventId = eventUrl.split('/').at(-1);
  const attempts = page.getByRole('table', { name: 'Processing attempts' });
  await attempts.getByRole('cell', { name: '422', exact: true }).waitFor();

  const workspaceNavigation = page.getByRole('navigation', { name: 'Workspace navigation' });
  await workspaceNavigation.getByRole('link', { name: 'Dead Letter Queue' }).click();
  await page.getByRole('heading', { name: 'Dead Letter Queue' }).waitFor();
  await page.getByRole('searchbox', { name: 'Search events' }).fill(eventId);
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await page.getByRole('link', { name: `Inspect company.created ${eventId}` }).click();
  assert.equal(page.url(), eventUrl);
  await page.getByRole('button', { name: 'Replay event', exact: true }).click();
  await page.getByRole('dialog', { name: 'Replay dead-letter event' }).waitFor();
  await page.getByLabel('Recovery reason').fill('Browser acceptance: simulated validation problem resolved');
  await page.getByRole('button', { name: 'Confirm replay' }).click();
  await attempts.getByRole('cell', { name: '200', exact: true }).waitFor({ timeout: 15_000 });
  await attempts.getByRole('cell', { name: '422', exact: true }).waitFor();
  await page.getByRole('cell', { name: 'Browser acceptance: simulated validation problem resolved' }).waitFor();
  assert.equal(page.url(), eventUrl);
  await screenshot(page, 'event-recovery.png');

  await workspaceNavigation.getByRole('link', { name: 'Overview', exact: true }).click();
  await page.getByRole('table', { name: 'Integration events' }).waitFor();
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await page.getByRole('table', { name: 'Integration events' }).waitFor();
  await screenshot(page, 'integration-overview.png');
  const themeSwitch = page.getByRole('switch', { name: 'Dark theme' });
  assert.equal(await themeSwitch.getAttribute('aria-checked'), 'true');
  await themeSwitch.click();
  assert.equal(await themeSwitch.getAttribute('aria-checked'), 'false');
  await themeSwitch.click();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('heading', { name: 'Integration overview' }).waitFor();
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    'Mobile viewport must not have page-wide horizontal overflow');
  await screenshot(page, 'integration-overview-mobile.png');
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await workspaceNavigation.getByRole('link', { name: 'Settings', exact: true }).click();
  await page.getByRole('heading', { name: 'Settings' }).waitFor();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await page.getByRole('heading', { name: 'Sign in to SyncOps' }).waitFor();

  assert.deepEqual(browserErrors, [], 'Browser console or API errors');
  console.log('Browser acceptance passed: sign-in, 422, DLQ search, replay with preserved history, audit, theme, mobile navigation and sign-out.');
} finally {
  await browser.close();
}
