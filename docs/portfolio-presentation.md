# SyncOps portfolio presentation

**Project description**

SyncOps is a self-hosted integration reliability platform and DevOps engineering lab. A React and FastAPI console tracks synthetic CRM, ERP and TMS deliveries through a durable SQL queue. It shows which deliveries recovered automatically and gives authorized operators an audited way to replay the remainder. The lab connects application behavior to container assurance, Kubernetes, GitOps, observability and database recovery.

## Business problem

Consider a logistics provider whose ERP sometimes rejects or delays account updates, orders or shipments. A dispatcher needs to know whether a failed shipment update is still retrying, whether it needs intervention and who made the last recovery decision. SyncOps keeps those answers together with the attempt history. Stable event identity reduces the risk that retrying a request creates a duplicate effect. The lab uses fixed mock destinations and synthetic business data.

## Presentation outline

| Segment | Show | Explain |
| --- | --- | --- |
| Business applications | Overview, Integrations and an event timeline | Define which system owns the source data, which destination failed and what a safe replay preserves. |
| DevOps and CloudOps | The PR, Compose checks, image digest and attestations | Trace the source change into a verified artifact and show the limits of each check. |
| Platform engineering | The Helm chart, staged desired revision and Argo CD health and sync status | Show deployment separation, the promotion decision, reconciliation and a Git revert. |
| Reliability and incident response | The application event detail, Grafana, Alertmanager and recovery evidence | Follow one correlation ID and use durable attempts to validate the collected logs. |
| Security and ownership | Scan summary, access boundaries and release gates | Discuss findings by package and exposure. Attribute scope and approval to the Product Owner and engineering and verification work to the recorded AI-assisted process. |

## Engineering lifecycle evidence

