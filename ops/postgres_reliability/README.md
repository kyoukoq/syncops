# PostgreSQL reliability drill

Run from the repository root with Python 3.12 or newer, a running local Docker engine in the default context, and Docker Compose v2. The drill builds the existing backend image and uses the public PostgreSQL 17 image. It requires no application dependencies on the host.

    python -m ops.postgres_reliability.run

To keep the non-sensitive result, choose a new path outside the tracked files.

    python -m ops.postgres_reliability.run --evidence .syncops/postgres-reliability.json

The evidence path's parent must exist. The public GitHub Actions workflow records its JSON in the job summary. It uses a standard Ubuntu runner and uploads no archives, credentials, or raw logs. [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

## Isolation and cleanup

The runner generates a new project name, source database, restore database, application credentials and mock token on each invocation. It uses a separate labeled volume with an internal database network, and an ephemeral IPv4 loopback port for the API. It never reads existing SyncOps settings or accepts a database URL, project name, remote Docker endpoint, or external archive. It checks exact ownership labels and generated database names before SQL destruction, container termination and project cleanup. The archive lives in the temporary drill directory. Treat it as sensitive during the run because it includes the lab's application state.

The script removes its own disposable data and containers when it finishes. Keep the printed project name for diagnostics if the host is interrupted. Use Docker inspection to verify the exact project label and run ID label before removing any leftovers.

## What the checks prove

- **Crash after commit.** The lab-only HTTP gate sends the production worker's request to the real mock. The runner reads one committed mock operation while the event is still processing, sends SIGKILL to that worker, and checks exit code 137. The replacement workers finish only after the persisted lease expires. The test requires one interrupted attempt, one succeeded attempt and one business effect.
- **Parallel work and idempotency.** The fixed workload sends two concurrent copies of each of 24 keyed requests. It requires 24 unique successful events, one normal attempt and one business effect per event, completions from two different worker containers, and overlapping attempt intervals persisted in PostgreSQL.
- **Backup and restore.** The runner pauses workers to establish a known recovery point, creates a logical archive with pg_dump, and acknowledges one queued canary after the archive. It stops the API and mock, drops the generated source database, confirms the loss, then restores into another empty database with pg_restore. It verifies fingerprints of events, attempts, destination operations, integrations and audit records, reruns Alembic, starts the recovered stack, checks that the later canary is absent and completes a new delivery. [pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html) · [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html)

## Reading the evidence

| Field | Measurement |
| --- | --- |
| Queue wait | Persisted first attempt start minus enqueue timestamp |
| Enqueue to terminal | Persisted successful attempt finish minus enqueue timestamp |
| Delivery throughput | Unique successful events divided by wall time from first submission to observation of terminal state for the batch |
| Worker recovery time | Wall time from issuing SIGKILL until the recovered event is observed to succeed, including lease expiry |
| Observed recovery time | Wall time from initiating isolated database loss until the restored app has verified old data and successfully delivered a new event |
| Recovery point observations | Wall time between backup completion and initiating loss, plus the number of acknowledged post-backup records intentionally excluded from the restored state |

Latency quantiles use nearest rank. These observations describe one bounded synthetic run. PostgreSQL's logical per-database archive requires the destination cluster and database roles to be recreated separately if those are lost. The drill retains its disposable cluster for the restore. It establishes neither a production performance target nor point-in-time recovery.
