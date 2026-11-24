#!/usr/bin/env bash
set -euo pipefail

context=kind-syncops-ci
namespace=syncops-staging
forward_pid=
forward_log=

kube() {
    kubectl --context "$context" --namespace "$namespace" "$@"
}

chart() {
    helm --kube-context "$context" --namespace "$namespace" "$@"
}

database() {
    kube exec statefulset/syncops-db -- sh -ec \
        'PGPASSWORD="$POSTGRES_PASSWORD" exec psql -XAt -h 127.0.0.1 -U postgres -d syncops -v ON_ERROR_STOP=1 -c "$1"' \
        syncops-ci "$1"
}

close_forward() {
    if [[ -n "$forward_pid" ]]; then
        kill "$forward_pid" 2>/dev/null || true
        wait "$forward_pid" 2>/dev/null || true
        forward_pid=
    fi
    if [[ -n "$forward_log" ]]; then
        rm -f -- "$forward_log"
        forward_log=
    fi
}
trap close_forward EXIT

smoke() {
    local password port base_url
    password=$(kube get secret syncops-api-auth -o 'jsonpath={.data.admin-password}' | base64 -d)
    echo "::add-mask::$password"
    forward_log=$(mktemp)
    kubectl --context "$context" --namespace "$namespace" port-forward \
        --address 127.0.0.1 svc/syncops-web :8080 >"$forward_log" 2>&1 &
    forward_pid=$!
    for _ in {1..30}; do
        port=$(sed -nE 's/^Forwarding from 127[.]0[.]0[.]1:([0-9]+) -> .*/\1/p' "$forward_log")
        if [[ "$port" =~ ^[0-9]+$ ]]; then
            break
        fi
        if ! kill -0 "$forward_pid" 2>/dev/null; then
            cat "$forward_log" >&2
            return 1
        fi
        sleep 1
    done
    [[ "$port" =~ ^[0-9]+$ ]]
    base_url="http://127.0.0.1:$port"
    curl --noproxy '*' --retry 15 --retry-delay 1 --retry-connrefused -fsS \
        --max-time 2 "$base_url/healthz"
    SYNCOPS_ADMIN_PASSWORD="$password" python3 scripts/smoke.py --base-url "$base_url"
    close_forward
}

verify_workers() {
    local expected="$1"
    local replicas
    kube rollout status deployment/syncops-worker --timeout=120s
    replicas=$(kube get deploy syncops-worker -o 'jsonpath={.status.readyReplicas}')
    [[ "$replicas" == "$expected" ]]
    for _ in {1..15}; do
        if [[ $(database 'SELECT count(*) FROM worker_heartbeats WHERE updated_at > extract(epoch FROM clock_timestamp()) - 15;') == "$expected" ]]; then
            echo "$expected worker replicas are ready with distinct fresh heartbeats"
            return
        fi
        sleep 2
    done
    echo "Expected $expected fresh worker heartbeats" >&2
    return 1
}

install_release() {
    chart upgrade --install syncops charts/syncops --wait --wait-for-jobs --timeout 5m
    kube wait --for=condition=complete job -l 'app.kubernetes.io/component=migrate' --timeout=30s
}

install_release
verify_workers 2
smoke

chart upgrade syncops charts/syncops --set worker.replicas=3 --wait --wait-for-jobs --timeout 3m
verify_workers 3

signature_sql="SELECT concat_ws(':',
    (SELECT string_agg(id, ',' ORDER BY id) FROM events WHERE status = 'succeeded'),
    (SELECT count(*) FROM attempts WHERE status = 'succeeded'),
    (SELECT count(*) FROM mock_operations));"
signature=$(database "$signature_sql")
[[ "$signature" =~ ^[a-f0-9-]+:1:1$ ]]
pod_uid=$(kube get pod syncops-db-0 -o 'jsonpath={.metadata.uid}')
pvc_uid=$(kube get pvc data-syncops-db-0 -o 'jsonpath={.metadata.uid}')

kube rollout restart statefulset/syncops-db
kube rollout status statefulset/syncops-db --timeout=180s
[[ $(kube get pod syncops-db-0 -o 'jsonpath={.metadata.uid}') != "$pod_uid" ]]
[[ $(kube get pvc data-syncops-db-0 -o 'jsonpath={.metadata.uid}') == "$pvc_uid" ]]
[[ $(database "$signature_sql") == "$signature" ]]
echo 'PostgreSQL pod replacement retained the same PVC, delivered event, attempt and mock effect'
verify_workers 3

if chart upgrade syncops charts/syncops --reuse-values \
    --set images.frontend.reference=syncops/frontend:unavailable-drill \
    --rollback-on-failure --wait --wait-for-jobs --timeout 45s; then
    echo 'The deliberately unavailable frontend unexpectedly deployed' >&2
    exit 1
fi
chart history syncops -o json | python3 -c '
import json
import sys

history = json.load(sys.stdin)
assert history[-2]["status"] == "failed", history
assert history[-1]["status"] == "deployed", history
'
kube rollout status deployment/syncops-web --timeout=120s
[[ $(kube get deploy syncops-web -o 'jsonpath={.spec.template.spec.containers[0].image}') == syncops/frontend:local ]]
[[ $(database "$signature_sql") == "$signature" ]]
smoke

staging_secret_uid=$(kube get secret syncops-api-auth -o 'jsonpath={.metadata.uid}')
staging_password_hash=$(kube get secret syncops-api-auth -o 'jsonpath={.data.admin-password}' | sha256sum)
namespace=syncops-production-lab
install_release
[[ $(kube get secret syncops-api-auth -o 'jsonpath={.metadata.uid}') != "$staging_secret_uid" ]]
[[ $(kube get secret syncops-api-auth -o 'jsonpath={.data.admin-password}' | sha256sum) != "$staging_password_hash" ]]
[[ $(kube get pvc data-syncops-db-0 -o 'jsonpath={.metadata.uid}') != "$pvc_uid" ]]
[[ $(database 'SELECT count(*) FROM events;') == 0 ]]
smoke
[[ $(database 'SELECT count(*) FROM mock_operations;') == 1 ]]
echo 'Production lab used separate credentials and storage and delivered its own event'
