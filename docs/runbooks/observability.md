# Local observability

The optional Compose overlay scrapes the SyncOps API every 15 seconds, provisions a Grafana delivery dashboard and routes alerts to the local Alertmanager. It adds no hosted service. Alertmanager groups live alerts in its local UI and has no external notification destinations.

## Start the lab

Run these commands from the repository root with PowerShell 7.4 or later, Docker Engine 28.0 or later and Compose v2. Use the default bridge routing. Earlier Docker versions can expose loopback-published ports to hosts on the same network segment. Keep the original core `.env` for an existing lab. [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/)

```powershell
if (-not (Test-Path -LiteralPath .env)) { ./scripts/Initialize-Compose.ps1 }
$env:SYNCOPS_GRAFANA_PASSWORD = Read-Host 'Set a distinct Grafana admin password' -MaskInput
$stack = @('compose', '-f', 'compose.yaml', '-f', 'compose.observability.yaml')
docker @stack config --quiet
docker @stack up -d --build --wait --wait-timeout 180
```

Grafana uses `admin` and the supplied password when it creates its database. For subsequent starts, provide the same env variable and use the password stored in Grafana. A changed environment value alone does not reset a password in an existing volume. Keep the password in your local credential manager and out of command history and screenshots.

| Interface | Local address | What to inspect |
| --- | --- | --- |
| Grafana | `http://127.0.0.1:3000` | **SyncOps → SyncOps Delivery Overview** |
| Prometheus | `http://127.0.0.1:9090` | Scrape targets and alert rule evaluation |
| Alertmanager | `http://127.0.0.1:9093` | Grouped active alerts and local silences |

The published ports use IPv4 loopback. Prometheus and Alertmanager trust local users. The application proxy does not publish its internal `/metrics` path. Only the API and Prometheus share the private telemetry network. Grafana and Alertmanager communicate with Prometheus through the monitoring network.

## Verify before deployment

Run the bundled config and rule validators before starting services. These one-off checks do not start the core application.

```powershell
docker @stack config --quiet
docker @stack run -T --rm --no-deps --entrypoint /bin/promtool prometheus check config /etc/prometheus/prometheus.yml
docker @stack run -T --rm --no-deps -w /etc/prometheus --entrypoint /bin/promtool prometheus test rules alert-rules.test.yml
docker @stack run -T --rm --no-deps --entrypoint /bin/amtool alertmanager check-config /etc/alertmanager/alertmanager.yml
```

With the stack running, verify readiness and live collection. Confirm `up` equals `1`, the heartbeat timestamp is positive, and the persisted event series show the expected synthetic states. Inspect active alerts using Alertmanager's API.

```powershell
Invoke-WebRequest -NoProxy 'http://127.0.0.1:9090/-/ready' | Select-Object StatusCode
Invoke-WebRequest -NoProxy 'http://127.0.0.1:9093/-/ready' | Select-Object StatusCode
Invoke-RestMethod -NoProxy 'http://127.0.0.1:3000/api/health' | Select-Object database, version
$query = [Uri]::EscapeDataString('up{job="syncops-api"}')
(Invoke-RestMethod -NoProxy "http://127.0.0.1:9090/api/v1/query?query=$query").data.result
Invoke-RestMethod -NoProxy 'http://127.0.0.1:9093/api/v2/alerts'
```

## Isolated worker drill

Run this drill on a disposable SyncOps lab with synthetic traffic. Confirm the worker is healthy, stop it with `docker @stack stop worker`, and leave the API running. Within about two minutes, inspect `SyncOpsWorkerHeartbeatStale` in Alertmanager. Restart the worker with `docker @stack start worker` and confirm that the heartbeat age drops and the alert resolves. The rule waits for 45 seconds of heartbeat age and one minute of continuous evaluation. A graceful worker stop removes its heartbeat and can make the rule pending at the next scrape.

| Alert | Trigger | Investigation |
| --- | --- | --- |
| `SyncOpsApiScrapeFailed` | Scrape target down for 1 minute | Inspect API readiness, DB and the internal scrape target |
| `SyncOpsWorkerHeartbeatStale` | Heartbeat older than 45 seconds for 1 minute while the scrape succeeds | Inspect the worker and DB health, then verify recovery in the event timeline |
| `SyncOpsDeadLettersPresent` | At least one current dead letter for 30 seconds | Inspect attempts and correlation IDs, address the cause, then request authorized recovery |

The dashboard counts current events by state. Successful replay moves an event between those series. The attempt counter counts recorded attempts, including retries, and can restart after restoring a database snapshot.

## Lab reliability objectives

During a controlled exercise, target 99% of accepted events with valid inputs completing within 30 seconds. Calculate the result from accepted and succeeded timestamps for the same run. Report deliberate permanent failures and isolated outage scenarios separately from the steady-state sample. The Prometheus worker heartbeat measures recent worker availability and helps explain events that exceed the target. Save the duration, eligible event count, failed or late count and recovery evidence in the incident record. These are lab objectives for a single host.

## Operation, storage and cost

Use `docker @stack stop grafana prometheus alertmanager` to stop monitoring while leaving SyncOps running. The overlay uses separate named volumes for metrics, Grafana configuration state and Alertmanager state. Prometheus retains seven days or up to 256 MB of metrics blocks, whichever limit removes blocks first. Reserve additional disk space for the write-ahead log and head data. Alertmanager retains notification state for 24 hours. Each monitoring container rotates its local logs at 10 MB and keeps three files. The lab runs one instance of each service.

The images use public release tags with verified Docker Hub manifest digests. Prometheus and Alertmanager are Apache 2.0. Grafana OSS is AGPLv3. The base Docker Compose profile, optional overlay and named volumes run locally without a service account. Docker Hub documents anonymous and free Personal image pull limits. [Prometheus release](https://github.com/prometheus/prometheus/releases/tag/v3.16.0) · [Alertmanager release](https://github.com/prometheus/alertmanager/releases/tag/v0.35.0) · [Grafana OSS image documentation](https://grafana.com/docs/grafana/latest/setup-grafana/configure-docker/) · [Grafana OSS release](https://grafana.com/grafana/download/13.3.0?edition=oss) · [Docker Hub limits](https://docs.docker.com/docker-hub/usage/)
