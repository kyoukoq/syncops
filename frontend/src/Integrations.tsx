import { useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowLeft, ArrowUpRight, Layers3, Pencil, Plus } from 'lucide-react';
import { errorMessage, request, useResource } from './api';
import type { Integration, IntegrationConfig, Page, Session, SyncEvent, System } from './api';
import { Dialog, Empty, EventsTable, HealthChip, LoadState, PageTitle, PanelTitle, Systems } from './components';
import { number, systems } from './format';

function IntegrationEditor({ integration, session, onClose, onSaved }: { integration?: Integration; session: Session; onClose: () => void; onSaved: (integration: Integration) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const config: IntegrationConfig = {
      name: String(values.get('name')).trim(),
      description: String(values.get('description')).trim(),
      source: values.get('source') as System,
      destination: values.get('destination') as System,
      enabled: values.has('enabled'),
      timeout_seconds: Number(values.get('timeout_seconds')),
      max_attempts: Number(values.get('max_attempts')),
      retry_base_seconds: Number(values.get('retry_base_seconds')),
    };
    const path = integration ? `/integrations/${encodeURIComponent(integration.id)}` : '/integrations';
    setBusy(true);
    setError('');
    try {
      onSaved(await request<Integration>(path, session.token, { method: integration ? 'PATCH' : 'POST', body: JSON.stringify(config) }));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title={integration ? 'Configure integration' : 'Create integration'} close={onClose}>
      <form className="form-stack" onSubmit={save}>
        <label className="field">Name<input name="name" defaultValue={integration?.name} required maxLength={100} /></label>
        <label className="field">Description<textarea name="description" defaultValue={integration?.description} maxLength={600} rows={2} /></label>
        <div className="form-grid">
          <label className="field">Source<select name="source" defaultValue={integration?.source ?? 'crm'}>{Object.entries(systems).map(([system, label]) => <option value={system} key={system}>{label}</option>)}</select></label>
          <label className="field">Destination<select name="destination" defaultValue={integration?.destination ?? 'erp'}>{Object.entries(systems).map(([system, label]) => <option value={system} key={system}>{label}</option>)}</select></label>
        </div>
        <div className="form-grid three">
          <label className="field">Timeout (s)<input name="timeout_seconds" type="number" min="0.2" max="15" step="any" required defaultValue={integration?.timeout_seconds ?? 2} /></label>
          <label className="field">Max attempts<input name="max_attempts" type="number" min="1" max="12" step="1" required defaultValue={integration?.max_attempts ?? 4} /></label>
          <label className="field">Base retry delay (s)<input name="retry_base_seconds" type="number" min="0.2" max="60" step="any" required defaultValue={integration?.retry_base_seconds ?? 1} /></label>
        </div>
        <label className="check"><input name="enabled" type="checkbox" defaultChecked={integration?.enabled ?? true} />Enable integration</label>
        {error && <p className="notice error" role="alert">{error}</p>}
        <div className="form-actions"><button className="button" type="button" onClick={onClose}>Cancel</button><button className="button primary" disabled={busy}>{busy ? 'Saving…' : 'Save integration'}</button></div>
      </form>
    </Dialog>
  );
}

export function Integrations({ session, id, notify }: { session: Session; id?: string; notify: (message: string) => void }) {
  const result = useResource<Integration[]>('/integrations', session.token, 5000);
  const [editing, setEditing] = useState(false);
  const canEdit = session.user.role === 'admin';
  const integration = id ? result.data?.find((entry) => entry.id === id) : undefined;

  function saved(entry: Integration) {
    setEditing(false);
    result.refresh();
    notify(integration ? 'Integration configuration saved.' : 'Integration created.');
    if (!id) window.location.hash = `/integrations/${encodeURIComponent(entry.id)}`;
  }

  if (id) return <>
    <a className="back-link" href="#/integrations"><ArrowLeft size={16} aria-hidden="true" />Integrations</a>
    <PageTitle title={integration?.name ?? 'Integration details'} description={integration?.description || 'Review connector health and delivery configuration.'} actions={canEdit && integration ? <button className="button primary" onClick={() => setEditing(true)}><Pencil size={17} aria-hidden="true" />Configure</button> : undefined} />
    <LoadState loading={result.loading} error={result.error} retry={result.refresh} />
    {result.data && !integration && <div className="panel"><Empty title="Integration not found" /></div>}
    {integration && <>
      <section className="panel spaced-panel">
        <PanelTitle title="Connector configuration" actions={<HealthChip health={integration.health} />} />
        <dl className="detail-grid">
          <div><dt>Route</dt><dd><Systems source={integration.source} destination={integration.destination} /></dd></div>
          <div><dt>State</dt><dd>{integration.enabled ? 'Enabled' : 'Disabled'}</dd></div>
          <div><dt>Timeout</dt><dd>{number(integration.timeout_seconds, ' s')}</dd></div>
          <div><dt>Maximum attempts</dt><dd>{number(integration.max_attempts)}</dd></div>
          <div><dt>Base retry delay</dt><dd>{number(integration.retry_base_seconds, ' s')}</dd></div>
        </dl>
      </section>
      <IntegrationHistory id={id} token={session.token} />
      {editing && <IntegrationEditor integration={integration} session={session} onClose={() => setEditing(false)} onSaved={saved} />}
    </>}
  </>;

  return (
    <>
      <PageTitle title="Integrations" description="Manage routes between simulated enterprise systems." actions={canEdit ? <button className="button primary" onClick={() => setEditing(true)}><Plus size={18} aria-hidden="true" />New integration</button> : undefined} />
      <LoadState loading={result.loading} error={result.error} retry={result.refresh} />
      {result.data && (result.data.length ? <div className="integration-grid">
        {result.data.map((entry) => (
          <a className="panel integration-card" key={entry.id} href={`#/integrations/${encodeURIComponent(entry.id)}`}>
            <div className="integration-card-top"><Layers3 className="accent" size={25} aria-hidden="true" /><HealthChip health={entry.health} /></div>
            <h2>{entry.name}<ArrowUpRight size={17} aria-hidden="true" /></h2>
            <Systems source={entry.source} destination={entry.destination} />
            {entry.description && <p>{entry.description}</p>}
          </a>
        ))}
      </div> : <section className="panel"><Empty title="No integrations configured" /></section>)}
      {editing && <IntegrationEditor session={session} onClose={() => setEditing(false)} onSaved={saved} />}
    </>
  );
}

function IntegrationHistory({ id, token }: { id: string; token: string }) {
  const query = new URLSearchParams({ integration_id: id, limit: '8' });
  const result = useResource<Page<SyncEvent>>(`/events?${query}`, token, 5000);
  return (
    <section className="panel">
      <PanelTitle title="Recent delivery history" actions={<a className="text-link" href={`#/events?integration_id=${encodeURIComponent(id)}`}>View all</a>} />
      <LoadState loading={result.loading} error={result.error} retry={result.refresh} />
      {result.data && (result.data.items.length ? <EventsTable events={result.data.items} detailed /> : <Empty title="No events for this integration" />)}
    </section>
  );
}
