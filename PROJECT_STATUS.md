# SyncOps project status

## Current milestone

The [v0.1.0 MVP preview](https://github.com/kyoukoq/syncops/releases/tag/v0.1.0) remains the published release. The Advanced DevOps Lab entered local acceptance from main revision `f0e4aca`. The workstation has a dedicated Ubuntu WSL2 checkout and separate PostgreSQL credentials. Native Windows operation still uses SQLite.

## Local acceptance

| Gate | Status | Evidence |
| --- | --- | --- |
| Rootless Linux foundation | Passed | Ubuntu 24.04.5 under WSL2, systemd 255 as PID 1, Docker Community Engine 29.10.1 and Compose 5.8.0. Cgroup v2 and CPU, memory, PID and I/O delegation verified. The daemon uses a user-owned Unix socket. |
| Compose and synthetic delivery | Passed | PostgreSQL, API, worker, web and private CRM, ERP and TMS simulator started healthy. Independent QA confirmed 10 distinct demo events and correlation IDs, eight successful mock effects and two permanent HTTP 422 dead letters. Two HTTP 503 retries recovered. HTTP 429 waited 2.192 s from failure completion to next attempt, above the two-second Retry-After. |
| Windows Chromium against Compose | Passed | Chromium accessed the actual WSL2 deployment through Windows loopback. All console pages, three roles, denied operations, real charts, filters, light and dark themes, mobile navigation, replay and audit passed. Seven genuine screenshots were captured locally. |
| Observability and incident flow | Passed | Prometheus loaded three rules and scraped successful deliveries. Grafana loaded both dashboards. Loki returned the retry and success worker records through the Alloy pipeline for correlation ID `6f3e1061-c096-46ba-af76-818b4dfa1c69`. Alertmanager fired on a stopped worker and resolved after restart. |
| Kubernetes and Helm | Passed | Rootless kind ran Kubernetes 1.35.0 with Helm 4.3.1. The lab scaled two workers to three, replaced a worker Pod, preserved PostgreSQL state through Pod replacement, rolled back a failed upgrade and verified delivery and network isolation in both namespaces. |
| Argo CD | Passed | Argo CD Core 3.6.3 reached healthy, digest-pinned revisions, repaired live replica drift, promoted the healthy staging tree to Production Lab and recovered both environments from Git reverts. |
| Isolated PostgreSQL restore and load | Passed | The Alpine backend passed lease recovery, 24 unique deliveries from 48 requests with zero duplicate effects, and a verified database restore. Observed recovery was 25.813 s. |
| Backend runtime remediation | Passed for local scan | The supported Alpine base reduced the backend package inventory from 87 to 38 and the same Trivy database reported zero OS and Python rows after pip was removed from runtime. SQLite and wheel-vendored libraries remain separately tracked. |
| Core regressions | Passed | 15 backend tests, Ruff, TypeScript and Vite production build. Dependency audits and Gitleaks also passed in an independent security review. |
| Stable release | Blocked | Explicit Product Owner acceptance of material [security risks](docs/security-risk-register.md) and assurance for the exact proposed release digests are required. |

The [local verification report](docs/local-acceptance.md) records tools, commands, loopback endpoints and observed recovery measurements.

## Verified vertical slices

| Gate | Status | Evidence |
| --- | --- | --- |
| Native operation and demo data | Passed | Windows API readiness returned HTTP 200. Running `scripts/seed_demo.py` twice returned the same nine correlation IDs across three dedicated integrations, with seven succeeded and two dead-letter events. |
| Repository-scoped Codex configuration | Passed for effective configuration and all seven roles | Local app-server `config/read` returned the project layer and an effective cap of three. ChatGPT-authenticated CLI runs started all seven custom names and received verification markers. The additional six ran with at most two nested agents active. |
| Core Compose and Chromium | Passed in hosted CI | The release fixture rebuilt with the refreshed runtime images and passed its API and browser smoke checks. [Core regression](https://github.com/kyoukoq/syncops/actions/runs/45511484017) |
| Supply-chain scanning and SBOM | Passed in hosted CI | Gitleaks reported no leaks, the runtime UID checks passed, and both CycloneDX SBOMs were generated. Trivy reported zero high or critical frontend findings and 53 backend findings with no fixed version in the advisory database. The gate currently fails high or critical findings with a published fix. [Container assurance](https://github.com/kyoukoq/syncops/actions/runs/45511484050) |
| GHCR candidate publishing and attestations | Passed | Hosted CI pushed versioned image candidates by digest and generated provenance and CycloneDX SBOM attestations. Anonymous manifest requests returned HTTP 200 for both digests. GitHub CLI independently verified both predicate types for both image digests while excluding self-hosted signers. [Publication and attestation run](https://github.com/kyoukoq/syncops/actions/runs/45512578781) |
| Worker log correlation | Passed in hosted CI | Alloy collected actual worker stdout. Grafana queried Loki for the same correlation ID and found both `retry_scheduled` and `succeeded` without the payload marker. [Central log integration](https://github.com/kyoukoq/syncops/actions/runs/45511230280) |
| PostgreSQL crash, load and restore | Passed in hosted CI | Worker `SIGKILL` after committed effect left one mock effect after lease recovery. Two workers split 24 unique events from 48 requests evenly with no duplicate business effects. Queue p95 2.194 s, terminal p95 2.453 s, observed restore 12.2 s. The matching archive excluded one acknowledged post-backup record, as expected. [Reliability run](https://github.com/kyoukoq/syncops/actions/runs/45511422619) |
| Kubernetes and Helm | Passed in hosted kind | Staging and production-lab used separate credentials and volumes. CI scaled workers from two to three, preserved the PostgreSQL PVC through pod replacement, and verified restored service after a failed Helm rollout. [Kubernetes lab](https://github.com/kyoukoq/syncops/actions/runs/45512478105) |
| GitOps and rollback | Passed in hosted kind | Argo CD reconciled digest-pinned staging and production-lab, reversed replica drift, gated promotion on the staged Git tree, blocked a revision with an unavailable image and recovered both environments by Git revert. Delivery smoke passed after recovery. [Argo verification](https://github.com/kyoukoq/syncops/actions/runs/45513353704) |
| Extended console acceptance | Passed in hosted Chromium | Hosted 1440×1024 desktop and 390×844 mobile coverage includes live chart bars, filter state, integration management, incident and audit views, role gates, retry/replay and sign-out. The explicit visual-evidence run generated seven authentic PNGs, and two were retrieved, verified against SHA-256 and visually inspected. [Browser acceptance](https://github.com/kyoukoq/syncops/actions/runs/45513587704) · [Visual evidence](https://github.com/kyoukoq/syncops/actions/runs/45514208097) |

The load and recovery measurements represent one disposable runner with a small synthetic dataset. They do not establish a production service-level claim.

## Active or blocked gates

- **Native browser origin**. The previously declined in-app permission for `http://127.0.0.1:5173` concerns the SQLite console. The separate Compose console at port 8080 opened in the in-app browser and passed its local Chromium suite.
- **Release**. v0.2.0 awaits the final evidence and explicit risk decision. GHCR candidate tags identify prerelease artifacts.

See the [acceptance report](docs/verification.md), [Windows activation runbook](docs/runbooks/windows-container-host.md), and [portfolio demonstration](docs/advanced-lab-demo.md).
