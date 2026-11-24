# ADR 0001. Durable SQL queue and HTTP simulator

**Status** — Accepted for the MVP.

## Context

SyncOps needs a reliable demonstration on a Windows workstation, predictable recovery and one source of truth for accepted events. The tested workstation had no container runtime and no WSL installation. Compose and Kubernetes remain project targets.

## Decision

Use a React/Vite console, a FastAPI REST service, a separate lease-based worker and one private mock HTTP service with CRM, ERP and TMS adapters. Use SQLAlchemy and Alembic against a common schema. PostgreSQL is the Compose database. SQLite with WAL on local disk enables the native Windows profile.

Persist the event and queue state before acknowledging ingestion. Scope idempotency to the integration and verify a fingerprint on reuse. Claim due work with an atomic conditional update and a lease token. Workers can reclaim abandoned work and must present the current token before recording a result. Use a stable event ID at each delivery. The simulator transactionally deduplicates its effect by dimension and event ID.

## Alternatives

Redis or a broker would add coordination between accepted events and a second persistence boundary. In-memory processing cannot demonstrate durable restart recovery. One database reduces deployment and verification overhead. SQLite is suitable for the one-host profile. PostgreSQL is the path to reliable multiworker concurrency.

## Consequences

Delivery may repeat after uncertainty about the remote response. Idempotent destination behavior is a prerequisite, and the demo simulator proves it only within its own storage boundary. PostgreSQL and SQLite need independent tests because locking and operational characteristics differ. A local lab remains one failure domain.
