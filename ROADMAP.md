# SyncOps roadmap

| Phase | Milestone | Acceptance gate | State |
| --- | --- | --- | --- |
| 00 | Engineering team bootstrap | Real native delegation, supported configuration and tool inventory | In progress |
| 01 | Foundation | Local Git, system design, shared contract and continuity docs | Passed |
| 02 | Backend | Migrations, ingestion, mock adapters and persistence tests | Passed |
| 03 | Reliability | Retry classification, scheduling, leases, DLQ, replay and duplicate-effect verification | Passed |
| 04 | Containerization | Non-root images, PostgreSQL, probes and Compose smoke run | Passed in hosted CI |
| 05 | Web operations console | Browser-tested sign-in, simulation, investigation and replay | Passed in hosted Chromium |
| 06 | CI/CD | Verified public hosted checks, scans, SBOM and signed-off release workflow | In progress |
| 07 | Observability | Real scraped metrics, centralized logs and actionable alert verification | Metrics, dashboard and alert recovery passed in hosted CI. Centralized logs pending |
| 08 | Kubernetes | Locally verified Helm charts with probes, persistent storage and resource limits | Planned |
| 09 | GitOps | Verified Argo CD reconciliation, environment promotion and rollback | Planned |
| 10 | DevSecOps | Independent findings addressed, container and dependency evidence, documented trust boundaries | In progress |
| 11 | SRE simulation | Recorded load tests, SLOs, worker failure, deployment rollback and database restore | In progress |
| 12 | Portfolio release | Verified scenarios, screenshots, presentation materials, versioned public release | Planned |

The first MVP has native Windows delivery evidence and hosted PostgreSQL/Compose and Chromium evidence. Observability and recovery milestones precede the production-lab demonstration. See the [Advanced DevOps Lab milestone](https://github.com/kyoukoq/syncops/milestone/1) for active issues.
