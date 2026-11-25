# Postmortem of the local ERP recovery drill

**Date** — 2026-11-25. **Environment** — rootless Docker Compose on Ubuntu WSL2. **Impact** — synthetic logistics deliveries in the lab.

## Incident and response

The workstation seed deliberately made the simulated ERP reject the first customer update with HTTP 503. SyncOps kept the failed attempt and scheduled another dispatch. The next attempt started 0.949 seconds after the first attempt completed and returned HTTP 200. Read-only PostgreSQL verification found one destination effect for the event. The application kept the event and correlation IDs throughout the retry.

| Relative step | Evidence |
| --- | --- |
| Accept event | The application accepted `customer.updated` with correlation ID `743bfff3-adbc-4016-a13a-18263acb2764`. |
| Receive the temporary failure | The first attempt recorded HTTP 503. SyncOps scheduled a retry. |
| Recover | The next attempt recorded HTTP 200. Independent QA found one persisted mock effect. |
| Verify the log path | A second temporary outage exercised the same retry path in the log smoke check. Grafana queried Loki for `6f3e1061-c096-46ba-af76-818b4dfa1c69` and returned the worker's retry and success records without the payload. |
| Verify worker availability alerts | In a separate drill, a stopped worker caused the stale-heartbeat alert to fire. Starting it restored the heartbeat and cleared the alert in Alertmanager. |

The failure was intentionally injected by the simulator. No real ERP, customer records or external service participated. The alert drill tested a worker outage. A single automatically recovered 503 does not justify the stale-heartbeat alert.

## Follow-up

- Use the event ID and attempt history to confirm whether a transient incident recovered. Inspect the same correlation ID in Grafana when application history needs supporting logs.
- Use a new named demo batch when repeating the exercise. This creates fresh incident records and preserves the prior timeline and audit history.
- Treat workload readiness and alerting at the current worker-pool level. Apply the [recovery runbook](recovery.md) for a real backlog or a failed replay within the lab.

Use the [correlation walkthrough](trace-worker-incident.md) and the [workstation report](../local-acceptance.md) to repeat the checks.
