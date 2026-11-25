# Engineering workflow

SyncOps uses the lead Codex agent for architecture approval, shared contracts, integration, release checks and Product Owner reporting. Native subagents handle bounded assignments under a concurrency limit of three. The Product Owner specifies outcomes, validates product decisions and demonstrates the system with evidence gathered during development.

## Initial assignments

| Native assignment | Ownership | Evidence |
| --- | --- | --- |
| Architect | Design review | Proposed the SQL queue, lease fencing, Windows and PostgreSQL profiles, and simulator trust boundary |
| Backend | `backend/` | API, migrations, persistence, worker, simulator and backend tests |
| Frontend | `frontend/` | React operations console and real API interactions |
| Platform | `deploy/`, `scripts/`, Compose and workflows | Native launcher, container profile and delivery checks |
| QA | `e2e/native_delivery.py` | Verified live scenarios A–F and a separate worker process crash drill |
| Security | Read-only review | Raised audit exposure, cleartext local secret modes, smoke redirect and container memory risks. The lead applied remediations |
| Documentation | `docs/verification.md` | Recorded acceptance evidence, verification commands and remaining gates |

Implementation began with explicit non-overlapping file ownership in a shared working folder while Git metadata writes required escalation. The local foundation commit established `main` and a separate `feature/core-mvp` branch. A detached test worktree successfully opened the foundation commit. The lead owns integration and remote writes.

The repository stores seven custom role definitions under `.codex/agents/`. Native delegation was exercised using the running chat's available agents. The files were validated as TOML and their option names were verified against the Codex reference. When continuing in a new trusted SyncOps chat, inspect the available agent types for `syncops_architect`, `syncops_backend`, `syncops_frontend`, `syncops_platform`, `syncops_qa`, `syncops_security` and `syncops_documentation`. Record name-based launch results before claiming registration.

## Quality gates

Publish only intended tracked files from a verified commit. Run API/worker tests, lint, type checking, production build, real local delivery and independent review before requesting merge. Record separate outcomes for native SQLite, Compose PostgreSQL, live browser and deployment targets. Avoid deploying local self-hosted CI for public pull requests.

Public GitHub repositories and standard public GitHub-hosted runners fit the lab's $0 budget. Public container publication requires confirming package visibility and free Container registry terms. Avoid paid runner classes and long-lived CI artifacts. See [GitHub Free](https://docs.github.com/en/repositories/creating-and-managing-repositories/about-repositories), [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) and [Packages billing](https://docs.github.com/en/billing/concepts/product-billing/github-packages).

## Advanced DevOps Lab assignments

- The lead reviewed upstream service terms, coordinated worktrees and GitHub checks, refreshed container runtime images after Trivy findings, implemented GHCR candidate controls and centralized logging, and seeded the native demonstration through the API.
- The backend subagent implemented and checked the isolated PostgreSQL recovery and load fixture in `lab/postgres-reliability`. The lead ran its hosted workflow and integrated the verified branch.
- The architect subagent implemented the Helm and Argo CD slices in `lab/kubernetes` and `lab/gitops`. The lead owns CI fixups, checkpoint verification and integration.
- The frontend subagent expanded hosted Chromium acceptance and optional export of bounded synthetic visual evidence in `lab/browser-acceptance`.
- The initial Platform and Security follow-up assignments hit the included Codex usage limit. The lead reassigned Kubernetes and completed the supply-chain lane directly. The failed starts did not create implementation work.

The local app-server confirmed the project config layer and its concurrency limit of three. A native custom `syncops_architect` invocation returned its expected verification marker under the ChatGPT account. Ephemeral CLI testing encountered a thread-store limitation. The named executions succeeded in regular local CLI sessions. The six other exact names also returned `ROLE_OK` in a bounded run. The diagnostic CLI PowerShell startup probes were blocked by Windows package identity restrictions. The lead performed the repository inspection directly.

## Local release acceptance assignments

| Native agent | Assignment | Recorded work |
| --- | --- | --- |
| `syncops_platform` | Operator workflows in an isolated worktree | Implemented Windows and WSL2 launchers and safety tests. Restored a synthetic SQLite snapshot outside the live database. |
| `syncops_security` | Independent candidate and source assurance | Reran Trivy, Gitleaks and package audits, verified both attestation predicates and documented residual findings. |
| `syncops_documentation` | Public guides and private learning guide | Authored the technical implementation guide, architecture diagrams, ten-minute portfolio presentation and a private Ukrainian guide. |
| `syncops_qa` | Read-only independent workstation test | Compared authenticated event histories with PostgreSQL rows and mock effects for all ten seeded cases. Verified the three role boundaries and Retry-After timing. |
| `syncops_architect` | Independent operational and release review | Reviewed cgroup delegation, rollout identity, namespace boundaries and release criteria. The lead addressed the stale local image tag and added a network isolation assertion. |
| `syncops_frontend` | Independent screenshots and targeted fix | Inspected actual workstation captures, verified timezone labels and corrected overlapping search field text. |

The lead configured the workstation, exercised the local deployment and Chromium suite, integrated the changes and owns the release decision. A maximum of three subagents worked concurrently.
