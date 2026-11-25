# SyncOps MVP acceptance evidence

The native Windows lab used a loopback API, a local SQLite database and synthetic CRM, ERP and TMS adapters. Run `afcaab34` exercised the live API, durable worker and mock destination. The suite created a dedicated integration, disabled it after the run and revoked all three test sessions.

## Scenario results

| ID | Status | Observed evidence |
| --- | --- | --- |
| A | Passed | A synthetic company event completed over HTTP with one persisted mock effect. Viewer event detail excluded the payload. |
| B | Passed | The first attempt returned HTTP 503 and entered the scheduled retry state. The next attempt returned HTTP 200 and produced one mock effect. |
| C | Passed | HTTP 429 requested a two-second delay. The persisted retry was due after 2.000 s and dispatch began after 2.022 s. The mock effect count was one. |
| D | Passed | HTTP 422 entered the dead-letter queue after one attempt, with no retry deadline or mock effect. |
| E | Passed | A persistent timeout exhausted both attempts. Operator replay retained the event and correlation IDs, preserved prior attempts, completed delivery and recorded an audit entry. The viewer replay request returned 403. |
| F | Passed | Eight concurrent submissions with the same key and body returned one event ID and produced one mock effect. Reusing the key with changed content returned 409. |
| G | Passed | In a separate native drill, QA terminated an isolated child worker during HTTP delivery. The destination committed before the replacement acquired the expired lease. The replacement completed the event with interrupted and succeeded attempts and one persisted mock effect. |
| H | Passed in hosted Helm drill | A deliberately unavailable frontend image failed the staging upgrade. Helm restored the prior image and a new event delivered successfully. Argo CD separately rejected an unhealthy staging revision and restored delivery after Git reverts in both environments. [Hosted Kubernetes](https://github.com/kyoukoq/syncops/actions/runs/45512478105) · [Hosted GitOps](https://github.com/kyoukoq/syncops/actions/runs/45513353704) |
| I | Partially verified | Native and hosted browser checks exercised event investigation and replay audit. A hosted real delivery checked both correlated worker records through Grafana and Loki. Windows UI validation remains blocked. [Central log integration](https://github.com/kyoukoq/syncops/actions/runs/45511230280) |
| J | Passed in hosted PostgreSQL and Windows snapshot drill | A SQLite snapshot restored to a new isolated path with matching counts of two events, two attempts and two mock operations. A hosted disposable PostgreSQL drill restored matching fingerprints and a working API in 12.2 seconds. The one unbacked acknowledged record was absent after restore. [PostgreSQL recovery evidence](https://github.com/kyoukoq/syncops/actions/runs/45511422619) |

## Additional checks

| Check | Status | Evidence |
| --- | --- | --- |
| Access and sessions | Passed | Anonymous overview requests, viewer writes, operator administration and non-admin audit requests were rejected. The focused audit regression verified that event-level audit entries are visible to administrators. |
| Backend and database | Passed | All 14 pytest cases passed, followed by a passing focused audit regression. Ruff, `pip check` and the SQLite Alembic upgrade, check, downgrade and re-upgrade passed. |
| Frontend production build | Passed | TypeScript and the Vite production build passed. |
| Windows browser acceptance | Blocked | Browser origin permission for the local console was declined. |
| PostgreSQL Compose and hosted Chromium | Passed | Standard GitHub-hosted CI built and started the Compose stack, verified real PostgreSQL delivery, and passed sign-in, DLQ search, replay, preserved attempt and audit history, theme, mobile navigation and sign-out in Chromium. [GitHub Actions run](https://github.com/kyoukoq/syncops/actions/runs/45506797414) |
| Optional monitoring profile | Passed | The hosted Compose run validated three alert rules, observed real delivery metrics through Prometheus and Grafana, verified dashboard provisioning, and observed the stale-worker alert firing and resolving in Alertmanager. [GitHub Actions run](https://github.com/kyoukoq/syncops/actions/runs/45507954694) |
| Hosted all-page console | Passed | Browser coverage verified live data, integration management, filter navigation, recovery, three roles, console health and mobile navigation. [Chromium acceptance](https://github.com/kyoukoq/syncops/actions/runs/45513587704) |

## Hosted visual evidence

The explicit CI dispatch exported authentic desktop overview and recovery screenshots from an isolated synthetic Compose fixture. Both PNG signatures, byte counts and SHA-256 hashes matched the workflow markers. The overview shows the live activity graph and delivery indicators. The recovery image shows the identical event after HTTP 422 and successful replay, including the audit entry. The screenshots are stored in the ignored local `.syncops/visual-evidence` directory. [Visual evidence run](https://github.com/kyoukoq/syncops/actions/runs/45514208097)

## Repeat the native checks

Start the native profile as described in the [README](../README.md). From the repository root, run the HTTP acceptance suite against the native API and keep the credentials and database local.

```powershell
& .\.venv\Scripts\python.exe e2e/native_delivery.py --base-url http://127.0.0.1:8000
Push-Location backend
& ..\.venv\Scripts\python.exe -m pytest -q
& ..\.venv\Scripts\python.exe -m pytest -q tests/test_recovery.py -k crashed_worker_does_not_duplicate_business_effect
Pop-Location
npm --prefix frontend run build
```

The focused crash regression exercises lease expiry and duplicate-effect prevention with a test fixture. The separate process-termination drill used a disposable worker and database. The [recovery runbook](runbooks/recovery.md#native-sqlite-snapshot-and-restore-drill) contains the native snapshot and restore commands.

These checks establish delivery and recovery behavior for the tested configurations and the supplied synthetic adapters. The [roadmap](../ROADMAP.md) tracks the remaining deployment, observability and portfolio gates.
