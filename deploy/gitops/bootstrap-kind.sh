#!/usr/bin/env bash
set -euo pipefail

cluster="${1:?Pass an unused kind cluster name}"
registry="syncops-registry-$cluster"
context="kind-$cluster"
node_image=kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f
argocd_manifest=https://raw.githubusercontent.com/argoproj/argo-cd/v3.6.3/manifests/core-install.yaml
registry_path=/etc/containerd/certs.d/localhost:5001

kind create cluster --name "$cluster" --image "$node_image" --wait 180s
docker run -d --name "$registry" --network kind -p 127.0.0.1:5001:5000 registry:3
for node in $(kind get nodes --name "$cluster"); do
    docker exec "$node" mkdir -p "$registry_path"
    printf '[host."http://%s:5000"]\n  capabilities = ["pull", "resolve"]\n' "$registry" \
        | docker exec -i "$node" sh -ec 'cat > "$1/hosts.toml"' sh "$registry_path"
done
curl --noproxy '*' --retry 15 --retry-connrefused --retry-delay 1 -fsS --max-time 2 http://127.0.0.1:5001/v2/

kubectl --context "$context" create namespace argocd
kubectl --context "$context" -n argocd apply --server-side -f "$argocd_manifest"
kubectl --context "$context" wait --for=condition=Established crd/applications.argoproj.io crd/appprojects.argoproj.io --timeout=90s
kubectl --context "$context" -n argocd rollout status deployment/argocd-repo-server --timeout=180s
kubectl --context "$context" -n argocd rollout status statefulset/argocd-application-controller --timeout=180s

for namespace in syncops-staging syncops-production-lab; do
    kubectl --context "$context" create namespace "$namespace"
    kubectl --context "$context" label namespace "$namespace" pod-security.kubernetes.io/enforce=restricted
    pwsh -NoProfile -File deploy/kubernetes/Initialize-Secrets.ps1 -Context "$context" -Namespace "$namespace" -Release "$namespace"
done
