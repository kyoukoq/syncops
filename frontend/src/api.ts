import { useCallback, useEffect, useState } from 'react';

export type Role = 'admin' | 'operator' | 'viewer';
export type User = { username: string; role: Role };
export type Session = { token: string; user: User };
export type System = 'crm' | 'erp' | 'tms';
export type Health = 'healthy' | 'degraded' | 'idle' | 'disabled';
export type Status = 'queued' | 'processing' | 'retry_scheduled' | 'succeeded' | 'dead_letter';
export type Scenario = 'success' | 'http_400' | 'http_401' | 'http_403' | 'http_404' | 'http_409' | 'http_422' | 'http_429' | 'http_500' | 'http_502' | 'http_503' | 'http_504' | 'timeout' | 'temporary_outage' | 'invalid_response';

export type IntegrationConfig = {
  name: string;
  description: string;
  source: System;
  destination: System;
  enabled: boolean;
  timeout_seconds: number;
  max_attempts: number;
  retry_base_seconds: number;
};
export type Integration = IntegrationConfig & { id: string; health: Health };

export type SyncEvent = {
  id: string;
  correlation_id: string;
  integration_id: string;
  integration_name: string;
  event_type: string;
  status: Status;
  source: System;
  destination: System;
  attempt_count: number;
  http_status: number | null;
  duration_ms: number | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  next_retry_at: string | null;
};

export type Attempt = {
  number: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  http_status: number | null;
  duration_ms: number | null;
  error: string | null;
};

export type AuditEntry = {
  id: string;
  actor: string;
  action: string;
  target_id: string;
  detail: string;
  created_at: string;
};

export type EventDetail = SyncEvent & { attempts: Attempt[]; audit: AuditEntry[] };
export type Page<T> = { items: T[]; total: number };
export type ActivityBucket = { label: string; succeeded: number; failed: number; pending: number };
export type Overview = {
  total_events: number;
  succeeded: number;
  dead_letters: number;
  success_rate: number | null;
  avg_latency_ms: number | null;
  active_integrations: number;
  unhealthy_integrations: number;
  pending_retries: number;
  queue_depth: number;
  activity: ActivityBucket[];
  integrations: Integration[];
  recent_events: SyncEvent[];
};
export type AppHealth = { status: string; database: string; worker: string };

export const SESSION_EXPIRED = 'syncops:session-expired';

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'The request could not be completed.';
}

async function readError(response: Response): Promise<string> {
  const responseBody: unknown = await response.json().catch(() => null);
  if (typeof responseBody === 'object' && responseBody !== null && 'detail' in responseBody) {
    const { detail } = responseBody;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      const messages = detail.flatMap((entry: unknown) => {
        if (typeof entry !== 'object' || entry === null || !('msg' in entry) || typeof entry.msg !== 'string') return [];
        const field = 'loc' in entry && Array.isArray(entry.loc) ? entry.loc.slice(1).join('.') : '';
        return [field ? `${field.replaceAll('_', ' ')} — ${entry.msg}` : entry.msg];
      });
      if (messages.length) return messages.join('. ');
    }
  }
  return `Request failed (${response.status}).`;
}

export async function request<T>(path: string, token?: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, { ...options, headers, cache: 'no-store' });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new Error('The API is unreachable. Check that the local SyncOps services are running.');
  }
  if (response.status === 401 && token) window.dispatchEvent(new Event(SESSION_EXPIRED));
  if (!response.ok) throw new Error(await readError(response));
  return response.status === 204 ? undefined as T : await response.json() as T;
}

type ResourceState<T> = { key: string; data?: T; error?: string; updatedAt?: number };

export function useResource<T>(path: string, token: string, pollMs = 0) {
  const [state, setState] = useState<ResourceState<T>>({ key: path });
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((current) => current + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;

    async function load() {
      try {
        const data = await request<T>(path, token, { signal: controller.signal });
        if (!controller.signal.aborted) setState({ key: path, data, updatedAt: Date.now() });
      } catch (error) {
        if (!controller.signal.aborted) {
          setState((previous) => ({ ...(previous.key === path ? previous : {}), key: path, error: errorMessage(error) }));
        }
      } finally {
        if (pollMs && !controller.signal.aborted) timer = window.setTimeout(load, pollMs);
      }
    }

    void load();
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [path, token, pollMs, revision]);

  const current = state.key === path ? state : { key: path };
  return { ...current, loading: current.data === undefined && current.error === undefined, refresh };
}
