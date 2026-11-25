# ADR 0004. Supported Alpine backend runtime

**Status** — Accepted for candidate validation. Stable release requires evidence for the published digests.

## Context

The Debian 13.8 backend candidate contained 87 installed OS packages. Trivy 0.76.2 reported 53 HIGH Debian package rows across 13 CVEs without a stable package fix. The candidate used a supported Python release and ran as an unprivileged user. The goal was to reduce the actual runtime footprint while keeping the existing APIs, Python imports and workload constraints.

## Decision

Use the official CPython 3.12.16 image on Alpine 3.24, pinned by its OCI index digest. Preserve the two-stage Dockerfile, application requirements and numeric runtime UID and GID. Use pip in the dependency stage and exclude installed pip tools from the final image. Apply stable Alpine package updates during the runtime build.

Verify Linux amd64 application and PostgreSQL behavior through the actual Compose, worker recovery, Helm and Argo CD entry points. Compare Trivy scans using the same vulnerability database. Keep native Windows interpreter selection independent.

## Alternatives and consequences

Continuing with the Debian image would preserve glibc compatibility and depend on stable security backports. Alpine reduces the package inventory and uses musl, so native Python wheels and platform compatibility must be exercised when dependencies change. The runtime still contains the system SQLite library and libraries bundled by the Psycopg wheel. Track those components separately from the package scan. [Risk register](../security-risk-register.md) · [Official Python image variants](https://github.com/docker-library/docs/tree/master/python)
