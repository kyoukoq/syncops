# Local SyncOps operations

Use the native Windows profile for lightweight SQLite operation, or run the PostgreSQL profiles from a dedicated clone inside Ubuntu WSL2. Each checkout has its own data and locally generated credentials. The launcher works without elevation and preserves volumes, existing credentials and the Windows checkout.

## Native Windows

From the Windows checkout in PowerShell 7.4 or later, run the start command in a foreground terminal. The first run prepares the Python 3.12 environment and installs the locked frontend dependencies. Use `-SkipInstall` on subsequent runs when dependencies are unchanged.

```powershell
Set-Location "$([Environment]::GetFolderPath('MyDocuments'))/SyncOps"
./scripts/SyncOps-Lab.ps1 start
```

Use a second PowerShell terminal in the same checkout for operator commands.

```powershell
./scripts/SyncOps-Lab.ps1 status
./scripts/SyncOps-Lab.ps1 urls
./scripts/SyncOps-Lab.ps1 diagnose
./scripts/SyncOps-Lab.ps1 demo
./scripts/SyncOps-Lab.ps1 backup
./scripts/SyncOps-Lab.ps1 restore-drill -Archive .syncops/backups/<snapshot>.sqlite
```

The native launcher uses loopback ports 5173 for the console, 8000 for the API and 8001 for the simulator. The `urls` command verifies availability while the launcher holds its checkout lock. Retrieve credentials privately from `.syncops/credentials.json`. Copy a backup to a protected location before relying on it for recovery. The restore drill uses an existing snapshot to produce and integrity-check a separate file. It leaves the active SQLite database intact.

Press **Ctrl+C** in the start terminal to stop the services started by that launcher. The `stop` command reports which action is needed. Start again after a Windows reboot with `./scripts/SyncOps-Lab.ps1 start -SkipInstall` when the installed dependencies match the checkout.

## Ubuntu WSL2 and Docker Compose

From PowerShell, open `wsl -d Ubuntu-24.04`. Inside Ubuntu use the dedicated Linux checkout, such as `~/SyncOps`. For a new checkout, clone the repository into the Linux home filesystem. Select the local Docker context created for that Ubuntu environment. For the rootless installation, start the user daemon and select its context if needed.

```bash
systemctl --user start docker
docker context use rootless
cd ~/SyncOps
bash scripts/syncops.sh start compose
bash scripts/syncops.sh urls compose
```

Choose `start observability` for Prometheus, Grafana and Alertmanager, or `start logs` to also collect worker logs with Alloy and Loki. Each starts the required application services. After stopping one profile, use the desired profile's start command to switch. The application uses port 8080 by default. Prometheus, Grafana and Alertmanager use ports 9090, 3000 and 9093. The launcher prints each URL as verified after a successful health probe against an actual loopback binding. Open the verified URLs from the Windows browser and confirm Windows-to-WSL loopback access there.

The Linux launcher generates mode-0600 settings if needed and retains existing settings. Retrieve the admin, operator, viewer and Grafana passwords privately from the Linux `.env`. Keep the PostgreSQL, simulator, Loki and Kubernetes management ports private. Setting a shell variable does not override the launcher's Compose settings file. Use the same Linux checkout for the named `syncops` project.

```bash
bash scripts/syncops.sh status compose
bash scripts/syncops.sh diagnose logs
bash scripts/syncops.sh demo compose
bash scripts/syncops.sh backup compose
bash scripts/syncops.sh restore-drill compose
bash scripts/syncops.sh stop compose
```

The demo creates synthetic integrations and events through the API. The same request identities make reseeding safe. Use the [worker incident walkthrough](trace-worker-incident.md) to reproduce and inspect a fresh incident. The live database is preserved during seeding and stopping. The backup command writes a protected PostgreSQL archive with a readable catalog under `.syncops/backups/`. The restore drill runs with synthetic data, a new Compose project and a separate PostgreSQL volume. It measures restoration and records JSON evidence under `.syncops/backups/`. Follow the [recovery runbook](recovery.md) to investigate actual data loss and restore a user archive to an isolated target.

After Windows restarts, open Ubuntu, start the local Docker daemon if needed, return to this checkout and run the selected `start` command. The same Compose volumes keep database and observability data. The launcher adds no startup tasks.

## Local Kubernetes and GitOps

Install the versioned tools listed in the [Kubernetes lab guide](../../deploy/kubernetes/README.md) in Ubuntu and keep the daemon local. Stop Compose before working on the Kubernetes profile to reduce memory use. Rootless Docker requires cgroup v2 and delegation for kind. [kind rootless requirements](https://kind.sigs.k8s.io/docs/user/rootless/)

```bash
bash scripts/syncops.sh start kind
bash scripts/syncops.sh status kind
bash scripts/syncops.sh open kind staging
```

The launcher uses a private kubeconfig under `.syncops/`, a dedicated kind node and separate staging and production-lab Helm deployments. Keep `open` running in a foreground terminal, then run `bash scripts/syncops.sh urls kind staging` in a second terminal. Use `production-lab` instead of `staging` for the other namespace. Their console forwards use ports 18080 and 18081. Use the [Kubernetes lab guide](../../deploy/kubernetes/README.md) for private credential retrieval with the launcher's `.syncops/kind-local.yaml` kubeconfig and `kind-syncops-local` context.

Close a port-forward with **Ctrl+C**. Run `bash scripts/syncops.sh stop kind` to stop the owned node and retain its storage. Run `bash scripts/syncops.sh start kind` to resume it after a Windows restart. The node and its storage share one failure domain. Preserve important data with a database backup.

The acceptance commands create disposable clusters for the Kubernetes and Argo CD procedures used in CI. They exercise deliberate deployment failures and clean up their temporary infrastructure. Run them one at a time with the persistent cluster stopped. GitOps uses local registry port 5001 and a private Git fixture. It does not require a hosted Git repository, external credentials or public network listeners.

```bash
bash scripts/syncops.sh verify kind
bash scripts/syncops.sh verify gitops
```

See the [GitOps lab guide](../../deploy/gitops/README.md) for the drift, promotion and rollback assertions. Treat a nonzero acceptance exit as a failed check and use the command output for diagnosis. Review the evidence for each run before making release claims.
