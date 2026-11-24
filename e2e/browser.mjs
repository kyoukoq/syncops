import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { appendFile, mkdir, readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require(process.env.SYNCOPS_PLAYWRIGHT_MODULE || 'playwright');
const base = new URL(process.env.SYNCOPS_E2E_URL || 'http://127.0.0.1:5173/');
assert(base.protocol === 'http:' && ['127.0.0.1', 'localhost'].includes(base.hostname)
  && !base.username && !base.password, 'Browser acceptance requires an isolated loopback fixture');

const roles = ['admin', 'operator', 'viewer'];
const credentials = Object.fromEntries(roles.map(role => [role, process.env['SYNCOPS_E2E_' + role.toUpperCase() + '_PASSWORD']]));
if (roles.some(role => !credentials[role])) {
  const credentialsPath = process.env.SYNCOPS_E2E_CREDENTIALS
    || new URL('../.syncops/credentials.json', import.meta.url);
  const localCredentials = JSON.parse(await readFile(credentialsPath, 'utf8'));
  for (const role of roles) credentials[role] ||= localCredentials[role];
}
assert(roles.every(role => typeof credentials[role] === 'string' && credentials[role].length),
  'The browser fixture requires generated admin, operator and viewer credentials');

const screenshots = process.env.SYNCOPS_E2E_SCREENSHOTS;
if (screenshots) await mkdir(screenshots, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.SYNCOPS_CHROMIUM_PATH || undefined });
const browserErrors = [];
const captures = [];
const fixture = randomUUID().slice(0, 8);
const integrationName = 'Warehouse dispatch ' + fixture;
const replayReason = 'Synthetic validation issue resolved in the warehouse adapter';
const operatorReason = 'Operator cleared the simulated shipment failure';

function heading(page, name) {
  return page.getByRole('heading', { name, exact: true });
}

function navigation(page) {
  return page.getByRole('navigation', { name: 'Workspace navigation' });
}

async function openPage(page, label, title = label) {
  await navigation(page).getByRole('link', { name: label, exact: true }).click();
  await heading(page, title).waitFor();
}

function apiResponse(page, method, path) {
  return page.waitForResponse(response => {
    const url = new URL(response.url());
    return url.origin === base.origin && url.pathname === '/api/v1' + path
      && response.request().method() === method;
  });
}

async function api(page, token, method, path, options = {}) {
  return page.request.fetch(new URL('/api/v1' + path, base).href, {
    ...options, method, maxRedirects: 0,
    headers: { ...options.headers, Authorization: 'Bearer ' + token },
  });
}

async function screenshot(page, filename) {
  if (!screenshots) return;
  await page.evaluate(() => document.fonts.ready);
  const path = join(screenshots, filename);
  await page.screenshot({ path, animations: 'disabled', fullPage: true });
  const image = await readFile(path);
  assert(image.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])),
    'Chromium screenshot is a PNG');
  const width = image.readUInt32BE(16);
  const height = image.readUInt32BE(20);
  assert.equal(width, page.viewportSize().width, filename + ' is the expected viewport width');
  assert(height >= page.viewportSize().height, filename + ' spans the viewport');
  const digest = createHash('sha256').update(image).digest('hex');
  captures.push([filename, width + ' × ' + height, image.length, digest]);
}

async function newPage() {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1024 }, locale: 'en-US', timezoneId: 'UTC',
  });
  page.on('pageerror', error => browserErrors.push(error.message));
  page.on('console', message => {
    if (message.type() === 'warning' || message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('response', response => {
    const url = new URL(response.url());
    if (url.origin === base.origin && url.pathname.startsWith('/api/') && !response.ok()) {
      browserErrors.push('HTTP ' + response.status() + ' on ' + url.pathname);
    }
  });
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin: base.origin });
  await page.goto(base.href);
  assert.equal(new URL(page.url()).origin, base.origin, 'The sign-in page stayed in the isolated fixture');
  assert.match(await page.title(), /^SyncOps/);
  await heading(page, 'Sign in to SyncOps').waitFor();
  return page;
}