| Link in the chain | What to open and identify |
| --- | --- |
| Code change and PR | Review the Docker runtime and assurance changes in [PR #7](https://github.com/kyoukoq/syncops/pull/7). Show the diff, review context and checks. |
| Automated tests | Open [hosted Compose CI](https://github.com/kyoukoq/syncops/actions/runs/45511484017) and [hosted Chromium acceptance](https://github.com/kyoukoq/syncops/actions/runs/45513587704). Identify the tested revision, browser fixture and event replay. |
| Security scanning | Inspect the dependency audit and [container assurance](https://github.com/kyoukoq/syncops/actions/runs/45511484050). Show the Gitleaks history result, Trivy report, non-root check and SBOM. Use the current [project status](../PROJECT_STATUS.md) and [supply-chain documentation](supply-chain.md) for unresolved findings and release disposition. |
| Images and GHCR | Open the [candidate build](https://github.com/kyoukoq/syncops/actions/runs/45512578781) and point out the immutable digests and both provenance and CycloneDX predicates. Confirm whether the cited version is a candidate or published release. |
| GitOps and Kubernetes | Open the [kind deployment drill](https://github.com/kyoukoq/syncops/actions/runs/45512478105) and the [Argo CD drill](https://github.com/kyoukoq/syncops/actions/runs/45513353704). Show a healthy staging revision, drift correction, exact-tree promotion, the bad revision and the Git revert. The hosted Argo drill used its own local-registry images. |
| Observability and recovery | Open the [correlation check](https://github.com/kyoukoq/syncops/actions/runs/45511230280), the [alert lifecycle check](https://github.com/kyoukoq/syncops/actions/runs/45507954694) and [database recovery](https://github.com/kyoukoq/syncops/actions/runs/45511422619). Point out which signals came from the application and which scenario was intentionally induced. |

Present the environment and revision for each item. Use [current local acceptance](../PROJECT_STATUS.md) before describing any part of the chain as verified on this workstation. The [hosted screenshots](https://github.com/kyoukoq/syncops/actions/runs/45514208097) show the real hosted fixture. Use a separately labeled local capture when the session is running locally.

## Prepare the ten-minute demonstration

- Start a disposable dataset using the [deployment profile](../README.md) and open the console. Confirm System Health shows the database and worker ready. Start the [observability](runbooks/observability.md) and [central logs](runbooks/trace-worker-incident.md) overlays in advance for the Grafana portion.
- Seed the native profile from the repository root with `& .\.venv\Scripts\python.exe scripts/seed_demo.py --credentials .syncops/credentials.json`. The [seed script](../scripts/seed_demo.py) accepts a Compose loopback `--base-url` with that profile's local `.env` as its `--credentials` input. Use distinct credentials and keep them out of the recording. The [seed walkthrough](advanced-lab-demo.md#seed-the-native-demo) explains the scenarios and stable keys.
- The final lab seed submits company and contact creation, customer update, account sync, order and shipment creation, and shipment status updates. To generate a fresh shipment example, submit `shipment.created` with **Successful delivery** in **Failure simulation**. Open a successful result, one recovered rate limit and a validation failure before recording. Save only the synthetic event and correlation IDs.
- For a fresh incident and retry timeline, run `bash scripts/syncops.sh demo compose portfolio-demo` with a new batch name. Repeat the same name to keep its event IDs. To demonstrate an empty starting database, use a separate disposable instance with its own storage. [Local operations](runbooks/local-operations.md) · [Recovery and isolated restore](runbooks/recovery.md)
- Open the PR, CI, GHCR and GitOps evidence before presenting. Keep a healthy cluster, a tested prior Git revision and GitOps recovery evidence available for the deployment portion. The ten-minute version can use recorded execution evidence for the slower infrastructure and restore drills.

## Live sequence

| Time | Action | Evidence the audience should see |
| --- | --- | --- |
| 0:00–1:00 | Introduce the logistics case. Open **Overview** and **Integrations**. | Actual totals and activity charts for the disposable dataset, with enabled synthetic routes. |
| 1:00–2:15 | Open the code review and checks, then the candidate digest and attestations. | The tested source revision, scan results and immutable image identity. |
| 2:15–3:30 | Show the staged Git revision, its Helm values and Argo CD health. Open the promotion and rollback evidence. | Separate environments, the Git revision, an immutable image reference, and the healthy revision reached after the revert. |
| 3:30–5:00 | In **Failure simulation**, select the accounts route (CRM to ERP), `customer.updated` and **HTTP 503 · Service unavailable** with one failure before success. Submit a synthetic payload and open the event details. | One event ID and correlation ID, an HTTP 503 attempt, its retry deadline and a successful next attempt. The timestamps and history persist after recovery. |
| 5:00–6:00 | Search **Events** for the seeded HTTP 429 order. Open its first and later attempts. | A rate-limited attempt and later successful delivery. The [Retry-After acceptance trace](verification.md) gives the recorded minimum wait if the UI timestamp precision cannot show it. |
| 6:00–7:15 | Open a seeded HTTP 422 event in **Dead Letter Queue**. As the operator, clear the simulated failure for replay, then check the event and review its audit as admin. | The original validation attempt, same event and correlation IDs, a successful replay and ensuing audit entry. |
| 7:15–9:00 | Paste the HTTP 503 correlation ID into **SyncOps Worker Incident**. Open **SyncOps Delivery Overview** and Alertmanager. | Loki retry and success logs match the application's persisted history. Prometheus shows real delivery and heartbeat metrics. Use the alert exercise below to show firing and resolution. |
| 9:00–10:00 | Open the recovery drill and summarize the security and release limits. Return to **System Health**. | Matching restored row fingerprints, a working new event and the measured gap for a write after backup. |

The HTTP 503 may resolve before a persistent alert can fire. On the disposable Compose stack only, have the stale-worker alert ready using the [timed worker drill](runbooks/observability.md#isolated-worker-drill). Stop the worker after the live event succeeds, let the alert mature while showing the DLQ and then restart the worker. Confirm firing and resolution in Alertmanager. If the alert window exceeds the demo slot, show those observations from the recorded drill and keep the live scene focused on the event trace.

## Likely interview questions

**How do you prevent duplicate processing with no separate broker?** The API cannot acknowledge before the event and intake audit commit. The unique integration/idempotency key prevents duplicate queue entries, while compare-and-update claims and token-fenced writes prevent races between workers. Redelivery can still occur if the downstream effect commits and the worker loses its response. The simulator handles that case with unique effect identity based on the event ID. [Worker and deduplication](technical-guide.md#persistence-and-delivery-guarantees)

**Why use a SQL queue?** It keeps intake, queue state and attempt history durable in one store and makes recovery inspectable in the console. Competing workers and API requests also share database capacity. Use the [controlled PostgreSQL drill](../ops/postgres_reliability/README.md) as a limited workload characterization. A broker would need a delivery handoff strategy and downstream idempotency would still matter.

**What distinguishes retry, replay and rollback?** Retry is a worker policy after a transient error. Replay is an authorized action on a terminal event and retains its history. GitOps rollback changes the desired deployment revision. Database restore is a separate recovery operation with its own accepted data-loss window. [Recovery guide](runbooks/recovery.md) · [GitOps runbook](../deploy/gitops/README.md)

**How do you distinguish pipeline health from service behavior?** A build or an attestation gives evidence about an artifact. Probes and Argo CD health apply to deployment state. An accepted event, persisted delivery attempt and mock effect confirm the application path. Connect them using the deployment revision and event identity. [Verification evidence](verification.md)

**What happens when a worker disappears or a revision fails?** Kubernetes replaces the pod. An expired lease lets a replacement continue the event, and fencing prevents a late completion by the original worker. An unavailable image fails readiness on the new workload. The hosted Helm drill restored the prior image, and the Argo CD drill restored Git desired state with a revert and verified a new event. [Hosted reliability](https://github.com/kyoukoq/syncops/actions/runs/45511422619) · [Hosted GitOps](https://github.com/kyoukoq/syncops/actions/runs/45513353704)

**How do you know the incident data is real?** The simulation calls the same API and queue as other fixture deliveries, and the mock sends actual HTTP responses. The worker writes each attempt, emits a structured log and contributes to metrics derived from persisted state. The same correlation ID appears in the console and Loki. The database remains authoritative if the best-effort log transport drops a record. [Trace walkthrough](runbooks/trace-worker-incident.md)

**Which findings and controls matter for a release?** Read the current scanner results by CVE and affected package, then check applicability, fix availability and controls such as non-root processes, scoped secrets, private networking and limited CI permissions. Require explicit acceptance of material residual risks. Image provenance identifies the build and source context and the SBOM inventories components. Neither settles vulnerability applicability. [Supply chain](supply-chain.md) · [Active gates](../PROJECT_STATUS.md)

**Who built and verified SyncOps?** The Product Owner defined scope, operating constraints and release criteria and enabled the workstation prerequisites. The engineering record attributes AI-assisted changes to actual native Codex assignments and records independent QA and security evidence. Git history, pull requests, run reports and decision records support that account. [Engineering workflow](engineering-workflow.md)

## Trade-offs and future work

- The simulator makes safety and repeatability practical. A real integration needs a destination-specific adapter, contract tests and a verified idempotency strategy.
- Staging and Production Lab use separate credentials and volumes while sharing one host. Additional hosts, managed storage or verified off-host backups would change that failure domain.
- Loopback and namespace boundaries suit a personal lab. Shared use would require further identity, network and data protection controls.
- Local telemetry is bounded and the log forwarding path is best-effort. Future work can test backpressure, retention and a durable forwarding strategy.
- The workload and recovery measurements characterize the test fixture. Future sizing should use representative inputs, longer measurement windows and explicit service objectives.
