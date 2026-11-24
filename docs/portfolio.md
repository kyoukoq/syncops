# SyncOps portfolio walkthrough

## Project description

SyncOps is a self-hosted operations console for monitoring synthetic CRM, ERP and TMS integration traffic. It persists events before delivery, applies configurable transient-error recovery, exposes dead letters and gives authorized operators a way to investigate and replay failures. A stable delivery identity lets mock destinations deduplicate business effects after an uncertain response.

## Demonstration sequence

1. Sign in to a running native lab. Use **Failure Simulation** to submit a successful `company.created` event through Mock CRM to Mock ERP. Open the event and review the first attempt.
2. Submit a temporary outage and watch the event transition through retry scheduling to delivery. Check the recorded HTTP 503 and attempt times.
3. Submit a permanent validation failure. Open **Dead Letter Queue**, inspect the error, request recovery with a reason and clear the injected fault. Show the same event ID and preserved attempt history after success.
4. Show **Audit Logs** as an admin. Identify the affected event by correlation ID and review the replay actor and timestamp.
5. Explain how the worker claims a lease and how a destination commits its idempotent effect. Use test evidence when presenting worker restart or duplicate recovery scenarios.

## Presentation outline

1. Business problem and target operations teams.
2. Browser walkthrough from delivery to recovery.
3. Services, database boundary and durable event lifecycle.
4. Transient and permanent failure behavior, idempotency and remaining guarantees.
5. Authentication, authorization, audit history and private mock egress.
6. Native and container verification evidence, current limitations and next lab milestones.
7. Product ownership and documented native Codex collaboration.

## Interview prompts

- **Why use a SQL queue?** A single transaction persists acceptance and work availability. It reduces dependencies for a self-hosted lab. Database contention and throughput need measurement before scaling.
- **What happens if the worker dies after the destination commits?** The lease expires and another attempt can deliver with the original event identity. The destination deduplicates that operation. A stale worker result is fenced.
- **Why do 400 and 503 behave differently?** Invalid input normally requires correction. A temporary availability error can resolve while the bounded retry budget is active.
- **How would you add a real destination?** Define its idempotency contract and credential scope, then add an allowlisted adapter, egress policy, integration tests and operational verification.

## Resume entry

Led product definition and acceptance for SyncOps, a self-hosted integration reliability lab built with an AI-assisted engineering team. Defined failure and recovery scenarios, reviewed architecture trade-offs, and prepared an evidence-based demonstration of durable delivery, audit trails and controlled replay.
