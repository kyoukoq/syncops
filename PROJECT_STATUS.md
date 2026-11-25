# SyncOps project status

## Current milestone

The [v0.1.0 MVP preview](https://github.com/kyoukoq/syncops/releases/tag/v0.1.0) remains the published release. The current Advanced DevOps Lab slices have merged through verified public pull requests. Native Windows operation still uses SQLite. Hosted fixtures use PostgreSQL with synthetic data exclusively.

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

- **Windows virtualization** — Firmware virtualization and the hypervisor are enabled. Docker Engine, Compose runtime, Kubernetes and Argo CD on this machine are blocked on WSL installation and first-time Ubuntu setup. Follow the [Windows host runbook](docs/runbooks/windows-container-host.md).
- **Windows browser visual acceptance** — The Codex origin policy blocks `http://127.0.0.1:5173`. Hosted fixture evidence is separate from Windows visual verification.
- **Local profile verification** — Hosted evidence does not establish Windows Compose or Kubernetes operation. Perform the local activation and validation gates before shipping the intended release. Follow the [Advanced DevOps Lab milestone](https://github.com/kyoukoq/syncops/milestone/1).
- **Release** — v0.2.0 is pending the intended scope and deployment verification. GHCR candidate tags are distinct from product releases.

See the [acceptance report](docs/verification.md), [Windows activation runbook](docs/runbooks/windows-container-host.md), and [portfolio demonstration](docs/advanced-lab-demo.md).
