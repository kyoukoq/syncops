# SyncOps roadmap

| Phase | Milestone | Acceptance gate | State |
| --- | --- | --- | --- |
| 00 | Engineering team bootstrap | Real native delegation, supported configuration and tool inventory | Core agent execution verified |
| 01 | Foundation | Local Git, system design, shared contract and continuity docs | Passed |
| 02 | Backend | Migrations, ingestion, mock adapters and persistence tests | Passed |
| 03 | Reliability | Retry classification, scheduling, leases, DLQ, replay and duplicate-effect verification | Passed |
| 04 | Containerization | Non-root images, PostgreSQL, probes and Compose smoke run | Passed on WSL2 rootless Docker and in hosted CI |
| 05 | Web operations console | Browser-tested sign-in, simulation, investigation and replay | Passed in Windows Chromium against local Compose and in hosted CI |
| 06 | CI/CD | Hosted checks, scans, SBOM and verified stable image promotion | Passed. v0.2.0 GHCR tags use the attested candidate manifests |
| 07 | Observability | Real scraped metrics, centralized logs and actionable alert verification | Metrics, alert recovery and correlation logs passed in local Compose and hosted CI |
| 08 | Kubernetes | Helm charts with probes, persistent storage and resource limits | Passed in rootless workstation kind and hosted kind |
| 09 | GitOps | Verified Argo CD reconciliation, environment promotion and rollback | Passed in rootless workstation kind and hosted kind |
| 10 | DevSecOps | Independent findings addressed, container and dependency evidence, documented trust boundaries | Passed for v0.2.0. Lab-only residual risks accepted and review scheduled |
| 11 | SRE simulation | Recorded load tests, SLOs, worker failure, deployment rollback and database restore | PostgreSQL concurrency, lease recovery and restore passed locally and in hosted CI |
| 12 | Portfolio release | Verified scenarios, screenshots, presentation materials, versioned public release | [v0.2.0 published](https://github.com/kyoukoq/syncops/releases/tag/v0.2.0) on 2026-11-25 |

The [Advanced DevOps Lab milestone](https://github.com/kyoukoq/syncops/milestone/1) tracks the completed work. Live HTTPS Ingress and visual acceptance of the native Windows SQLite profile remain unverified. See the [release decision](docs/releases/v0.2.0.md) for the approved scope and the [security risk register](docs/security-risk-register.md) for maintenance.
