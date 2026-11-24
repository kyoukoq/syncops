# ADR 0002. Fixed trust boundary for simulator delivery

**Status** — Accepted for the MVP.

## Context

Integration configuration is necessary for a meaningful operations demo. A client-supplied origin would let operators turn the worker into a request proxy. Retried HTTP calls can also repeat business operations.

## Decision

Expose a fixed set of adapter selectors. Only trusted deployment configuration supplies the mock service origin and authorization secret. Disable redirects and use bounded timeouts. Restrict mock failure injection to synthetic events submitted by authorized actors. Issue an idempotency key per logical event and reuse it during all attempts and replay. Sanitize response and log fields before storage or display.

## Alternatives and consequences

Production-configurable origins would require connection-time egress controls, DNS and address policy, SSRF regression coverage, credential scopes and an operator trust model. The fixed local simulator supports the required recovery scenarios with a smaller boundary. Connecting real enterprise systems requires a separate decision and implementation.
