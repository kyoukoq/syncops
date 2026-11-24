# SyncOps incident postmortem template

## Incident summary

- Incident ID and UTC window
- Affected synthetic integration and impact on accepted deliveries
- Source of detection and whether service objectives were affected

## Timeline and evidence

Record accepted event IDs and correlation IDs, persisted attempt transitions, appropriate Prometheus alert timestamps, and the relevant Loki queries. Link the exact application version, configuration revision and CI run. Record system-clock differences that might affect reconstructed chronology.

## Recovery and protection

Describe the root cause, remediation, operator or controller action, and how successful delivery and duplicate exclusion were verified. If a backup was used, record archive completion and incident times, observed service recovery time and the count of acknowledged records missing after restore. Use the affected lab environment and redact credentials and event payloads.

## Follow-up

Associate each remediation with a GitHub issue, owner and acceptance check. Record a blind spot when the available evidence did not establish a claim.

## Example from the isolated PostgreSQL drill

A runner terminated a worker after its destination committed an effect and before acknowledgement. A replacement reclaimed the expired lease after approximately 30.16 seconds and wrote the succeeded attempt. The destination still contained one business effect. The database-loss portion restored a 25,289-byte logical archive into another disposable database and verified fresh delivery through the restored API in 12.2 seconds. The one record acknowledged after backup completion was absent from the restored snapshot. [Hosted PostgreSQL acceptance](https://github.com/kyoukoq/syncops/actions/runs/45511422619)