async function signIn(page, role) {
  await page.getByLabel('Username').fill(role);
  await page.getByLabel('Password').fill(credentials[role]);
  const [response] = await Promise.all([
    apiResponse(page, 'POST', '/auth/login'),
    page.getByRole('button', { name: 'Sign in', exact: true }).click(),
  ]);
  assert.equal(response.status(), 200, role + ' signed in');
  const { token, user } = await response.json();
  assert.equal(user.role, role);
  assert(typeof token === 'string' && token.length, role + ' received a session');
  await heading(page, 'Integration overview').waitFor();
  return token;
}

async function signOut(page, token) {
  await heading(page, 'Settings').waitFor();
  const [response] = await Promise.all([
    apiResponse(page, 'POST', '/auth/logout'),
    page.getByRole('button', { name: 'Sign out', exact: true }).click(),
  ]);
  assert.equal(response.status(), 204);
  await heading(page, 'Sign in to SyncOps').waitFor();
  assert.equal((await api(page, token, 'GET', '/auth/me')).status(), 401, 'Sign-out revoked the token');
}

async function createIntegration(page) {
  await openPage(page, 'Integrations');
  await page.getByRole('button', { name: 'New integration', exact: true }).click();
  const editor = page.getByRole('dialog', { name: 'Create integration' });
  await editor.getByLabel('Name', { exact: true }).fill(integrationName);
  await editor.getByLabel('Description').fill('Routes synthetic dispatches to the transportation adapter.');
  await editor.getByLabel('Source').selectOption('crm');
  await editor.getByLabel('Destination').selectOption('tms');
  await editor.getByLabel('Timeout (s)').fill('3');
  const [response] = await Promise.all([
    apiResponse(page, 'POST', '/integrations'),
    editor.getByRole('button', { name: 'Save integration' }).click(),
  ]);
  assert.equal(response.status(), 201);
  const integration = await response.json();
  assert.equal(integration.destination, 'tms');
  await heading(page, integrationName).waitFor();
  await page.getByText('No events for this integration', { exact: true }).waitFor();
  return integration;
}

async function configureIntegration(page, integration, enabled) {
  await page.getByRole('button', { name: 'Configure', exact: true }).click();
  const editor = page.getByRole('dialog', { name: 'Configure integration' });
  await editor.getByLabel('Max attempts').fill('5');
  await editor.getByLabel('Base retry delay (s)').fill('0.5');
  await editor.getByLabel('Enable integration').setChecked(enabled);
  const [response] = await Promise.all([
    apiResponse(page, 'PATCH', '/integrations/' + integration.id),
    editor.getByRole('button', { name: 'Save integration' }).click(),
  ]);
  assert.equal(response.status(), 200);
  const saved = await response.json();
  assert.equal(saved.enabled, enabled);
  assert.equal(saved.max_attempts, 5);
  assert.equal(saved.retry_base_seconds, 0.5);
  await editor.waitFor({ state: 'hidden' });
  await page.locator('dl').getByText(enabled ? 'Enabled' : 'Disabled', { exact: true }).waitFor();
}

async function verifyDisabledIntegration(page, token, integration) {
  await openPage(page, 'Failure Simulation', 'Failure simulation');
  const routes = page.locator('select[name="integration_id"]');
  await routes.waitFor();
  assert.equal(await routes.locator('option').filter({ hasText: integrationName }).count(), 0,
    'Disabled routes are excluded from the form');
  const disabled = eventData(integration, 'order.created', { reference: 'ORD-DISABLED', pallets: 2 });
  assert.equal((await api(page, token, 'POST', '/events', { data: disabled })).status(), 409,
    'The API rejects new events for a disabled route');
  await openPage(page, 'Integrations');
  const integrationCard = page.getByRole('link').filter({ has: heading(page, integrationName) });
  assert.equal(await integrationCard.getAttribute('href'), '#/integrations/' + integration.id);
  await integrationCard.click();
  await heading(page, integrationName).waitFor();
  await configureIntegration(page, integration, true);
}

