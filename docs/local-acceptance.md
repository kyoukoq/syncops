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

The [incident postmortem](runbooks/local-incident-postmortem.md) records the ERP scenario, measured retry and related alert exercise.

### Isolated PostgreSQL recovery

`bash scripts/syncops.sh restore-drill compose` passed on the Alpine backend, PostgreSQL 17.12 and Docker Compose 5.8.0. The separate project `syncops-pg-lab-0a27ea6f37be` removed its own temporary database during the exercise. Independent QA verified the JSON against the raw log, found no resources remaining under the temporary project label and confirmed the primary PostgreSQL volume was still attached to the regular Compose DB. The recovery JSON SHA-256 is `b142c7024826fba32ae449df89d65ebb7a9390d2e2884395577005faaba0c431`.

| Measurement | Observation |
| --- | --- |
| Worker crash and lease recovery | Exit 137 after one committed effect. The recovery worker observed the expired lease in 29.737 s, preserved the interrupted attempt and completed with exactly one effect. |
| Concurrent delivery and duplicate prevention | 48 requests produced 24 unique deliveries, 12 processed by each worker with overlapping attempt times. Every delivery succeeded and zero business effects were duplicated. |
| Queue and terminal latency | Queue p95 2.620 s. Enqueue to terminal p95 2.889 s. Observed throughput 6.372 events/s for this short workload. |
| Backup and data recovery | A 25,273-byte archive completed in 4.358 s. Restored table counts and fingerprints matched. API access and new delivery passed. |
| Observed RTO | 25.813 s from simulated data loss to verified new delivery. Planned preparation before the loss is outside the measurement. |
| Observed recovery point | The completed archive preceded simulated loss by 4.816 s. One acknowledged post-backup canary was absent as designed. This is one observed recovery gap. |

## Kubernetes and Helm

`systemd-run --user --scope -p Delegate=yes bash scripts/syncops.sh verify kind` passed on kind 0.31.0, Kubernetes and kubectl 1.35.0, and Helm 4.3.1. The first attempt failed because kind's generic Docker image export included a PostgreSQL OCI index with an absent platform blob. The launcher now exports a platform-specific archive with Docker, which both kind and the node's containerd imported successfully. [Docker platform archive support](https://docs.docker.com/reference/cli/docker/image/save/#save-a-specific-platform---platform) · [kind image import issue](https://github.com/kubernetes-sigs/kind/issues/3795)

- Staging started with two ready workers with distinct heartbeats. Helm scaled the deployment to three. Deleting one Pod triggered replacement, and three workers became ready again.
- The restarted PostgreSQL StatefulSet retained the PVC identity and the persisted event, successful attempt and mock effect. Delivery succeeded before and after a deliberately unavailable frontend image caused a failed Helm rollout and automatic rollback.
- Production Lab used separate secrets and a fresh PVC. It delivered its own integration event. Its API connected to PostgreSQL in its namespace and could not connect to the resolved staging database address.
- The cluster was disposable. The console was verified through loopback port-forwards. Live HTTPS Ingress was not run. Worker readiness still represents the pool heartbeat and cannot diagnose an individually stuck worker while peers remain healthy.

## Local Argo CD

The disposable Argo CD Core 3.6.3 lab synced digest-pinned images from a local Git fixture and loopback registry. In the first local run, both environments reached the baseline commit `0e35f48`, staging corrected manually introduced replica drift, and healthy staging commit `8e6c72e` was promoted as the exact Git tree of `48f0b05`. The deliberately missing image in `bbedf5e` failed the staging gate while Production Lab stayed healthy. Staging revert `f564f71` and Production Lab revert `a72eddc` both restored healthy revisions and successful delivery. These Git commits belong to the disposable fixture.

## Release and security

Gitleaks, dependency audits and historical candidate attestation verification passed. The [risk register](security-risk-register.md) covers the 13 distinct CVEs in the 53 HIGH rows reported for the Debian backend. The built Alpine replacement showed zero rows across severity levels in the same Trivy database. The frontend had zero HIGH or CRITICAL rows. Stable publication requires exact GHCR digest verification and explicit Product Owner acceptance of the remaining runtime risks.

Run the workstation procedures from the [operator guide](runbooks/local-operations.md). These measurements describe one workstation and synthetic data. Kubernetes and disaster recovery share a single-host failure domain and carry no production availability claim.
