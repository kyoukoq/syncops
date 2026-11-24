import { CalendarDays, CircleCheck, Layers3, Mail, Play, RefreshCw } from 'lucide-react';
import { useResource } from './api';
import type { ActivityBucket, Overview as OverviewData, Session } from './api';
import { Empty, EventsTable, HealthChip, LoadState, PageTitle, PanelTitle, Systems } from './components';
import { number, time } from './format';

function chartMax(values: ActivityBucket[]) {
  const highest = Math.max(1, ...values.flatMap(({ succeeded, failed, pending }) => [succeeded, failed, pending]));
  const order = 10 ** Math.floor(Math.log10(highest));
  return Math.max(4, Math.ceil(highest / (4 * order)) * 4 * order);
}

function ActivityChart({ values }: { values: ActivityBucket[] }) {
  const buckets = values.slice(-10);
  const scale = chartMax(buckets);
  const hasPending = buckets.some(({ pending }) => pending > 0);
  const hasActivity = buckets.some(({ succeeded, failed, pending }) => succeeded + failed + pending > 0);
  const summary = buckets.map(({ label, succeeded, failed, pending }) => `${label}: ${succeeded} succeeded, ${failed} failed, ${pending} pending`).join('; ');

  return (
    <section className="panel chart-panel" aria-label="Event activity">
      <PanelTitle title="Event activity" actions={
        <div className="legend"><span>24h · UTC</span><span><i className="chart-success" />Succeeded</span><span><i className="chart-failure" />Failed</span>{hasPending && <span><i className="chart-pending" />Pending</span>}</div>
      } />
      {!hasActivity ? <Empty title="No activity in this window"><p>Processed events will appear here.</p></Empty> : (
        <div className="chart" role="img" aria-label={summary}>
          <div className="chart-axis" aria-hidden="true">{[scale, scale * .75, scale * .5, scale * .25, 0].map((tick) => <span key={tick}>{number(tick)}</span>)}</div>
          <div className="chart-plot" aria-hidden="true">
            {buckets.map(({ label, succeeded, failed, pending }, index) => (
              <div className="chart-group" key={`${label}-${index}`} title={`${label} · ${succeeded} succeeded · ${failed} failed · ${pending} pending`}>
                <div className="bar chart-success" style={{ height: `${succeeded / scale * 100}%` }} />
                <div className="bar chart-failure" style={{ height: `${failed / scale * 100}%` }} />
                {!!pending && <div className="bar chart-pending" style={{ height: `${pending / scale * 100}%` }} />}
                <span className="chart-label">{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

export function Overview({ session }: { session: Session }) {
  const result = useResource<OverviewData>('/overview', session.token, 5000);
  const { data } = result;
  const stats = data ? [
    { icon: CalendarDays, tone: 'accent', label: 'Total events', value: number(data.total_events), path: '#/events' },
    { icon: CircleCheck, tone: 'success', label: 'Success rate', value: number(data.success_rate, '%'), path: '#/events?status=succeeded' },
    { icon: Mail, tone: 'failure', label: 'Dead letters', value: number(data.dead_letters), path: '#/dead-letter' },
    { icon: Layers3, tone: 'accent', label: 'Active integrations', value: number(data.active_integrations), path: '#/integrations' },
  ] : [];

  return (
    <>
      <PageTitle title="Integration overview" description="Monitor event delivery and recover failed synchronizations." actions={
        <>
          <button type="button" className="button" onClick={result.refresh}><RefreshCw size={18} aria-hidden="true" />Refresh</button>
          {session.user.role !== 'viewer' && <a className="button primary" href="#/simulation"><Play size={18} aria-hidden="true" />Run simulation</a>}
        </>
      } />
      <LoadState loading={result.loading} error={result.error} retry={result.refresh} />
      {data && <>
        <div className="stats">
          {stats.map(({ icon: Icon, tone, label, value, path }) => (
            <a href={path} className="stat panel" key={label}>
              <Icon className={`stat-icon ${tone}`} size={36} strokeWidth={1.8} aria-hidden="true" />
              <div><p>{label}</p><strong>{value}</strong></div>
            </a>
          ))}
        </div>
        <div className="overview-grid">
          <ActivityChart values={data.activity} />
          <section className="panel health-panel">
            <PanelTitle title="Integration health" />
            {data.integrations.length === 0 ? <Empty title="No integrations" /> : (
              <ul className="health-list">
                {data.integrations.slice(0, 4).map((integration) => (
                  <li key={integration.id}>
                    <a className="health-row" href={`#/integrations/${encodeURIComponent(integration.id)}`}>
                      <div><strong><Systems source={integration.source} destination={integration.destination} /></strong><small>{integration.name}</small></div>
                      <HealthChip health={integration.health} />
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
        <section className="panel recent-panel">
          <PanelTitle title="Recent events" actions={<a href="#/events" className="text-link">View all</a>} />
          {data.recent_events.length === 0 ? <Empty title="No events received"><p>Submit a synthetic event to see its delivery status.</p></Empty> : <EventsTable events={data.recent_events.slice(0, 8)} />}
        </section>
        <dl className="overview-notes">
          <div><dt>Succeeded</dt><dd>{number(data.succeeded)}</dd></div>
          <div><dt>Queue depth</dt><dd>{number(data.queue_depth)}</dd></div>
          <div><dt>Pending retries</dt><dd>{number(data.pending_retries)}</dd></div>
          <div><dt>Average latency</dt><dd>{number(data.avg_latency_ms, ' ms')}</dd></div>
          <div><dt>Degraded integrations</dt><dd>{number(data.unhealthy_integrations)}</dd></div>
          <div className="overview-updated"><dt>Last updated</dt><dd>{time(result.updatedAt)}</dd></div>
        </dl>
      </>}
    </>
  );
}
