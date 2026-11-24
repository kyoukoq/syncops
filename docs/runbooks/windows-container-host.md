# Windows container lab activation

The native SQLite profile runs independently. This runbook activates the Linux container path on a dedicated Ubuntu environment. It requires administrative Windows approval and a restart.

## Activate WSL2

Run this from an elevated PowerShell window and restart Windows when it completes.

```powershell
wsl --install -d Ubuntu-24.04
```

Launch Ubuntu once and initialize the local Linux account. Verify that `wsl --list --verbose` reports Ubuntu as version 2. Confirm the distribution has systemd and use a repository checkout inside the Ubuntu filesystem for container build and database durability checks. [Microsoft WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install)

## Enable the container runtime

Install Docker Engine and the Compose plugin from Docker's official Ubuntu repository in the dedicated Ubuntu installation. Follow the rootless prerequisites and setup in that installation when supported, and verify the selected Docker context. Keep the Docker API local. Docker Desktop for personal use is an alternative when its license terms and host prerequisites are satisfied. [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/) · [Docker rootless setup](https://docs.docker.com/engine/security/rootless/) · [kind rootless prerequisites](https://kind.sigs.k8s.io/docs/user/rootless/)

```bash
docker version
docker compose version
docker info
```

Use Docker Engine 28 or later and start the core profile using locally generated credentials. Check the Compose health state and use `scripts/smoke.py` with those credentials. Restart the Compose project and repeat the smoke check with the same PostgreSQL volume. Confirm the event history is present before enabling the metrics and central log overlays. Use a separate disposable project for forced failures or data loss.

Open only the loopback application and dashboard addresses. Keep the Docker socket private and do not add users to the root-equivalent Docker group solely for this lab. In rootless setups, verify that the daemon can reach the loopback syslog port before treating the local logs overlay as verified.
