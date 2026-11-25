# v0.2.0 security risk register

Reviewed on 2026-11-25. Review again before publishing the stable release, upon a relevant upstream security update, and by 2026-12-02 if the release remains pending. This assessment covers an amd64 lab deployment with synthetic data, trusted workstation users, and loopback-only service access. Short-lived GitHub-hosted CI runs and image publication are separate from local runtime acceptance.

Stable release requires an exact release-candidate scan, remediation and retesting of material findings with supported fixes, and explicit Product Owner acceptance of the remaining material risks. Record the accepted risks, exact image digests, applicable lab boundaries, decision date, and next review in the release decision. Approval is pending.

## Evidence

Fresh Trivy 0.76.2 scans ran locally in Ubuntu WSL2 against the public `linux/amd64` candidate digests with remote OCI access. The vulnerability DB was updated at `2026-11-25T07:11:44Z`. Both OCI configurations identify source revision `305e2b90398a76a43b4790c13bfb896994c885d1`.

| Candidate image | Base and configured user | HIGH rows | Distinct CVEs | CRITICAL rows | Rows with a fix |
| --- | --- | ---: | ---: | ---: | ---: |
| `backend@sha256:a8bd16b80fbd467507ceb0dc27756a802bb2c889dfd020ce3a0bd792c71acbe2` | Debian 13.8, CPython 3.12.16, `10001:10001` | 53 | 13 | 0 | 0 |
| `frontend@sha256:490f35455de5d2e6aac7259cf2dfe061381c3e0b39f6052e313bae529ac80cb0` | Alpine 3.24.4, `101:101` | 0 | 0 | 0 | 0 |

Trivy found all 53 backend rows in the Debian OS inventory. The same scan found zero HIGH or CRITICAL rows in the backend's Python package inventory. The table below covers each CVE in both the historical and fresh reports. CycloneDX 1.7 conversion of the fresh inventories produced 113 backend components and 73 frontend components.

The raw local reports in the ignored `.syncops/release-security/` directory had SHA-256 hashes `2aa337b48db14d6c0ae2ed66c2ce36d7898b555dd7fafea124f379a8c7290f5b` for the backend and `a4f652e4803885d99a52691894a8a39cca677efaf4cb00124a3b1d64db4ca1cb` for the frontend.

The fresh dependency and secret checks below ran against the engineering checkout at `f0e4acab0d1d4ef22d2369b673fb13736c40915d` on 2026-11-25.

| Gate | Observed result |
| --- | --- |
| Gitleaks v8.30.1 full local Git history | Passed. The command scanned 23 commits across the local Git refs. No leaks reported. |
| Gitleaks v8.30.1 tracked snapshot | Passed. Scanned the safe `git archive HEAD` snapshot. No leaks reported. |
| pip-audit 2.10.0 for `backend/requirements.txt` | Passed. 21 resolved requirements and zero reported vulnerabilities. |
| npm audit 11.12.1 from `frontend/` | Passed. 123 resolved lockfile dependencies, including development dependencies, and zero reported vulnerabilities. |

