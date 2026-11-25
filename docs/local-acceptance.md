# Local release acceptance

The workstation checks started on 2026-11-25 from SyncOps main revision `f0e4aca`. The Windows checkout retained its native SQLite data. Ubuntu WSL2 used its own checkout, generated credentials, PostgreSQL volume and synthetic fixtures. Hosted GitHub Actions evidence appears in the [original acceptance report](verification.md).

## Host and Compose

| Check | Result |
| --- | --- |
| WSL | Passed. Default Ubuntu 24.04.5 distribution, WSL2, systemd 255 as PID 1, Linux kernel 6.18.58.1, 12 CPUs and a 15 GiB WSL memory allocation. |
| Docker | Passed. Community Engine 29.10.1, Compose 5.8.0, rootless context, user Unix socket, systemd cgroup v2 and delegated controllers. The system daemon and automatic user-service startup were disabled. |
| Container builds and networking | Passed. The backend, frontend, database, simulator and migration ran in Docker. The database was reachable from the app on the private network. Only loopback ports were published. Container UIDs were 10001 for the API and 101 for nginx. |
| Health and persistence | Passed. API, worker, simulator, database and frontend health checks passed, migration exited 0, and the named database volume retained 49 events after a database restart. |
| Backup artifact | Passed. The operator launcher created a private PostgreSQL custom-format archive and `pg_restore --list` read its catalog. |
| Synthetic dataset | Passed. The application processed 10 events through three integrations and issued ten distinct event and correlation IDs. A named batch returned the same correlations on repeat. |
| Integration and access controls | Passed. Independent QA checked all three roles and matched API results against the PostgreSQL database in a read-only transaction. The audit endpoint was admin-only. Logout revoked each session. |

### Verified Windows loopback endpoints

| Service | URL | Probe |
| --- | --- | --- |
| SyncOps | `http://127.0.0.1:8080/` | Visible sign-in, live browser acceptance, `/healthz` |
| Grafana | `http://127.0.0.1:3000/` | Health, authenticated dashboard and Loki datasource query |
| Prometheus | `http://127.0.0.1:9090/` | Readiness, parsed rules and successful event series |
| Alertmanager | `http://127.0.0.1:9093/` | Readiness, active alert and resolution |

Loki and Alloy stay inside the Docker networks. Alloy accepts syslog on a WSL loopback UDP port. Grafana provides the authenticated path for log searches. PostgreSQL, API and simulator have no published host ports.

## Application and reliability

- Two transient 503 cases recovered with recorded retry gaps of 0.949 s and 0.860 s. The 429 order case respected its two-second Retry-After with a measured 2.192 s gap. The two validation failures entered the dead-letter queue after one 422 attempt with zero destination effects.
- Windows Chromium ran `npm --prefix frontend run test:e2e` at the Compose loopback URL with all three generated test credentials. It verified every console page, authentication, restrictions, charts, filters, pagination, both themes, a mobile viewport and audited replay. Seven genuine PNGs were captured. The [overview](images/local-overview.png) and [recovery](images/local-event-recovery.png) were independently reviewed and contain synthetic data.
- The 15 backend tests, Ruff, the production frontend build and npm audit passed on Windows. The updated Python 3.12.16 and SQLite 3.54.1 pair also passed the backend tests in an isolated Windows environment. The native installation remains independently managed.

## Observability and recovery

`promtool check config`, `promtool test rules` and `amtool check-config` passed in their running containers. Prometheus exposed nine succeeded deliveries at the time of the observed query. Grafana loaded `syncops-overview` and `syncops-worker-incident`. The Loki query through Grafana returned both retry and success for correlation ID `6f3e1061-c096-46ba-af76-818b4dfa1c69` and excluded the synthetic payload. Alertmanager received the stale worker alert after the lab stopped its worker. The alert resolved after the worker restarted and Prometheus observed a fresh heartbeat.

## Release and security

Gitleaks, dependency audits and published candidate attestation verification passed. The [risk register](security-risk-register.md) covers the 13 distinct CVEs in the 53 HIGH backend package rows. The current candidate scan reported zero CRITICAL rows and zero fixable backend rows. The frontend candidate had zero HIGH or CRITICAL rows. Stable publication remains blocked on explicit risk acceptance and assurance for the exact proposed release images.

Run the workstation procedures from the [operator guide](runbooks/local-operations.md). These measurements describe one workstation and synthetic data. Kubernetes and disaster recovery share a single-host failure domain and carry no production availability claim.
