# SyncOps roadmap

| Phase | Milestone | Acceptance gate | State |
| --- | --- | --- | --- |
| 00 | Engineering team bootstrap | Real native delegation, supported configuration and tool inventory | Core agent execution verified |
| 01 | Foundation | Local Git, system design, shared contract and continuity docs | Passed |
| 02 | Backend | Migrations, ingestion, mock adapters and persistence tests | Passed |
| 03 | Reliability | Retry classification, scheduling, leases, DLQ, replay and duplicate-effect verification | Passed |
| 04 | Containerization | Non-root images, PostgreSQL, probes and Compose smoke run | Passed on WSL2 rootless Docker and in hosted CI |
| 05 | Web operations console | Browser-tested sign-in, simulation, investigation and replay | Passed in Windows Chromium against local Compose and in hosted CI |
| 06 | CI/CD | Hosted checks, scans, SBOM and verified candidate workflow | Passed in hosted CI. Stable product release pending |
| 07 | Observability | Real scraped metrics, centralized logs and actionable alert verification | Metrics, alert recovery and correlation logs passed in local Compose and hosted CI |
| 08 | Kubernetes | Helm charts with probes, persistent storage and resource limits | Passed in hosted kind. Windows deployment pending |
| 09 | GitOps | Verified Argo CD reconciliation, environment promotion and rollback | Passed in hosted kind. Windows deployment pending |
| 10 | DevSecOps | Independent findings addressed, container and dependency evidence, documented trust boundaries | In progress |
| 11 | SRE simulation | Recorded load tests, SLOs, worker failure, deployment rollback and database restore | PostgreSQL concurrency, crash and restore passed in hosted CI |
| 12 | Portfolio release | Verified scenarios, screenshots, presentation materials, versioned public release | Portfolio artifacts prepared. Stable publication awaits risk acceptance and exact-image assurance |

The first MVP has native Windows delivery evidence and hosted PostgreSQL/Compose and Chromium evidence. Observability and recovery milestones precede the production-lab demonstration. See the [Advanced DevOps Lab milestone](https://github.com/kyoukoq/syncops/milestone/1) for active issues.