function eventData(integration, type, record, scenario = 'success') {
  return {
    integration_id: integration.id,
    event_type: type,
    scenario,
    payload: { record_id: record.reference + '-' + fixture, ...record },
  };
}

async function simulate(page, data, key = randomUUID()) {
  await openPage(page, 'Failure Simulation', 'Failure simulation');
  await page.locator('select[name="integration_id"]').selectOption(data.integration_id);
  await page.getByLabel('Event type').selectOption(data.event_type);
  await page.getByLabel('Delivery scenario').selectOption(data.scenario);
  await page.getByLabel('Synthetic payload').fill(JSON.stringify(data.payload, null, 2));
  await page.getByLabel('Idempotency key').fill('browser-' + key);
  const [response] = await Promise.all([
    apiResponse(page, 'POST', '/events'),
    page.getByRole('button', { name: 'Run simulation', exact: true }).click(),
  ]);
  assert.equal(response.status(), 202);
  const event = await response.json();
  assert.equal(event.integration_id, data.integration_id);
  await page.waitForURL(url => url.hash === '#/events/' + event.id);
  await heading(page, data.event_type).waitFor();
  return event;
}

async function verifyAttempt(page, status) {
  await page.getByRole('table', { name: 'Processing attempts' })
    .getByRole('cell', { name: String(status), exact: true }).waitFor({ timeout: 20_000 });
}

function eventLink(page, event) {
  return page.getByRole('link', { name: 'Inspect ' + event.event_type + ' ' + event.id, exact: true });
}

async function findEvent(page, event) {
  const searchResponse = page.waitForResponse(response => {
    const url = new URL(response.url());
    return url.origin === base.origin && url.pathname === '/api/v1/events' && url.searchParams.get('search') === event.id;
  });
  await page.getByRole('searchbox', { name: 'Search events' }).fill(event.id);
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  const response = await searchResponse;
  assert.equal(response.status(), 200);
  assert.deepEqual((await response.json()).items.map(item => item.id), [event.id]);
  await eventLink(page, event).click();
  await page.waitForURL(url => url.hash === '#/events/' + event.id);
}

