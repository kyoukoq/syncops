# SyncOps GitOps lab

Argo CD Core reconciles the Helm chart into `syncops-staging` and `syncops-production-lab`. Each [Application and AppProject](apps.yaml) allows a single source repository, destination namespace and set of namespaced resource kinds. The operator creates database and application credentials separately with the Kubernetes lab's secret initializer. Application Pods stay in restricted namespaces. Argo CD Core has cluster-wide controller privileges and belongs on a dedicated lab cluster. [Argo CD installation guide](https://argo-cd.readthedocs.io/en/stable/operator-manual/installation/)

Each environment tracks its own Git branch. A release commit includes the chart and the OCI manifest digests for the backend and frontend. Argo CD renders the chart from that commit, detects cluster drift and restores the committed state. The production-lab branch advances through an explicitly reviewed Git merge after staging deployment and smoke checks. [Argo CD automated sync](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/)

## Start a local cluster

Use a dedicated Docker host with Bash, Docker plus BuildKit, Python 3, `curl`, Git, PowerShell 7.4, [kind v0.31.0](https://github.com/kubernetes-sigs/kind/releases/tag/v0.31.0) and `kubectl` v1.35.0. The procedure creates a kind cluster with a loopback-only local registry and installs the version-pinned Argo CD Core distribution. The base image pulls use public registries within their limits. [kind local registry](https://kind.sigs.k8s.io/docs/user/local-registry/) · [Docker terms and limits](https://docs.docker.com/docker-hub/usage/)

Start with a clean checkout. If using a fork, set the exact public HTTPS clone URL for both `repoURL` and `sourceRepos` in `apps.yaml` and use the fork as `origin`.

```bash
bash deploy/gitops/bootstrap-kind.sh syncops-gitops
context=kind-syncops-gitops
registry=localhost:5001/syncops

docker build -t "$registry/backend:baseline" -f deploy/backend.Dockerfile backend
docker build --build-context config=deploy -t "$registry/frontend:baseline" -f deploy/frontend.Dockerfile frontend
docker push "$registry/backend:baseline"
docker push "$registry/frontend:baseline"
backend=$(docker image inspect --format '{{index .RepoDigests 0}}' "$registry/backend:baseline")
frontend=$(docker image inspect --format '{{index .RepoDigests 0}}' "$registry/frontend:baseline")

git switch -c syncops-lab-staging
python3 deploy/gitops/release.py write-values --backend "$backend" --frontend "$frontend"
git add deploy/gitops/release-values.json
git commit -m 'deploy: select the baseline release for the SyncOps lab'
git branch syncops-lab-production
git push origin syncops-lab-staging syncops-lab-production
kubectl --context "$context" apply -f deploy/gitops/apps.yaml
kubectl --context "$context" -n argocd get applications
```

The cluster's containerd resolves the loopback registry reference using its private Docker network. A registry manifest digest identifies the image to pull. Branches contain image references and deployment configuration. Database passwords and simulator tokens remain namespaced Secrets and must stay outside source control.

## Promote a staging revision

Build and push the candidate images to the local registry with new tags, capture their full digest references, and run `release.py write-values` on `syncops-lab-staging`. Commit and push the staging change. Verify the candidate after Argo CD reconciles it. Run the delivery smoke described in the [Kubernetes lab](../kubernetes/README.md) using `syncops-staging-web` and `syncops-staging-api-auth`.

```bash
candidate=$(git rev-parse syncops-lab-staging)
python3 deploy/gitops/release.py verify --context kind-syncops-gitops --environment staging --revision "$candidate"

git switch syncops-lab-production
git merge --no-ff "$candidate" -m 'deploy: promote the verified SyncOps stage to the production lab'
test "$(git rev-parse HEAD^{tree})" = "$(git rev-parse "$candidate^{tree}")"
git push origin syncops-lab-production
python3 deploy/gitops/release.py verify --context kind-syncops-gitops --environment production-lab --revision "$(git rev-parse HEAD)"
```

Wait for the Application to reach `Synced` and `Healthy` at the new revision before rerunning `verify`. The gate checks that the reconciled commit matches the expected SHA and that every Deployment has rolled out the digest declared at that commit. If the merge-tree check fails, review the divergent production branch before pushing. Keep repository write permissions and merge review as the control point for production-lab promotion.

## Recover through Git

Revert the failed staging commit on `syncops-lab-staging` and push the revert. The dedicated controller has a 150-second sync timeout so a stuck rollout can finish failing before the revert reconciles. For a production-lab promotion merge, run `git revert -m 1 <promotion-merge-sha>` on `syncops-lab-production`, push, and verify the new revert commit with `release.py verify`. Run a fresh synthetic delivery smoke on the recovered environment. Git reverts restore desired workload configuration. Plan backwards-compatible migrations or take a database backup before schema changes.

## Verification

The [GitOps lab workflow](../../.github/workflows/gitops.yml) runs on standard GitHub-hosted runners in this public repository. It uses a disposable Git HTTP fixture and a loopback-bound registry, with read-only GitHub permissions. [GitHub Actions billing](https://docs.github.com/en/actions/concepts/billing-and-usage)

Its acceptance script checks independent staging and production-lab reconciliation, drift correction, a successful digest-pinned promotion, rejection of an unhealthy staging image, staging recovery and production rollback through Git reverts. Both environments exercise real SyncOps delivery. See the workflow run for execution evidence.
