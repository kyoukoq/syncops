import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { AlertCircle, ArrowRight, Check, Clock3, Inbox, LoaderCircle, Minus, RefreshCw, X } from 'lucide-react';
import type { Health, Status, SyncEvent, System } from './api';
import { eventPath, healthLabels, number, statusLabels, systems, time } from './format';

const statusVisual = {
  queued: { icon: Clock3, tone: 'muted' },
  processing: { icon: LoaderCircle, tone: 'accent' },
  retry_scheduled: { icon: RefreshCw, tone: 'warning' },
  succeeded: { icon: Check, tone: 'success' },
  dead_letter: { icon: Inbox, tone: 'failure' },
};

const healthVisual = {
  healthy: { icon: Check, tone: 'success' },
  degraded: { icon: AlertCircle, tone: 'warning' },
  idle: { icon: Clock3, tone: 'muted' },
  disabled: { icon: Minus, tone: 'muted' },
};

export function StatusChip({ status }: { status: Status }) {
  const { icon: Icon, tone } = statusVisual[status];
  return <span className={`chip ${tone}`}><Icon size={14} aria-hidden="true" />{statusLabels[status]}</span>;
}

export function HealthChip({ health }: { health: Health }) {
  const { icon: Icon, tone } = healthVisual[health];
  return <span className={`chip ${tone}`}><Icon size={14} aria-hidden="true" />{healthLabels[health]}</span>;
}

export function Systems({ source, destination }: { source: System; destination: System }) {
  return <span className="systems">{systems[source]} <ArrowRight size={15} aria-label="to" /> {systems[destination]}</span>;
}

export function PageTitle({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) {
  return (
    <header className="page-title">
      <div><h1>{title}</h1><p>{description}</p></div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function PanelTitle({ title, actions }: { title: string; actions?: ReactNode }) {
  return <div className="panel-title"><h2>{title}</h2>{actions}</div>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty"><Inbox size={26} aria-hidden="true" /><h3>{title}</h3>{children}</div>;
}

export function LoadState({ loading, error, retry }: { loading: boolean; error?: string; retry: () => void }) {
  if (loading) return <div className="load-state" role="status"><LoaderCircle className="spin" size={18} aria-hidden="true" /> Loading…</div>;
  if (!error) return null;
  return (
    <div className="notice error" role="alert">
      <AlertCircle size={18} aria-hidden="true" /> <span>{error}</span>
      <button className="button small" type="button" onClick={retry}>Try again</button>
    </div>
  );
}

export function EventsTable({ events, detailed = false }: { events: SyncEvent[]; detailed?: boolean }) {
  return (
    <div className="table-scroll">
      <table aria-label="Integration events">
        <thead><tr><th scope="col">Event</th><th scope="col">Integration</th><th scope="col">Status</th><th scope="col">Attempts</th>{detailed && <th scope="col">Response</th>}<th scope="col">Received</th></tr></thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id}>
              <td>
                <a className="table-link mono" title={event.id} href={eventPath(event.id)} aria-label={`Inspect ${event.event_type} ${event.id}`}>{event.id.slice(0, 13)}</a>
                {detailed && <small>{event.event_type}</small>}
              </td>
              <td>{detailed ? <><strong>{event.integration_name}</strong><small><Systems source={event.source} destination={event.destination} /></small></> : <Systems source={event.source} destination={event.destination} />}</td>
              <td><StatusChip status={event.status} /></td>
              <td className="metric">{event.attempt_count}</td>
              {detailed && <td><span className="mono">{event.http_status ?? '—'}</span><small>{number(event.duration_ms, ' ms')}</small></td>}
              <td className="date" title={event.created_at}>{time(event.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Dialog({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);

  return (
    <dialog ref={ref} aria-labelledby="dialog-title" onCancel={(event) => { event.preventDefault(); close(); }}>
      <div className="dialog-title">
        <h2 id="dialog-title">{title}</h2>
        <button className="icon-button" type="button" onClick={close} aria-label="Close dialog"><X size={20} /></button>
      </div>
      {children}
    </dialog>
  );
}

export function Pager({ offset, limit, total, onPage }: { offset: number; limit: number; total: number; onPage: (offset: number) => void }) {
  if (total === 0) return null;
  return (
    <div className="pager">
      <span>{number(offset + 1)}–{number(Math.min(offset + limit, total))} of {number(total)}</span>
      <div>
        <button className="button small" onClick={() => onPage(Math.max(0, offset - limit))} disabled={offset === 0}>Previous</button>
        <button className="button small" onClick={() => onPage(offset + limit)} disabled={offset + limit >= total}>Next</button>
      </div>
    </div>
  );
}
