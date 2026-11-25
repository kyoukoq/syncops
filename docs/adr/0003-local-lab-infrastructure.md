# ADR 0003. WSL2 and declarative local lab

**Status** — Accepted for the Advanced DevOps Lab. The WSL2 and rootless Docker foundation is verified locally.

## Context

SyncOps must retain its Windows SQLite profile and provide an isolated Linux container and Kubernetes lab on one workstation. The verified workstation runs Ubuntu 24.04.5 under WSL2 with systemd as PID 1. WSL reported 12 CPUs and 15 GiB of memory. The Linux checkout and its credentials have separate storage from the Windows SQLite profile.

## Decision

Use Ubuntu 24.04 on WSL2 with Docker Engine and its Compose plugin. Use the rootless user service and a local Unix socket. Docker Engine 29.10.1 and Compose 5.8.0 passed local checks with cgroup v2 and systemd delegation. System services for the rootful daemon remain disabled, and the rootless daemon starts on demand. Local apps and dashboards use loopback or a Kubernetes port-forward.

Declare workload state in Compose and Helm and use Git review and an Argo CD reconciliation path for controlled environment changes. Store lab secrets outside Git. Use disposable public GitHub-hosted runners for independent integration checks with synthetic data.

## Alternatives and consequences

Docker Desktop is an alternative for installations that satisfy its personal-use terms. Docker Engine avoids requiring Desktop for this lab. OpenTofu can manage provider-backed resources with plan and state, but this one-host lab currently has no separate infrastructure provider or long-lived infrastructure lifecycle for it to own. Adding OpenTofu state would duplicate the Compose, Helm and GitOps responsibilities. Re-evaluate when the project has multiple independently managed hosts, networks or persistent infrastructure. [Docker Desktop license](https://docs.docker.com/subscription/desktop-license/) · [OpenTofu overview](https://opentofu.org/docs/intro/)
