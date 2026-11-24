# ADR 0003. WSL2 and declarative local lab

**Status** — Accepted for the Advanced DevOps Lab. Windows host activation is pending.

## Context

SyncOps must retain its Windows SQLite profile and provide an isolated Linux container and Kubernetes lab on one workstation. The target host reports Windows 11 Pro build 26200, an active hypervisor, enabled firmware virtualization and approximately 32 GiB memory. The current session is not elevated and WSL is not installed.

## Decision

Use Ubuntu 24.04 on WSL2 with Docker Engine and its Compose plugin. Prefer rootless Engine in a dedicated Ubuntu environment when user-service and cgroup delegation checks pass. Use Docker Engine 28 or newer with default bridge routing for loopback publications. Keep the native profile available while host prerequisites are pending. Local apps and dashboards use loopback or a Kubernetes port-forward.

Declare workload state in Compose and Helm and use Git review and an Argo CD reconciliation path for controlled environment changes. Store lab secrets outside Git. Use disposable public GitHub-hosted runners for independent integration checks with synthetic data.

## Alternatives and consequences

Docker Desktop is an alternative for installations that satisfy its personal-use terms. Docker Engine avoids requiring Desktop for this lab. OpenTofu can manage provider-backed resources with plan and state, but this one-host lab currently has no separate infrastructure provider or long-lived infrastructure lifecycle for it to own. Adding OpenTofu state would duplicate the Compose, Helm and GitOps responsibilities. Re-evaluate when the project has multiple independently managed hosts, networks or persistent infrastructure. [Docker Desktop license](https://docs.docker.com/subscription/desktop-license/) · [OpenTofu overview](https://opentofu.org/docs/intro/)
