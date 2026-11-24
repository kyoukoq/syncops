import { useState } from 'react';
import type { FormEvent } from 'react';
import { Activity, Database, FlaskConical, LogOut, Play, RefreshCw, Server } from 'lucide-react';
import { errorMessage, request, useResource } from './api';
import type { AppHealth, AuditEntry, Integration, Page, Scenario, Session, SyncEvent } from './api';
import { Empty, LoadState, PageTitle, Pager, PanelTitle } from './components';
import { AuditTable } from './Events';
import { eventPath, eventTypes, roleLabels, time } from './format';

const scenarios: Record<Scenario, string> = {
  success: 'Successful delivery',
  temporary_outage: 'Temporary outage',
  http_429: 'HTTP 429 · Rate limited',
  http_422: 'HTTP 422 · Validation error',
  http_503: 'HTTP 503 · Service unavailable',
  http_500: 'HTTP 500 · Server error',
  http_502: 'HTTP 502 · Bad gateway',
  http_504: 'HTTP 504 · Gateway timeout',
  http_400: 'HTTP 400 · Bad request',
  http_401: 'HTTP 401 · Authentication error',
  http_403: 'HTTP 403 · Forbidden',
  http_404: 'HTTP 404 · Resource missing',
  http_409: 'HTTP 409 · Conflict',
  timeout: 'Request timeout',
  invalid_response: 'Invalid service response',
};

const retryScenarios: Scenario[] = ['http_429', 'http_500', 'http_502', 'http_503', 'http_504', 'temporary_outage', 'timeout'];

