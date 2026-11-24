# Kubernetes lab

The SyncOps Helm chart runs the console, API, simulator, workers, migration job and a single PostgreSQL instance. The database uses a StatefulSet and a dedicated PersistentVolumeClaim. The API, worker and simulator wait for the database to reach the Alembic revision shipped in their image. Images run as non-root users with read-only root filesystems, bounded temporary storage and resource requests and limits.

## Prerequisites

- Docker Engine on a Linux host with cgroup v2, or an eligible personal Docker Desktop installation with Linux containers. Use [Docker Desktop's personal-use terms](https://docs.docker.com/subscription/desktop-license/) when choosing the Windows runtime.
- [kind v0.31.0](https://github.com/kubernetes-sigs/kind/releases/tag/v0.31.0), [kubectl v1.35.0](https://kubernetes.io/docs/tasks/tools/), [Helm v4.3.1](https://github.com/helm/helm/releases/tag/v4.3.1), and PowerShell 7.4 or later. Use an image builder with Docker's build-context support.
- The public base images must be available for the first build. [Docker Hub's anonymous pull limits](https://docs.docker.com/docker-hub/usage/) apply. The lab builds and loads its application images locally.

## Create the cluster and install staging

Run from the repository root on a host with the prerequisites.

```powershell
$nodeImage = 'kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f'
kind create cluster --name syncops --image $nodeImage --wait 180s
$context = 'kind-syncops'
$namespace = 'syncops-staging'

docker build --tag syncops/backend:local --file deploy/backend.Dockerfile backend
docker build --build-context config=deploy --tag syncops/frontend:local --file deploy/frontend.Dockerfile frontend
docker pull postgres:17-bookworm
kind load docker-image --name syncops syncops/backend:local syncops/frontend:local postgres:17-bookworm

kubectl --context $context create namespace $namespace
kubectl --context $context label namespace $namespace pod-security.kubernetes.io/enforce=restricted
./deploy/kubernetes/Initialize-Secrets.ps1 -Context $context -Namespace $namespace
helm upgrade --install syncops charts/syncops --kube-context $context --namespace $namespace --wait --wait-for-jobs --timeout 5m
kubectl --context $context --namespace $namespace get pods,job,pvc,svc
kubectl --context $context --namespace $namespace port-forward --address 127.0.0.1 svc/syncops-web 8080:8080
```

Open `http://127.0.0.1:8080` and sign in as `admin` with the generated `admin-password` from the namespace's `syncops-api-auth` Secret. In a second terminal, the repository's smoke test reads it through an environment variable.

```powershell
$encoded = kubectl --context kind-syncops --namespace syncops-staging get secret syncops-api-auth -o 'jsonpath={.data.admin-password}'
$env:SYNCOPS_ADMIN_PASSWORD = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded))
try { python scripts/smoke.py } finally { Remove-Item Env:SYNCOPS_ADMIN_PASSWORD }
```

To create the production lab, repeat the namespace, secret and release steps with `syncops-production-lab` on the same cluster. Use another local port, such as `8081:8080`. Each namespace gets its own database, PVC, account bootstrap and simulator token. This profile shares the single kind node and its storage backend.

## Deployment configuration

- **Credentials.** The initializer preserves existing Secrets and sends newly generated hexadecimal values to Kubernetes over stdin. The chart refers to four Secrets prefixed with the release name. Set `api.optionalCredentials.operator`, `api.optionalCredentials.viewer` or `api.optionalCredentials.webhook` to enable the corresponding generated values. API passwords initialize missing users. Password rotation for existing users and PostgreSQL roles requires updating those accounts before replacing their Secrets.
- **Network access.** The default exposes ClusterIP services and a headless database service. The loopback port-forward targets the web console, which proxies the same-origin API. The API, simulator and database receive scoped ingress NetworkPolicies when `networkPolicy.enabled` is true. Verify enforcement with a policy-capable CNI before relying on it. Use the lab only on a trusted, dedicated cluster. Set `ingress.enabled`, `ingress.className`, `ingress.host` and `ingress.tlsSecretName` to expose HTTPS through an installed controller and an existing TLS Secret. The ingress controller and policy enforcement require verification in the target cluster.
- **Storage.** Use the default dynamic StorageClass or set `database.storageClassName` and `database.storageSize` before creating the release. The PVC is retained on normal StatefulSet removal. Deleting the namespace or kind cluster can remove access to its data. Back up PostgreSQL before removing lab storage or applying a schema change.
- **Upgrades.** Give every app release a new immutable tag or digest in `images.backend.reference` and `images.frontend.reference`. Load those images into kind before upgrading. Increase the chart version when changing migration job behavior. Backward-compatible database migrations support staged rollouts. A Helm rollback restores the workload manifest and leaves the database revision in place. Use the database recovery procedure for changes that need a schema rollback.
- **Worker probes.** The current worker readiness command reports the freshest database heartbeat across the worker pool. The Kubernetes lab check independently counts recent heartbeats to confirm distinct live workers. Kubernetes restarts exited containers and allows workers 45 seconds to finish on termination.

## Verify deployment and recovery

The [Kubernetes lab workflow](../../.github/workflows/kubernetes.yml) runs on standard GitHub-hosted runners for this public repository. It lints the chart, checks Kubernetes admission, builds local images, and executes [the kind acceptance script](verify-kind.sh). The script verifies the initial two workers, scales to three, sends a real event through the console proxy, replaces the staging database pod and checks the original PVC, event, attempt and mock effect. It tests failed frontend image rollout and automatic Helm rollback in staging, then installs and verifies independent credentials, storage and delivery in the production lab. Check the workflow run for execution evidence. [GitHub Actions public runner billing](https://docs.github.com/en/actions/concepts/billing-and-usage)

For diagnosis, inspect `kubectl get pods,job,pvc` and `kubectl get events` scoped to the environment. Check job and init-container logs when apps wait for the schema. Check that local image references exist in the selected kind node when pods report `ErrImageNeverPull`. If the ingress option is enabled, verify its hostname, TLS Secret and controller separately.