Historical [Container assurance run 45511484050](https://github.com/kyoukoq/syncops/actions/runs/45511484050) recorded 53 HIGH rows, zero CRITICAL rows and zero rows with a fix for the backend, and no HIGH or CRITICAL rows for the frontend. The 53 rows describe 13 distinct CVEs. Trivy matches Debian binary packages to source security records. One CVE can appear on several installed packages built from the same source. Four `util-linux` CVEs account for 36 of those rows. [Trivy vulnerability scanner](https://trivy.dev/docs/latest/scanner/vulnerability/)

[Candidate assurance run 45512578781](https://github.com/kyoukoq/syncops/actions/runs/45512578781) published the candidate references below and generated GitHub provenance and CycloneDX attestations. Provenance binds a build to an artifact digest and an identified build workflow. SBOMs describe inventoried components. GitHub CLI 2.105.0 verified both predicate types for each candidate digest against the publication workflow identity at refs/heads/main. Repeat verification on the release digests. See [supply-chain verification](supply-chain.md).

## Backend vulnerability assessment

Severity is the HIGH rating emitted by both Trivy scans. Advisory severity and the risk of reaching the affected code in SyncOps can differ. The version column lists the installed binaries on the candidate. Debian stable is `trixie` for these images.

| CVE and affected source | Binary packages and installed versions | Supported fix status and applicability | Mitigation and follow-up |
| --- | --- | --- | --- |
| [CVE-2025-69720](https://security-tracker.debian.org/tracker/CVE-2025-69720), ncurses | `libncursesw6`, `libtinfo6`, `ncurses-base`, `ncurses-bin` at `6.5+20250216-2` | A crafted terminal definition consumed by `infocmp` can cause a stack overflow. Debian lists the fix in testing/unstable (`6.6+20260608-2`). The tracker lists trixie as vulnerable. | The app entry points avoid terminal tooling and foreign terminfo data. Leave interactive shells and untrusted terminal data outside the runtime, assess safe package removal, and track a stable fix. |
| [CVE-2026-107494](https://security-tracker.debian.org/tracker/CVE-2026-107494), [CVE-2026-124709](https://security-tracker.debian.org/tracker/CVE-2026-124709), OpenSSL | `libssl3t64`, `openssl`, `openssl-provider-legacy` at `3.5.9-1~deb13u1` | A QUIC peer can cause unbounded memory growth. The deployed network paths use conventional HTTP over TCP. An OpenSSL dependency remains in Python and needs ongoing patching. Debian lists trixie as vulnerable. Upstream scheduled releases containing the fixes for 2026-12-01. [OpenSSL November 17 advisory](https://openssl-library.org/news/secadv/20261117.txt) · [November 24 advisory](https://openssl-library.org/news/secadv/20261124.txt) | Keep QUIC and HTTP/3 disabled for this profile. Restrict network peers and preserve resource limits. Rebuild when Debian publishes the backport. |
| [CVE-2026-119373](https://security-tracker.debian.org/tracker/CVE-2026-119373), [CVE-2026-119374](https://security-tracker.debian.org/tracker/CVE-2026-119374), [CVE-2026-119379](https://security-tracker.debian.org/tracker/CVE-2026-119379), SQLite | `libsqlite3-0` at `3.46.1-7+deb13u2` | FTS5 query/index handling and the session changeset path are affected. Debian lists the fix in testing/unstable (`3.54.1-2`) and trixie as vulnerable. The Compose and Helm profiles use PostgreSQL. | Application migrations and request handlers avoid FTS5 tables, raw SQL from clients, and changeset or database uploads. Review the native Windows SQLite profile separately, and preserve the contained SQLite fallback until a patched runtime has passed its own acceptance. |
| [CVE-2026-16742](https://security-tracker.debian.org/tracker/CVE-2026-16742), systemd | `libsystemd0`, `libudev1` at `257.13-1~deb13u1` | The affected `systemd-homed` path requires a managed local user and service. Debian lists the fix in testing/unstable (`262.2-1`) and trixie as vulnerable. | Image entry points use Python or Nginx and the optional Compose init, with no homed service configured. Apply workstation and WSL updates independently of image rebuilds. |
| [CVE-2026-54369](https://security-tracker.debian.org/tracker/CVE-2026-54369), acl | `libacl1` at `2.3.2-2+b1` | A privileged ACL path operation involving attacker-controlled symlinks is the relevant precondition. Debian lists the fix in testing/unstable (`2.4.0-1`) and trixie as vulnerable. | App paths omit privileged ACL operations. Keep writable mounts narrow and enforce the non-root, no-capability container settings. Track the stable backport. |
| [CVE-2026-76642](https://security-tracker.debian.org/tracker/CVE-2026-76642), [CVE-2026-78408](https://security-tracker.debian.org/tracker/CVE-2026-78408), [CVE-2026-78409](https://security-tracker.debian.org/tracker/CVE-2026-78409), [CVE-2026-78410](https://security-tracker.debian.org/tracker/CVE-2026-78410), util-linux | `bsdutils` at `1:2.41.5-0+deb13u1`; `libblkid1`, `liblastlog2-2`, `libmount1`, `libsmartcols1`, `libuuid1`, `mount`, `util-linux` at `2.41.5-0+deb13u1`; `login` at `1:4.16.0-2+really2.41.5-0+deb13u1` | The affected paths involve privileged mounts, mount hooks or namespace/cgroup entry. Debian lists the fixes in testing/unstable (`2.42.4-1`) and trixie as vulnerable. | Preserve `CAP_SYS_ADMIN` removal and the privileged execution prohibition. Exclude host mounts, Docker sockets, privileged workloads, and host administration tools from application access. Track stable fixes and remove unneeded utilities if demonstrated safe. |
| [CVE-2026-9538](https://security-tracker.debian.org/tracker/CVE-2026-9538), Perl | `perl-base` at `5.40.1-6+deb13u1` | Archive::Tar before `3.10` can exhaust memory on crafted archive input. Debian lists the fix in testing/unstable (`5.44.0-3`) and trixie as vulnerable. | The API has no archive extraction route. Avoid extraction of untrusted archives elsewhere in the workflow and track a stable package update. |

## Lab controls and residual risks

- **Image and deployment controls.** The [backend](../deploy/backend.Dockerfile) and [frontend](../deploy/frontend.Dockerfile) images set non-root users. [Compose](../compose.yaml) and the [Helm security helpers](../charts/syncops/templates/_helpers.tpl) apply read-only application root filesystems, drop all capabilities, prevent privilege escalation, and bound resources. Helm disables workload service account token mounting and uses RuntimeDefault seccomp. Compose publishes the web interface on loopback and keeps DB, API, mock and worker on a private network. Helm has targeted ingress policies for API, mock and DB. Confirm policy enforcement and loopback binding in the actual local acceptance environment.
- **Request and credential controls.** The [API](../backend/syncops/api.py) and [auth module](../backend/syncops/auth.py) enforce authenticated roles and authenticated webhook intake. Passwords are salted and scrypt-hashed, session tokens are hashed in the database, and login work is concurrency-bounded. The [worker](../backend/syncops/worker.py) uses an operator-configured mock origin, with redirect and proxy-environment handling disabled. The [web proxy](../deploy/nginx.conf) uses a fixed upstream, body-size cap and security headers. Use distinct credentials per environment, keep them out of Git and diagnostic output, and limit host and cluster access to trusted operators.
- **R1, image CVEs without available stable fixes.** Applicability is assessed against configured entry points, privileges, mounts and peer access. Installed vulnerable code remains relevant when these boundaries change or another foothold exists. Keep loopback access and the synthetic-data scope. A Docker, NodePort, ingress, port-forward or QUIC exposure change reopens the assessment. Product Owner approval is required before stable publication of an affected digest.
- **R2, native SQLite.** The original Windows project venv reported CPython `3.12.14`, SQLite `3.53.1`, and `ENABLE_FTS5` enabled. Those SQLite advisories merit independent review even though SyncOps does not implement FTS5 or changeset handlers. Keep the database and all backups local, open only trusted project-owned SQLite files, and verify the native profile on a patched Python distribution after a compatible SQLite update. A separate SHA-verified [Astral Windows build](https://github.com/astral-sh/python-build-standalone/releases/tag/20261124) of CPython `3.12.16` reported SQLite `3.54.1` and passed all 15 backend regression tests with one existing TestClient deprecation warning. The test used isolated files and left the active profile intact. Plan the Windows runtime update before accepting the profile as patched. This also picks up [security changes in CPython 3.12.16](https://www.python.org/downloads/release/python-31216/).
- **R3, lab trust boundary.** The application DB role owns its database so that migration and runtime operations can share one identity. A compromise of a DB-connected workload can affect events and audit history. Loopback HTTP also assumes trusted local principals. Continue using local synthetic data, restrict access to Docker and Kubernetes administration, and treat application audit records as mutable database records. A public or multi-tenant deployment would require further credential, TLS, migration/runtime role, network and audit controls.
- **R4, scan and release scope.** The candidate scan covers the two project images at one architecture. The database, observability, Argo CD, Kubernetes node, and host operating-system packages have separate update and evidence requirements. [Container assurance](../.github/workflows/supply-chain.yml) pins action commits, disables checkout credential persistence, gives routine jobs read-only repository access, and scopes registry and attestation writes to the trusted publication job. Candidate publication provides pre-release evidence. Reassess the exact final source revision and rebuilt image digests before publishing, especially because base OS package upgrades resolve against the distribution repository at build time.

## Remediation and base-image decision

1. Refresh the official Python 3.12 slim trixie digest and rebuild when upstream support updates are available. Compare Trivy inventories and vendor advisory status before and after, including any bundled CPython, OpenSSL, SQLite, libpq and Python wheel updates. The current Dockerfile already applies Debian package upgrades to the runtime stage.
2. Prefer stable packages for this lab. The supported `python:3.12-slim-bookworm` variant avoids the two listed OpenSSL 3.5 QUIC issues through its OpenSSL 3.0 package line. A move changes the full Debian package and patch inventory, and needs a comparative scan and regression run. The smaller official Python 3.12 Alpine variant is a second option. A binary-only `pip download` for CPython 3.12 amd64 with both `musllinux_1_1` and `musllinux_1_2` resolved 24 wheels, including psycopg-binary, pydantic-core and greenlet. That confirms package availability. Runtime compatibility and security posture need a container build, image scan and tests for scrypt logins, migration, PostgreSQL/SQLite startup, webhooks, worker delivery, and crash/retry recovery. Retain the existing `slim-trixie` image for this candidate while testing any migration separately and tracking Debian stable fixes. [Docker Official Python image variants](https://github.com/docker-library/docs/tree/master/python)
3. Review removable packages using the actual runtime inventory and dependency graph. A smaller runtime is useful only if it retains needed tools, reference libraries and security updates. Rebuild and rerun tests and scans after any package removal. This review kept the published image and its scanner policy intact.

## Reproduce the checks

Run the remote image check from an isolated report directory on Linux with [Trivy v0.76.2](https://github.com/aquasecurity/trivy/releases/tag/v0.76.2). The Linux amd64 archive checksum in [container assurance](../scripts/container-assurance.sh) is used to verify the tool. These scans read the public GHCR digests and need no Docker daemon.

```bash
trivy image --download-db-only --cache-dir cache
for image in backend@sha256:a8bd16b80fbd467507ceb0dc27756a802bb2c889dfd020ce3a0bd792c71acbe2 \
  frontend@sha256:490f35455de5d2e6aac7259cf2dfe061381c3e0b39f6052e313bae529ac80cb0; do
  component="${image%@*}"
  trivy image --cache-dir cache --image-src remote --platform linux/amd64 \
    --scanners vuln --severity HIGH,CRITICAL --list-all-pkgs --format json \
    --output "$component-candidate.json" --no-progress --timeout 8m \
    "ghcr.io/kyoukoq/syncops/$image"
done
```

To verify the attestations, use GitHub CLI and restrict the signing identity to the project's publication workflow. Use the predicate type for the provenance and SBOM records, respectively. The independent review used `--bundle` with both public attestations downloaded and decoded from the [GitHub REST endpoint](https://docs.github.com/en/rest/repos/attestations#list-attestations).

```bash
gh attestation verify "oci://ghcr.io/kyoukoq/syncops/$image" \
  --repo kyoukoq/syncops \
  --signer-workflow kyoukoq/syncops/.github/workflows/supply-chain.yml \
  --predicate-type https://slsa.dev/provenance/v1
gh attestation verify "oci://ghcr.io/kyoukoq/syncops/$image" \
  --repo kyoukoq/syncops \
  --signer-workflow kyoukoq/syncops/.github/workflows/supply-chain.yml \
  --predicate-type https://cyclonedx.org/bom
```

Set `image` to one of the digest references in the scan loop before running these commands.

Run the repository checks from the project root. The tracked snapshot used for the second Gitleaks check should be a private directory created with `git archive HEAD`.

```bash
gitleaks git . --log-opts=--all --redact=100 --no-banner --no-color
gitleaks dir "$tracked_snapshot" --redact=100 --no-banner --no-color
python -m pip_audit --progress-spinner off --requirement backend/requirements.txt
npm --prefix frontend audit
```