export function Simulation({ session, notify }: { session: Session; notify: (message: string) => void }) {
  const integrationResult = useResource<Integration[]>('/integrations', session.token);
  const [scenario, setScenario] = useState<Scenario>('success');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const enabled = integrationResult.data?.filter((integration) => integration.enabled) ?? [];
  const hasFaultCount = retryScenarios.includes(scenario);

  async function simulate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    let payload: unknown;
    setError('');
    try {
      payload = JSON.parse(String(fields.get('payload')));
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error();
    } catch {
      setError('Enter a valid JSON object as the event payload.');
      return;
    }

    const key = String(fields.get('idempotency_key')).trim();
    const failures = fields.get('failure_count');
    setBusy(true);
    try {
      const result = await request<SyncEvent>('/events', session.token, {
        method: 'POST',
        headers: key ? { 'Idempotency-Key': key } : undefined,
        body: JSON.stringify({
          integration_id: fields.get('integration_id'),
          event_type: fields.get('event_type'),
          payload,
          scenario,
          latency_ms: Number(fields.get('latency_ms')),
          failure_count: failures ? Number(failures) : undefined,
        }),
      });
      notify('Event accepted. Delivery history is live.');
      window.location.hash = eventPath(result.id);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageTitle title="Failure simulation" description="Send synthetic events through the same durable delivery queue." />
      <LoadState loading={integrationResult.loading} error={integrationResult.error} retry={integrationResult.refresh} />
      {integrationResult.data && (!enabled.length ? <section className="panel"><Empty title="No enabled integrations"><a className="text-link" href="#/integrations">Open integrations</a></Empty></section> : (
        <div className="operation-grid">
          <section className="panel padded-panel">
            <PanelTitle title="Create a test event" />
            <form className="form-stack" onSubmit={simulate}>
              <div className="form-grid">
                <label className="field">Integration<select name="integration_id" required>{enabled.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}</select></label>
                <label className="field">Event type<select name="event_type">{eventTypes.map((type) => <option key={type}>{type}</option>)}</select></label>
              </div>
              <label className="field">Delivery scenario<select value={scenario} onChange={(event) => setScenario(event.target.value as Scenario)}>{Object.entries(scenarios).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
              <div className="form-grid">
                <label className="field">Response latency (ms)<input type="number" min="0" max="10000" defaultValue="0" name="latency_ms" required /></label>
                {hasFaultCount && <label className="field">Failures before success<input type="number" min="0" max="50" defaultValue="1" name="failure_count" required /><small>Enter 0 to keep the failure active.</small></label>}
              </div>
              <label className="field">Synthetic payload<textarea className="mono" name="payload" rows={5} required defaultValue={'{\n  "record_id": "syncops-demo-001",\n  "name": "Aster Ridge Logistics"\n}'} /></label>
              <div className="field"><label htmlFor="simulation-key">Idempotency key <span className="field-optional">Optional</span></label><input id="simulation-key" name="idempotency_key" maxLength={128} pattern="[!-~]+" placeholder="Example: company-sync-demo" aria-describedby="simulation-key-help" /><small id="simulation-key-help">Reuse a key with the same request to inspect duplicate prevention.</small></div>
              {error && <p className="notice error" role="alert">{error}</p>}
              <div className="form-actions"><button className="button primary" disabled={busy}><Play size={17} aria-hidden="true" />{busy ? 'Submitting…' : 'Run simulation'}</button></div>
            </form>
          </section>
          <aside className="panel scenario-note">
            <FlaskConical size={25} className="accent" aria-hidden="true" />
            <h2>Simulated destinations</h2>
            <p>The selected destination applies the scenario to an actual mock HTTP response. Follow the event to see delivery attempts, retry timing, and recovery.</p>
            <a href="#/dead-letter" className="text-link">Open Dead Letter Queue</a>
          </aside>
        </div>
      ))}
    </>
  );
}

export function Audit({ token }: { token: string }) {
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const result = useResource<Page<AuditEntry>>(`/audit?limit=${limit}&offset=${offset}`, token, 5000);
  return <>
    <PageTitle title="Audit logs" description="Review recorded operator and administrator actions." actions={<button className="button" onClick={result.refresh}><RefreshCw size={18} aria-hidden="true" />Refresh</button>} />
    <LoadState loading={result.loading} error={result.error} retry={result.refresh} />
    {result.data && <section className="panel"><AuditTable entries={result.data.items} /><Pager limit={limit} offset={offset} total={result.data.total} onPage={setOffset} /></section>}
  </>;
}

export function SystemHealth({ token }: { token: string }) {
  const result = useResource<AppHealth>('/health', token, 5000);
  const checks = result.data ? [
    { label: 'Application', value: result.data.status, icon: Activity },
    { label: 'Database', value: result.data.database, icon: Database },
    { label: 'Queue worker', value: result.data.worker, icon: Server },
  ] : [];
  return <>
    <PageTitle title="System health" description="Inspect current application, database, and queue worker checks." actions={<button className="button" onClick={result.refresh}><RefreshCw size={18} aria-hidden="true" />Refresh</button>} />
    <LoadState loading={result.loading} error={result.error} retry={result.refresh} />
    {result.data && <>
      <div className="integration-grid">{checks.map(({ label, value, icon: Icon }) => <section className="panel health-check" key={label}><Icon size={23} className="accent" aria-hidden="true" /><h2>{label}</h2><p>{value.replaceAll('_', ' ')}</p></section>)}</div>
      <p className="subnote">Last checked {time(result.updatedAt)}</p>
    </>}
  </>;
}

export type Theme = 'dark' | 'light';

export function Settings({ session, theme, onTheme, signOut }: { session: Session; theme: Theme; onTheme: (theme: Theme) => void; signOut: () => void }) {
  return <>
    <PageTitle title="Settings" description="Manage your session and appearance preferences." />
    <div className="settings-grid">
      <section className="panel padded-panel"><PanelTitle title="Appearance" /><label className="field">Color theme<select value={theme} onChange={(event) => onTheme(event.target.value as Theme)}><option value="dark">Dark</option><option value="light">Light</option></select></label></section>
      <section className="panel padded-panel"><PanelTitle title="Account" /><dl className="detail-grid compact"><div><dt>Username</dt><dd>{session.user.username}</dd></div><div><dt>Role</dt><dd>{roleLabels[session.user.role]}</dd></div></dl><button className="button" onClick={signOut}><LogOut size={17} aria-hidden="true" />Sign out</button></section>
    </div>
  </>;
}