async function replay(page, event, reason) {
  await page.getByRole('button', { name: 'Replay event', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Replay dead-letter event' });
  await dialog.getByLabel('Recovery reason').fill(reason);
  await dialog.getByLabel('Clear the simulated failure').check();
  const [response] = await Promise.all([
    apiResponse(page, 'POST', '/events/' + event.id + '/retry'),
    dialog.getByRole('button', { name: 'Confirm replay' }).click(),
  ]);
  assert.equal(response.status(), 202);
  assert.equal((await response.json()).id, event.id);
  await verifyAttempt(page, 200);
}

async function verifyExplorer(page, token, integration) {
  // Submit additional real records through the application to cross the UI page boundary.
  const types = ['company.created', 'contact.created', 'customer.updated', 'order.created'];
  for (let offset = 0; offset < 20; offset += types.length) {
    await Promise.all(types.map(async (type, index) => {
      const sequence = String(offset + index + 1).padStart(2, '0');
      const payload = eventData(integration, type, {
        reference: 'WR-' + sequence, company: 'Westmere Supply', depot: 'North Distribution',
      });
      const response = await api(page, token, 'POST', '/events', {
        data: payload, headers: { 'Idempotency-Key': 'browser-fixture-' + fixture + '-' + sequence },
      });
      assert.equal(response.status(), 202);
    }));
  }

  await openPage(page, 'Events');
  const table = page.getByRole('table', { name: 'Integration events' });
  const links = table.getByRole('link', { name: /^Inspect / });
  async function loadPage(sort, offset, action) {
    const [response] = await Promise.all([
      page.waitForResponse(response => {
        const url = new URL(response.url());
        return url.origin === base.origin && url.pathname === '/api/v1/events'
          && url.searchParams.get('integration_id') === integration.id
          && url.searchParams.get('sort') === sort && url.searchParams.get('offset') === String(offset);
      }),
      action(),
    ]);
    assert.equal(response.status(), 200);
    const { items, total } = await response.json();
    assert(total > 20 && items.length && items.every(item => item.integration_id === integration.id),
      'The event explorer queried a populated page for the selected integration');
    const expected = '#/events/' + items[0].id;
    await page.waitForFunction(href =>
      document.querySelector('table[aria-label="Integration events"] tbody a')?.getAttribute('href') === href,
    expected);
    assert.equal(await links.count(), items.length);
    return expected;
  }

  const newest = await loadPage('newest', 0, () => page.getByLabel('Integration', { exact: true }).selectOption(integration.id));
  const oldest = await loadPage('oldest', 0, () => page.getByLabel('Sort events').selectOption('oldest'));
  assert.notEqual(newest, oldest);
  const next = await loadPage('oldest', 20, () => page.getByRole('button', { name: 'Next', exact: true }).click());
  assert.notEqual(next, oldest);
  const previous = await loadPage('oldest', 0, () => page.getByRole('button', { name: 'Previous', exact: true }).click());
  assert.equal(previous, oldest);

  await page.getByLabel('Event status').selectOption('dead_letter');
  await table.getByRole('cell', { name: 'Dead letter', exact: true }).first().waitFor();
  assert.equal(await table.getByRole('cell', { name: 'Succeeded', exact: true }).count(), 0);
  await page.getByRole('searchbox', { name: 'Search events' }).fill('does-not-match-' + fixture);
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await heading(page, 'No matching events').waitFor();
}

async function verifyDashboard(page) {
  await openPage(page, 'Overview', 'Integration overview');
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await heading(page, 'Recent events').waitFor();
  await heading(page, 'Integration health').waitFor();
  const chart = page.getByRole('img', { name: /(?:^|\s)[1-9]\d* succeeded/ });
  await chart.waitFor();
  assert(await chart.locator('.bar.chart-success').evaluateAll(bars => bars.some(bar => bar.offsetHeight > 0)),
    'Success activity has visible bar geometry');
  assert(await chart.locator('.bar.chart-failure').evaluateAll(bars => bars.some(bar => bar.offsetHeight > 0)),
    'Failure activity has visible bar geometry');
  await page.getByRole('table', { name: 'Integration events' }).waitFor();
  await screenshot(page, 'integration-overview.png');

  const theme = page.getByRole('switch', { name: 'Dark theme' });
  assert.equal(await theme.getAttribute('aria-checked'), 'true');
  const dark = await page.locator('html').evaluate(node => getComputedStyle(node).backgroundColor);
  await theme.click();
  await page.locator('html[data-theme="light"]').waitFor();
  const light = await page.locator('html').evaluate(node => getComputedStyle(node).backgroundColor);
  assert.equal(await theme.getAttribute('aria-checked'), 'false');
  assert.notEqual(light, dark);
  await screenshot(page, 'integration-overview-light.png');
  await theme.click();
  await page.locator('html[data-theme="dark"]').waitFor();

  await page.setViewportSize({ width: 390, height: 844 });
  await heading(page, 'Integration overview').waitFor();
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    'Mobile viewport has no page-wide horizontal overflow');
  await screenshot(page, 'integration-overview-mobile.png');
  const menu = page.getByRole('button', { name: 'Open navigation' });
  await menu.click();
  assert.equal(await menu.getAttribute('aria-expanded'), 'true');
  await page.keyboard.press('Escape');
  assert.equal(await menu.getAttribute('aria-expanded'), 'false');
  await menu.click();
  await openPage(page, 'Settings');
  await page.getByLabel('Color theme').selectOption('light');
  await page.locator('html[data-theme="light"]').waitFor();
}

async function adminFlow() {
  const page = await newPage();
  await screenshot(page, 'sign-in.png');
  const token = await signIn(page, 'admin');
  const integration = await createIntegration(page);
  await configureIntegration(page, integration, false);
  await verifyDisabledIntegration(page, token, integration);

  await openPage(page, 'Failure Simulation', 'Failure simulation');
  await page.getByLabel('Synthetic payload').fill('[]');
  await page.getByRole('button', { name: 'Run simulation', exact: true }).click();
  await page.getByRole('alert').getByText('Enter a valid JSON object as the event payload.').waitFor();

  const company = eventData(integration, 'company.created', { reference: 'CRM-104', name: 'Aster Ridge Logistics' });
  const accepted = await simulate(page, company, fixture + '-company');
  await verifyAttempt(page, 200);
  const duplicate = await simulate(page, company, fixture + '-company');
  assert.equal(duplicate.id, accepted.id, 'Idempotent simulation kept the published event ID');

  await simulate(page, eventData(integration, 'order.created',
    { reference: 'ORD-816', account: 'Hawthorn Foods', pallets: 9 }, 'temporary_outage'));
  await verifyAttempt(page, 503);
  await verifyAttempt(page, 200);
  await simulate(page, eventData(integration, 'customer.updated',
    { reference: 'CRM-119', name: 'Juniper Retail', payment_terms: 30 }, 'http_429'));
  await verifyAttempt(page, 429);
  await verifyAttempt(page, 200);

  const validation = await simulate(page, eventData(integration, 'order.created',
    { reference: 'ORD-819', account: 'Hawthorn Foods', pallets: 13 }, 'http_422'));
  await verifyAttempt(page, 422);
  await openPage(page, 'Dead Letter Queue');
  await findEvent(page, validation);
  await page.getByRole('button', { name: 'Copy correlation ID' }).click();
  await page.getByText('Correlation ID copied.', { exact: true }).waitFor();
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), validation.correlation_id);
  await replay(page, validation, replayReason);
  await verifyAttempt(page, 422);
  await page.getByRole('cell', { name: replayReason, exact: true }).waitFor();
  await screenshot(page, 'event-recovery.png');

  await openPage(page, 'Audit Logs', 'Audit logs');
  await page.getByRole('table', { name: 'Audit history' }).getByRole('cell', { name: replayReason, exact: true }).waitFor();
  await openPage(page, 'System Health', 'System health');
  for (const label of ['Application', 'Database', 'Queue worker']) await heading(page, label).waitFor();
  await page.getByText('healthy', { exact: true }).waitFor();
  assert.equal(await page.getByText('online', { exact: true }).count(), 2);

  const shipment = await simulate(page, eventData(integration, 'shipment.updated',
    { reference: 'SHP-320', lane: 'Cedar Point → Belford', status: 'In transit' }, 'http_400'));
  await verifyAttempt(page, 400);
  const account = await simulate(page, eventData(integration, 'account.synced',
    { reference: 'ACC-612', name: 'Westmere Supply' }, 'http_401'));
  await verifyAttempt(page, 401);

  await openPage(page, 'Incidents');
  await eventLink(page, account).waitFor();
  await eventLink(page, shipment).waitFor();
  assert.equal(await eventLink(page, validation).count(), 0, 'Recovered event cleared from incidents');
  await screenshot(page, 'incident-queue.png');

  await openPage(page, 'Integrations');
  await page.getByRole('link').filter({ has: heading(page, integrationName) }).click();
  await heading(page, 'Recent delivery history').waitFor();
  await eventLink(page, account).waitFor();
  await screenshot(page, 'integration-details.png');
  await page.getByRole('link', { name: 'View all', exact: true }).click();
  await page.waitForURL(url => url.hash.includes('integration_id=' + integration.id));
  await page.getByRole('table', { name: 'Integration events' }).waitFor();
  assert.equal(await page.getByLabel('Integration', { exact: true }).inputValue(), integration.id);

  await verifyDashboard(page);
  await signOut(page, token);
  // Return to desktop before checking persisted theme across a reload of the signed-out page.
  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.reload();
  await heading(page, 'Sign in to SyncOps').waitFor();
  await page.locator('html[data-theme="light"]').waitFor();

  await page.close();
  return { integration, shipment, account };
}

