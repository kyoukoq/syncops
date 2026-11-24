# Trace a worker incident with Loki

Use the core and metrics overlays together with the central log overlay on a dedicated lab host.

```powershell
docker compose -f compose.yaml -f compose.observability.yaml -f compose.logs.yaml up -d --build --wait
```

Docker Engine forwards worker stdout over its syslog driver to the loopback UDP listener on port 1514. Alloy forwards the JSON message to Loki. Grafana queries Loki over the private Compose network. The Loki HTTP port is internal and the forwarder has no Docker socket access. Worker logs retain a short local Docker cache. Loki expires stored logs after 72 hours. This lab transport can lose logs during collector outages. Persisted attempts and audit entries remain the authoritative delivery record.

Submit the temporary outage simulation and copy the correlation ID from event detail. Open **SyncOps Worker Incident** in Grafana and paste that ID. Confirm an attempt with `retry_scheduled` followed by `succeeded` and compare the attempt numbers and event ID with SyncOps. Confirm the aggregate worker and delivery metrics in **SyncOps Delivery Overview**. Record the event ID, correlation ID, timestamps, observed symptom, recovery and any missing evidence. The correlation ID is parsed at query time and is not an indexed label.

For verification in the dedicated fixture, set the generated SyncOps and Grafana admin passwords in the environment and run `python3 scripts/logs_smoke.py`. It submits one synthetic event, checks recovery and confirms both matching log records through the provisioned Grafana datasource without exposing the event payload. [Loki retention](https://grafana.com/docs/loki/latest/operations/storage/retention/) · [Alloy syslog receiver](https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.syslog/) · [Docker syslog driver](https://docs.docker.com/engine/logging/drivers/syslog/)
