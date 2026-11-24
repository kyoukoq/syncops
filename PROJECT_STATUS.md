# SyncOps project status

## Current milestone

The native Windows MVP is implemented and independently verified through its API and worker. A native architecture agent proposed the service boundaries and reliability semantics. Backend, frontend and platform agents delivered their assigned areas. Independent QA verified scenarios A–G, and the lead addressed material defensive review findings.

## Architecture

React/Vite console, FastAPI control plane, SQLAlchemy persistence, Alembic migrations, SQL-backed worker, and mock HTTP adapters representing CRM, ERP and TMS. SQLite WAL is the native Windows profile. PostgreSQL is the Compose profile. See [ADR 0001](docs/adr/0001-core-architecture.md) and the [API contract](docs/api-contract.md).

## Environment evidence

- Verified Git 2.56, PowerShell 7.6, Node.js 24 and npm 11, VS Code command, and a bundled Python 3.12 executable.
- GitHub and Git Credential Manager confirmed `kyoukoq`. GitHub CLI was absent. The [public SyncOps repository](https://github.com/kyoukoq/syncops) contains the foundation commit. MVP changes are on `feature/core-mvp`.
- Docker, Helm and Kubernetes tooling were absent from PATH. The WSL launcher reported that WSL was not installed.
- Verified native agent execution and functional Git worktrees. Parsed eight project TOML files, including seven unique custom roles. Project role registration in a newly trusted session is pending.

## Verification

| Check | Status | Evidence |
| --- | --- | --- |
| Native Windows launch | Passed | `pwsh -File scripts/Start-SyncOps.ps1 -SkipInstall` started API, worker, mock and Vite with local bindings |
| SQLite migration and API/worker tests | Passed | Alembic upgrade/check/downgrade/re-upgrade, Ruff lint and format, `pip check`, and 14 pytest cases |
| Live pipeline smoke | Passed | Real sign-in, accepted event, idempotent duplicate, mock HTTP delivery and attempt history via the Vite API proxy |
| Independent native scenarios A–F | Passed | `python e2e/native_delivery.py --base-url http://127.0.0.1:8000` verified 503 recovery, minimum 2.000 s Retry-After (observed 2.022 s), immediate 422 DLQ, persistent timeout exhaustion, audited replay, eight concurrent duplicate submissions, role gates and session revocation |
| Independent worker-crash drill G | Passed | QA terminated an isolated child worker during HTTP delivery. Its replacement reclaimed the expired lease and completed the event, preserving interrupted and succeeded attempts and one mock business effect |
| Native snapshot and restore | Passed | Restored a live SQLite snapshot to a new path. Event, attempt and mock-operation counts matched (2 each) |
| Frontend types and build | Passed | `npm --prefix frontend run build` compiled TypeScript and Vite production assets |
| Windows browser QA | Blocked | Browser origin approval declined access to `127.0.0.1:5173` |
| Compose and PostgreSQL | Not Run locally | Docker and WSL absent. Hosted CI has an isolated Compose and browser test |
| Kubernetes, GitOps and centralized observability | Not Run | Planned after core verification |

## Defensive review

Scoped event audit to admins, limited smoke-test authentication to loopback with redirects disabled, created Compose secrets with POSIX mode `0600`, and increased API memory headroom for concurrent scrypt computations. Local secret files and SQLite artifacts are ignored by Git.
