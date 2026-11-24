# SyncOps roadmap

| Phase | Milestone | Acceptance gate | State |
| --- | --- | --- | --- |
| 00 | Engineering team bootstrap | Real native delegation, supported configuration and tool inventory | In progress |
| 01 | Foundation | Local Git, system design, shared contract and continuity docs | In progress |
| 02 | Backend | Migrations, ingestion, mock adapters and persistence tests | In progress |
| 03 | Reliability | Retry classification, scheduling, leases, DLQ, replay and duplicate-effect verification | In progress |
| 04 | Containerization | Non-root images, PostgreSQL, probes and Compose smoke run | In progress |
| 05 | Web operations console | Browser-tested sign-in, simulation, investigation and replay | In progress |
| 06 | CI/CD | Verified public hosted checks, scans, SBOM and signed-off release workflow | Planned |
| 07 | Observability | Real scraped metrics, centralized logs and actionable alert verification | Planned |
| 08 | Kubernetes | Locally verified Helm charts with probes, persistent storage and resource limits | Planned |
| 09 | GitOps | Verified Argo CD reconciliation, environment promotion and rollback | Planned |
| 10 | DevSecOps | Independent findings addressed, container and dependency evidence, documented trust boundaries | Planned |
| 11 | SRE simulation | Recorded load tests, SLOs, worker failure, deployment rollback and database restore | Planned |
| 12 | Portfolio release | Verified scenarios, screenshots, presentation materials, versioned public release | Planned |

The first release candidate must demonstrate native Windows operations end to end. PostgreSQL/Compose verification enables Kubernetes packaging. Observability and recovery verification precede the production-lab demonstration.
