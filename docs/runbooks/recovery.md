# Delivery and storage recovery

## Investigate a failed event

1. Open **Dead Letter Queue** and record the event ID and correlation ID from the details view. Check the destination, HTTP status, timestamps and attempt outcomes.
2. For a persistent 4xx, correct the cause before requesting recovery. For a transient failure, check the mock availability, timeout and retry schedule. Use the **System Health** view to distinguish queue activity from component trouble.
3. Admins can open **Audit Logs** to see configuration changes and replay reasons. For native operation, inspect `.syncops/logs/worker.out.log` and match the correlation ID. Avoid copying credentials or arbitrary payloads into incident records.
4. Use **Retry event** as an administrator or operator. Record the reason. Clearing the simulation resolves only the injected lab fault. Verify that the original event ID moved to succeeded and that the new attempt is visible alongside historical attempts.

Sustained backlog or multiple failures on one integration indicate a broader issue than an individual dead letter. Pause new submissions when investigating the affected synthetic flow. Existing processing remains inspectable and should be allowed to reach a safe state.

## Native SQLite snapshot and restore drill

Run from the project root with a started native instance and at least one delivered synthetic event. The ignored `.syncops` directory contains local data and must be treated as sensitive. Use distinct new filenames for each drill.

```powershell
& .\.venv\Scripts\python.exe .\ops\sqlite_snapshot.py .syncops/syncops.db .syncops/drill-backup.sqlite
& .\.venv\Scripts\python.exe .\ops\sqlite_snapshot.py .syncops/drill-backup.sqlite .syncops/drill-restored.sqlite
```

The snapshot helper uses SQLite's online backup interface and verifies the new copy's integrity. Restore to a new isolated file and compare event, attempt and destination-effect rows. Keep the SQLite backup and matching local credential material protected. The helper refuses to overwrite an existing file. Windows native and PostgreSQL use different operating procedures.

## PostgreSQL backup and restore gate

Before using the Compose profile for a recovery demo, create a separate Compose project and synthetic dataset. Use PostgreSQL's `pg_dump` and `pg_restore`, restore to a new empty database, run the current schema migrations, restart the isolated API and worker, then compare event and mock-operation counts. Record the exact image versions, database size, restore time and verified records. The Compose drill requires a working container runtime.

## Incident record

Record customer-facing symptom, lab severity, UTC timeline, the first confirmed cause, recovery steps, verification evidence and an owner for follow-up. Use correlation IDs and masked metadata. Distinguish the duration of the incident from the time required to identify it.