async function operatorFlow({ integration, shipment }) {
  const page = await newPage();
  const token = await signIn(page, 'operator');
  assert.equal(await navigation(page).getByRole('link', { name: 'Audit Logs' }).count(), 0);
  await openPage(page, 'Integrations');
  assert.equal(await page.getByRole('button', { name: 'New integration' }).count(), 0);
  const { name, description, source, destination } = integration;
  assert.equal((await api(page, token, 'POST', '/integrations', { data: { name, description, source, destination } })).status(), 403);
  await simulate(page, eventData(integration, 'contact.created',
    { reference: 'CRM-221', company: 'Aster Ridge Logistics', department: 'Dispatch' }));
  await verifyAttempt(page, 200);
  await openPage(page, 'Dead Letter Queue');
  await findEvent(page, shipment);
  await replay(page, shipment, operatorReason);
  await verifyAttempt(page, 400);
  await heading(page, 'No audit entries').waitFor();
  await openPage(page, 'Settings');
  await page.getByText('Operator', { exact: true }).last().waitFor();
  await signOut(page, token);
  await page.close();
}

async function viewerFlow({ integration, account }) {
  const page = await newPage();
  const token = await signIn(page, 'viewer');
  assert.equal(await navigation(page).getByRole('link', { name: 'Audit Logs' }).count(), 0);
  assert.equal(await navigation(page).getByRole('link', { name: 'Failure Simulation' }).count(), 0);
  for (const [route, title] of [['audit', 'Audit Logs'], ['simulation', 'Failure Simulation']]) {
    await page.evaluate(target => { window.location.hash = '#/' + target; }, route);
    await heading(page, title).waitFor();
    await heading(page, 'Access restricted').waitFor();
  }
  assert.equal((await api(page, token, 'GET', '/audit')).status(), 403);
  const denied = eventData(integration, 'company.created', { reference: 'VIEW-77', name: 'Synthetic fixture' });
  assert.equal((await api(page, token, 'POST', '/events', { data: denied })).status(), 403);
  await openPage(page, 'Incidents');
  await findEvent(page, account);
  await verifyAttempt(page, 401);
  assert.equal(await page.getByRole('button', { name: 'Replay event', exact: true }).count(), 0);
  assert.equal((await api(page, token, 'POST', '/events/' + account.id + '/retry', {
    data: { reason: 'Read-only authorization check', clear_simulation: true },
  })).status(), 403);
  await openPage(page, 'Settings');
  await page.getByText('Viewer', { exact: true }).last().waitFor();
  await signOut(page, token);
  await page.close();
}

