# SyncOps MVP API contract

Routes below are relative to `/api/v1` unless otherwise stated. JSON uses snake_case, UTC ISO 8601 timestamps and opaque string IDs. Lists of events use zero-based offsets. Normal application requests use `Authorization: Bearer <session token>`.

## Authentication and policy

| Method | Route | Request and response |
| --- | --- | --- |
| POST | `/auth/login` | `{username, password}` → `{token, user: {username, role}}` |
| GET | `/auth/me` | `{username, role}` |
| POST | `/auth/logout` | Revokes the current bearer session, returns `204` |

Roles are `admin`, `operator`, and `viewer`. All authenticated users can read integrations, overview and events. Operators and admins can submit simulated events and request replay. Only admins can create or change integrations and see all audit entries. Response errors use FastAPI's `detail` field. Credentials and session tokens are never included in API logs.

## Integrations

`GET /integrations` returns `Integration[]`. `POST /integrations` creates one. `PATCH /integrations/{id}` modifies provided fields. Both mutations return the saved `Integration`.

```ts
type System = 'crm' | 'erp' | 'tms'
type Integration = {
  id: string; name: string; description: string;
  source: System; destination: System; enabled: boolean;
  timeout_seconds: number; max_attempts: number; retry_base_seconds: number;
  health: 'healthy' | 'degraded' | 'idle' | 'disabled';
}
```

Create accepts the configuration fields except `id` and `health`. Integrations select the simulator destination by adapter. Only trusted deployment configuration controls the mock service origin. No user-provided URL is fetched.

## Events and simulation

`POST /events` creates a real queued event. Optional `Idempotency-Key` header scopes deduplication to its integration. Same key and same request return the original event, while conflicting reuse returns `409`. Event type values for the demo are `company.created`, `contact.created`, `customer.updated`, `account.synced`, `order.created`, and `shipment.updated`.

```ts
type Scenario = 'success' | 'http_400' | 'http_401' | 'http_429' | 'http_500'
  | 'http_503' | 'timeout' | 'temporary_outage' | 'invalid_response';
type EventInput = {
  integration_id: string; event_type: string; payload: Record<string, unknown>;
  scenario?: Scenario; failure_count?: number; latency_ms?: number;
};
type Status = 'queued' | 'processing' | 'retry_scheduled' | 'succeeded' | 'dead_letter';
type Event = {
  id: string; correlation_id: string; integration_id: string; integration_name: string;
  event_type: string; status: Status; source: System; destination: System;
  attempt_count: number; http_status: number | null; duration_ms: number | null;
  error: string | null; created_at: string; updated_at: string; next_retry_at: string | null;
};
type Attempt = {
  number: number; status: string; started_at: string; finished_at: string | null;
  http_status: number | null; duration_ms: number | null; error: string | null;
};
```

`failure_count` specifies how many deliveries receive the selected failure before normal processing, with `0` meaning persistent. Temporary outage defaults to one failed delivery. `latency_ms` applies to actual mock HTTP responses. An absent scenario means success.

`GET /events?status=dead_letter&search=company&integration_id=...&limit=25&offset=0&sort=newest` returns `{items: Event[], total: number}`. Filter values are optional and `sort` supports `newest` and `oldest`.

`GET /events/{id}` returns `Event & {attempts: Attempt[], audit: AuditEntry[]}`. Arbitrary payload contents are omitted from read responses. `POST /events/{id}/retry` accepts `{reason: string, clear_simulation: boolean}`, requeues a dead-letter event under the same ID and returns the event. Previous attempt history remains intact.

`POST /webhooks/{integration_id}` accepts `{event_type, payload}` with `Idempotency-Key` and `X-Webhook-Secret` headers. Webhook configuration is deployment-scoped and disabled without `SYNCOPS_WEBHOOK_SECRET`. Failure injection is restricted to the authenticated demo submission path.

## Overview and audit

`GET /overview` returns the following object. `active_integrations` counts enabled integrations. `success_rate` is a percentage of terminal events, or null if there are none. `activity` is a bounded chronological set of labeled buckets from persisted events.

```ts
type Overview = {
  total_events: number; succeeded: number; dead_letters: number; success_rate: number | null;
  avg_latency_ms: number | null; active_integrations: number; unhealthy_integrations: number;
  pending_retries: number; queue_depth: number;
  activity: {label: string; succeeded: number; failed: number; pending: number}[];
  integrations: Integration[]; recent_events: Event[];
};
type AuditEntry = {
  id: string; actor: string; action: string; target_id: string;
  detail: string; created_at: string;
};
```

`GET /audit?limit=50&offset=0` returns `{items: AuditEntry[], total: number}`. `GET /health` returns authenticated application status with `{status, database, worker}` string fields. Top-level `/healthz` and `/readyz` are probe endpoints. Top-level `/metrics` is for a private Prometheus scrape.
