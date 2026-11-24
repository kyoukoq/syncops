# SyncOps product specification

SyncOps is an open-source, self-hosted integration monitoring and recovery platform for operations, business applications, integration, platform and reliability engineers. It tracks synchronization between simulated CRM, ERP and TMS systems, explains delivery failures and provides controlled recovery. The portfolio lab uses synthetic data exclusively and has an additional budget of $0. It must run on a single Windows workstation without paid services or corporate resources.

## Core application

- Manage integrations with an identity, description, source, destination adapter, enabled state, health, processing timeout and retry policy. Select endpoints from trusted deployment configuration. Endpoints must resist SSRF and redirects.
- Ingest validated REST and webhook events, persist them before acknowledgement, and deliver asynchronously from a durable queue. Keep correlation IDs, scoped idempotency keys, delivery metadata, attempts, timestamps and event history.
- Classify failures, apply exponential jittered backoff and `Retry-After`, enforce an attempt budget, reclaim expired leases and move terminal failures to a dead-letter queue. Provide audited, authorized replay while preserving delivery identity and attempt history.
- Simulate company and contact creation, customer updates, account synchronization, orders and shipments. Cover input errors, authentication failures, unavailable responses, rate limits, timeouts, latency and duplicates. Persist simulated side effects to demonstrate idempotency.
- Provide authenticated administrator, operator and read-only viewer roles. Use secure password hashing, expiring sessions, structured audit trails, bounded inputs, safe failure responses, and environment-provided secrets.
- Provide an accessible, responsive light and dark operations console. Users can view real activity and health, configure integrations, search and filter events, inspect attempts and correlation IDs, review dead letters, recover events, investigate incidents, view audit history, and run simulations.

## Deployment and engineering

- Core uses React and TypeScript, FastAPI and SQLAlchemy, Alembic, a durable SQL queue, and PostgreSQL in Compose. A native Windows profile may use SQLite on local disk and must document behavioral differences. Both profiles require repeatable initialization and health checks.
- The optional DevOps lab adds local Kubernetes, Helm, staging and production-lab isolation, Argo CD, controlled promotion and rollback, Prometheus, Grafana, Loki, a supported log collector and Alertmanager. Use infrastructure-as-code only when it simplifies reproducibility. Keep endpoints private and keep single-host reliability claims within the verified deployment semantics.
- GitHub public repository and standard hosted CI use verified $0 options. Use minimal permissions, pinned automation, tests and linting, dependency and secret scanning, build and smoke tests, container scanning, an SBOM and versioned releases. Publish only project-owned clean files and only use free registry workflows with verified public visibility and terms.
- Use native Codex agents for architecture, backend, frontend, platform, independent QA, independent defensive security review and technical writing. Maintain repository-scoped configuration, status, ADRs, change history and clear file ownership. Record actual delegation and results. English artifacts and Ukrainian Product Owner communication.

## Acceptance scenarios

| ID | Scenario | Evidence |
| --- | --- | --- |
| A | Successful synchronization | Queued company event becomes succeeded and creates one destination effect |
| B | Temporary outage | HTTP 503 schedules a retry and an available destination completes it |
| C | Rate limiting | HTTP 429 delays dispatch according to `Retry-After` and preserves unique effects |
| D | Permanent validation error | HTTP 4xx reaches an inspectable dead letter without automatic retries |
| E | Retry exhaustion | A continuing transient failure exhausts its budget. Operator replay after remediation succeeds |
| F | Duplicate event | Reused idempotency key returns the existing ID. Mismatched content conflicts |
| G | Worker crash | An expired claim recovers after crash, including uncertain acknowledgement after a mock commit |
| H | Failed deployment | A deliberately unhealthy isolated version fails checks and the prior version is restored |
| I | Incident investigation | Reconstruct a fault from app history, correlation IDs, retries, audit, metrics and centralized logs |
| J | Disaster recovery | Restore a dedicated lab backup after isolated data loss and verify recovered state |

## Release evidence

Each feature needs implementation, verification and corresponding documentation. Release evidence includes unit, integration, browser, migration, persistence, restart and recovery results, verified deployment profiles, scan results, actual screenshots, demonstrations, runbooks, a postmortem template and portfolio materials. Report Passed, Failed, Not Run, Not Verified and Blocked distinctly. Do not claim production guarantees, exactly-once delivery or availability beyond test evidence.
