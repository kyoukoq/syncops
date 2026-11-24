import { useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowLeft, Copy, RefreshCw, Search } from 'lucide-react';
import { errorMessage, request, useResource } from './api';
import type { AuditEntry, EventDetail, Integration, Page, Session, Status, SyncEvent } from './api';
import { Dialog, Empty, EventsTable, LoadState, PageTitle, Pager, PanelTitle, StatusChip, Systems } from './components';
import { number, statusLabels, time } from './format';

const pageSize = 20;

export function AuditTable({ entries }: { entries: AuditEntry[] }) {
  if (!entries.length) return <Empty title="No audit entries" />;
  return (
    <div className="table-scroll">
      <table aria-label="Audit history">
        <thead><tr><th scope="col">Action</th><th scope="col">Actor</th><th scope="col">Details</th><th scope="col">Time</th></tr></thead>
        <tbody>{entries.map((entry) => <tr key={entry.id}>
          <td><strong>{entry.action.replaceAll('_', ' ')}</strong><small className="mono" title={entry.target_id}>{entry.target_id.slice(0, 13)}</small></td>
          <td>{entry.actor}</td><td className="detail-cell">{entry.detail}</td><td className="date">{time(entry.created_at)}</td>
        </tr>)}</tbody>
      </table>
    </div>
  );
}

