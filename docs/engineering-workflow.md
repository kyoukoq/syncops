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

Implementation began with explicit non-overlapping file ownership in a shared working folder while Git metadata writes required escalation. The local foundation commit established `main` and a separate `feature/core-mvp` branch. A detached test worktree successfully opened the foundation commit. The lead owns integration and remote writes.

The repository stores seven custom role definitions under `.codex/agents/`. Native delegation was exercised using the running chat's available agents. The files were validated as TOML and their option names were verified against the Codex reference. When continuing in a new trusted SyncOps chat, inspect the available agent types for `syncops_architect`, `syncops_backend`, `syncops_frontend`, `syncops_platform`, `syncops_qa`, `syncops_security` and `syncops_documentation`. Record name-based launch results before claiming registration.

## Quality gates

Publish only intended tracked files from a verified commit. Run API/worker tests, lint, type checking, production build, real local delivery and independent review before requesting merge. Record separate outcomes for native SQLite, Compose PostgreSQL, live browser and deployment targets. Avoid deploying local self-hosted CI for public pull requests.

Public GitHub repositories and standard public GitHub-hosted runners fit the lab's $0 budget. Public container publication requires confirming package visibility and free Container registry terms. Avoid paid runner classes and long-lived CI artifacts. See [GitHub Free](https://docs.github.com/en/repositories/creating-and-managing-repositories/about-repositories), [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) and [Packages billing](https://docs.github.com/en/billing/concepts/product-billing/github-packages).