try {
  const fixtures = await adminFlow();
  await operatorFlow(fixtures);
  await viewerFlow(fixtures);
  const explorer = await newPage();
  const token = await signIn(explorer, 'admin');
  await verifyExplorer(explorer, token, fixtures.integration);
  await openPage(explorer, 'Settings');
  await signOut(explorer, token);
  await explorer.close();

  assert.deepEqual(browserErrors, [], 'Unexpected browser console or API errors');
  console.log('Browser acceptance passed: all console pages, integration controls, real chart rendering, search, filters, sorting, pagination, replay, mobile navigation, theme and role boundaries.');
  if (captures.length) {
    const evidence = [
      '### Chromium screenshots',
      '',
      'Rendered in the isolated Compose fixture. Files remain in the ephemeral runner screenshot directory.',
      '',
      '| File | Pixels | Bytes | SHA-256 |',
      '| --- | --- | ---: | --- |',
      ...captures.map(capture => '| ' + capture.join(' | ') + ' |'),
    ].join('\n');
    console.log(evidence);
    if (process.env.GITHUB_STEP_SUMMARY) await appendFile(process.env.GITHUB_STEP_SUMMARY, evidence + '\n');
  }
} catch (error) {
  let message = error instanceof Error ? error.stack ?? error.message : String(error);
  for (const credential of Object.values(credentials)) message = message.replaceAll(credential, '[redacted]');
  console.error(message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