export function Events({ session, mode, filters }: { session: Session; mode: 'events' | 'dead-letter' | 'incidents'; filters: URLSearchParams }) {
  const [searchText, setSearchText] = useState('');
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState(filters.get('status') ?? '');
  const [integration, setIntegration] = useState(filters.get('integration_id') ?? '');
  const [sort, setSort] = useState('newest');
  const [offset, setOffset] = useState(0);
  const integrations = useResource<Integration[]>('/integrations', session.token);
  const query = new URLSearchParams({ limit: String(pageSize), offset: String(offset), sort });
  if (mode !== 'events') query.set('status', 'dead_letter');
  else if (status) query.set('status', status);
  if (search) query.set('search', search);
  if (integration) query.set('integration_id', integration);
  const result = useResource<Page<SyncEvent>>(`/events?${query}`, session.token, 5000);

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    setSearch(searchText.trim());
    setOffset(0);
  }

  const modeLabels = {
    events: { title: 'Events', description: 'Search synchronization events and inspect their delivery history.' },
    'dead-letter': { title: 'Dead Letter Queue', description: 'Review terminal delivery failures and replay events after the cause is resolved.' },
    incidents: { title: 'Incidents', description: 'Investigate unresolved delivery failures. Open an event to see attempts and correlation details.' },
  };

  return (
    <>
      <PageTitle {...modeLabels[mode]} actions={<button className="button" onClick={result.refresh}><RefreshCw size={18} aria-hidden="true" />Refresh</button>} />
      <div className="filters" aria-label="Event filters">
        <form className="search" onSubmit={submitSearch}>
          <label className="search-field"><Search size={17} aria-hidden="true" />
            <input type="search" aria-label="Search events" placeholder="Search events…" value={searchText} maxLength={100} onChange={(event) => setSearchText(event.target.value)} />
          </label>
          <button className="button" type="submit">Search</button>
        </form>
        {mode === 'events' && <select aria-label="Event status" value={status} onChange={(event) => { setStatus(event.target.value); setOffset(0); }}>
          <option value="">All statuses</option>
          {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>}
        <select aria-label="Integration" value={integration} onChange={(event) => { setIntegration(event.target.value); setOffset(0); }}>
          <option value="">All integrations</option>
          {integrations.data?.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
        </select>
        <select aria-label="Sort events" value={sort} onChange={(event) => { setSort(event.target.value); setOffset(0); }}>
          <option value="newest">Newest first</option><option value="oldest">Oldest first</option>
        </select>
      </div>
      <LoadState loading={result.loading} error={result.error} retry={result.refresh} />
      {result.data && <section className="panel">
        {!result.data.items.length ? <Empty title={offset ? 'This page is empty' : 'No matching events'}>
          {!!offset && <button className="button small" onClick={() => setOffset(0)}>Return to first page</button>}
        </Empty> : <>
          <EventsTable events={result.data.items} detailed />
          <Pager offset={offset} limit={pageSize} total={result.data.total} onPage={setOffset} />
        </>}
      </section>}
    </>
  );
}

function RetryDialog({ event, session, onClose, onSaved }: { event: EventDetail; session: Session; onClose: () => void; onSaved: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function retry(submission: FormEvent<HTMLFormElement>) {
    submission.preventDefault();
    const values = new FormData(submission.currentTarget);
    setBusy(true);
    setError('');
    try {
      await request<SyncEvent>(`/events/${encodeURIComponent(event.id)}/retry`, session.token, {
        method: 'POST',
        body: JSON.stringify({ reason: String(values.get('reason')).trim(), clear_simulation: values.has('clear_simulation') }),
      });
      onSaved();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog title="Replay dead-letter event" close={onClose}>
      <form className="form-stack" onSubmit={retry}>
        <p className="muted-text">Replay keeps the same event ID and previous attempt history. Enter the reason for recovery.</p>
        <label className="field">Recovery reason<textarea name="reason" required maxLength={300} rows={3} /></label>
        <label className="check"><input type="checkbox" name="clear_simulation" defaultChecked />Clear the simulated failure</label>
        {error && <p className="notice error" role="alert">{error}</p>}
        <div className="form-actions"><button className="button" type="button" onClick={onClose}>Cancel</button><button className="button primary" disabled={busy}>{busy ? 'Replaying…' : 'Confirm replay'}</button></div>
      </form>
    </Dialog>
  );
}

export function EventDetails({ session, id, notify }: { session: Session; id: string; notify: (message: string) => void }) {
  const result = useResource<EventDetail>(`/events/${encodeURIComponent(id)}`, session.token, 2500);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [copyError, setCopyError] = useState('');
  const event = result.data;
  const canReplay = session.user.role !== 'viewer' && event?.status === 'dead_letter';

  async function copyCorrelation(value: string) {
    setCopyError('');
    try {
      await navigator.clipboard.writeText(value);
      notify('Correlation ID copied.');
    } catch {
      setCopyError('Clipboard access is unavailable. You can select the correlation ID to copy it.');
    }
  }

  return (
    <>
      <a className="back-link" href="#/events"><ArrowLeft size={16} aria-hidden="true" />Events</a>
      <PageTitle title={event?.event_type ?? 'Event details'} description={event?.integration_name ?? 'Inspect a synchronization event.'} actions={canReplay ?
        <button className="button primary" onClick={() => setDialogOpen(true)}><RefreshCw size={17} aria-hidden="true" />Replay event</button> : undefined} />
      <LoadState loading={result.loading} error={result.error} retry={result.refresh} />
      {event && <>
        <section className="panel spaced-panel">
          <PanelTitle title="Delivery details" actions={<StatusChip status={event.status} />} />
          <dl className="detail-grid">
            <div><dt>Event ID</dt><dd className="mono">{event.id}</dd></div>
            <div><dt>Correlation ID</dt><dd className="copy-value"><span className="mono">{event.correlation_id}</span><button type="button" className="icon-button" aria-label="Copy correlation ID" onClick={() => void copyCorrelation(event.correlation_id)}><Copy size={15} /></button></dd></div>
            <div><dt>Route</dt><dd><Systems source={event.source} destination={event.destination} /></dd></div>
            <div><dt>Received</dt><dd>{time(event.created_at)}</dd></div>
            <div><dt>Last change</dt><dd>{time(event.updated_at)}</dd></div>
            <div><dt>Next retry</dt><dd>{time(event.next_retry_at)}</dd></div>
          </dl>
          {copyError && <p className="notice error" role="alert">{copyError}</p>}
          {event.error && <p className="notice error"><strong>Latest error</strong> {event.error}</p>}
        </section>
        <section className="panel spaced-panel">
          <PanelTitle title="Processing attempts" />
          {!event.attempts.length ? <Empty title="No attempts yet" /> : <div className="table-scroll"><table aria-label="Processing attempts">
            <thead><tr><th scope="col">Attempt</th><th scope="col">Outcome</th><th scope="col">HTTP</th><th scope="col">Duration</th><th scope="col">Started</th><th scope="col">Finished</th></tr></thead>
            <tbody>{event.attempts.map((attempt) => <tr key={attempt.number}>
              <td className="mono">{attempt.number}</td>
              <td className="detail-cell"><strong>{attempt.status in statusLabels ? statusLabels[attempt.status as Status] : attempt.status.replaceAll('_', ' ')}</strong>{attempt.error && <small>{attempt.error}</small>}</td>
              <td>{attempt.http_status ?? '—'}</td><td>{number(attempt.duration_ms, ' ms')}</td><td className="date">{time(attempt.started_at)}</td><td className="date">{time(attempt.finished_at)}</td>
            </tr>)}</tbody>
          </table></div>}
        </section>
        <section className="panel"><PanelTitle title="Audit history" /><AuditTable entries={event.audit} /></section>
        {dialogOpen && <RetryDialog event={event} session={session} onClose={() => setDialogOpen(false)} onSaved={() => {
          setDialogOpen(false);
          result.refresh();
          notify('Replay queued with the same event ID.');
        }} />}
      </>}
    </>
  );
}
