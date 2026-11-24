# SyncOps project status

## Current milestone

The native Windows MVP is in implementation. Git was initialized locally. A native architecture agent proposed the service boundaries and reliability semantics. Backend, frontend and platform implementation are assigned to three native agents with non-overlapping path ownership.

## Architecture

React/Vite console, FastAPI control plane, SQLAlchemy persistence, Alembic migrations, SQL-backed worker, and mock HTTP adapters representing CRM, ERP and TMS. SQLite WAL is the native Windows profile. PostgreSQL is the Compose profile. See [ADR 0001](docs/adr/0001-core-architecture.md) and the [API contract](docs/api-contract.md).

## Environment evidence

- Verified Git 2.56, PowerShell 7.6, Node.js 24 and npm 11, VS Code command, and a bundled Python 3.12 executable.
- GitHub connector reported the personal login `kyoukoq`. GitHub CLI was absent. No SyncOps remote was configured at initialization.
- Docker, Helm and Kubernetes tooling were absent from PATH. The WSL launcher reported that WSL was not installed.
- Verified a native agent completed the architecture assignment. Project TOML registration in a newly trusted session is pending.

## Verification

Product tests and deployment checks are pending implementation. See [ROADMAP.md](ROADMAP.md) for later profile gates.
