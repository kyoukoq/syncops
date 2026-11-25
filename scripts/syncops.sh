#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
root=$(pwd -P)
state="$root/.syncops"
settings="$root/.env"
project=syncops
kind_name=syncops-local
kind_context="kind-$kind_name"
node_image=kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f

usage() {
    cat <<'EOF'
SyncOps local operations (Linux checkout)
  bash scripts/syncops.sh start|stop|status|urls|diagnose compose|observability|logs|kind
  bash scripts/syncops.sh demo compose [batch]
  bash scripts/syncops.sh backup|restore-drill compose
  bash scripts/syncops.sh open|urls kind [staging|production-lab]
  bash scripts/syncops.sh verify kind|gitops

compose         PostgreSQL application
observability   Compose with Prometheus, Grafana and Alertmanager
logs            Observability with Loki and Alloy
kind            Persistent Helm lab with two namespaces
verify          Disposable Kubernetes or Argo CD acceptance lab
EOF
}

fail() { printf 'SyncOps: %s\n' "$*" >&2; exit 1; }
need() {
    local tool
    for tool in "$@"; do
        command -v "$tool" >/dev/null || fail "Required tool missing: $tool"
    done
}

prepare_linux() {
    case "$root:$(stat -f -c '%T' "$root")" in
        /mnt/[a-z]:*|/mnt/[a-z]/*|*:9p|*:drvfs|*:cifs|*:smb2)
            fail "Clone SyncOps inside the WSL Linux home directory." ;;
    esac
}

private_path() {
    local path=$1 type=$2 mode=$3
    if [[ -L "$path" || ! -O "$path" || ( "$type" == d && ! -d "$path" ) ||
        ( "$type" == f && ! -f "$path" ) ]]; then
        fail "Expected an owned, non-symlink path: $path"
    fi
    [[ $(stat -c '%a' "$path") == "$mode" ]] || fail "Expected mode $mode: $path"
}

private_dir() {
    if [[ ! -e "$1" && ! -L "$1" ]]; then mkdir -m 0700 -- "$1"; fi
    private_path "$1" d 700
}

docker_local() {
    need docker
    local endpoint
    DOCKER_CONTEXT=$(docker context show)
    endpoint=$(docker context inspect "$DOCKER_CONTEXT" --format '{{.Endpoints.docker.Host}}')
    [[ "$endpoint" == unix:///* ]] || fail "Select a Docker context with a local Unix socket."
    unset DOCKER_HOST DOCKER_CERT_PATH DOCKER_TLS_VERIFY
    export DOCKER_CONTEXT
    docker version --format '{{.Server.Version}}' >/dev/null || fail "Start the local Docker daemon."
}

scrub_compose_env() {
    local key
    while IFS= read -r key; do
        case "$key" in SYNCOPS_*|COMPOSE_*) unset "$key" ;; esac
    done < <(compgen -e)
}

init_settings() (
    set +x
    need openssl flock
    private_dir "$state"
    exec 9>"$state/compose-env.lock"
    flock -x 9
    local tmp key generated
    if [[ ! -e "$settings" && ! -L "$settings" ]]; then
        tmp=$(mktemp "$root/.env.new.XXXXXXXX")
        trap 'rm -f -- "$tmp"' EXIT
        for key in DB_ADMIN_PASSWORD DB_PASSWORD ADMIN_PASSWORD OPERATOR_PASSWORD VIEWER_PASSWORD MOCK_TOKEN; do
            generated=$(openssl rand -hex 32)
            printf 'SYNCOPS_%s=%s\n' "$key" "$generated"
        done >"$tmp"
        printf 'SYNCOPS_WEB_PORT=8080\n' >>"$tmp"
        ln -- "$tmp" "$settings"
        printf 'Created private Linux credentials in .env.\n'
    fi
    private_path "$settings" f 600
    if [[ "$profile" != compose ]] && ! grep -q '^SYNCOPS_GRAFANA_PASSWORD=' "$settings"; then
        generated=$(openssl rand -hex 32)
        printf '\nSYNCOPS_GRAFANA_PASSWORD=%s\n' "$generated" >>"$settings"
        printf 'Added a separate Grafana credential to .env.\n'
    fi
)

containers() {
    docker ps "$@" --filter "label=com.docker.compose.project=$project"
}

check_compose_owner() {
    local owners owner
    owners=$(containers -a --format '{{.Label "com.docker.compose.project.working_dir"}}')
    if [[ -n "$owners" ]]; then
        while IFS= read -r owner; do
            [[ "$owner" == "$root" ]] || fail "The Compose project syncops belongs to another checkout."
        done <<<"$owners"
    fi
}

compose() {
    docker compose --env-file "$settings" --project-directory "$root" --project-name "$project" \
        "${files[@]}" "$@"
}

http_ok() {
    local code
    code=$(curl --noproxy '*' --proto '=http' -s --max-time 4 -o /dev/null -w '%{http_code}' "$1") &&
        [[ "$code" == 200 ]]
}

show_url() {
    local name=$1 origin=$2 check=$3
    if http_ok "$origin$check"; then
        printf 'Verified   %-17s %s\n' "$name" "$origin"
    else
        printf 'Unverified %-17s (loopback health probe failed)\n' "$name"
        return 1
    fi
}

compose_origin() {
    local binding
    binding=$(compose port "$1" "$2" 2>/dev/null) || return 1
    [[ "$binding" =~ ^127\.0\.0\.1:[0-9]{1,5}$ ]] || return 1
    printf 'http://%s\n' "$binding"
}

report_binding() {
    local origin
    if origin=$(compose_origin "$2" "$3"); then
        show_url "$1" "$origin" "$4"
    else
        printf 'Unverified %-17s (no published loopback port)\n' "$1"
        return 1
    fi
}

compose_urls() {
    need curl
    local result=0
    report_binding Console web 8080 /healthz || result=1
    if [[ "$metrics" == 1 ]]; then
        report_binding Prometheus prometheus 9090 /-/ready || result=1
        report_binding Grafana grafana 3000 /api/health || result=1
        report_binding Alertmanager alertmanager 9093 /-/ready || result=1
    fi
    return "$result"
}

diagnostics() {
    printf 'Docker context: %s\n' "$DOCKER_CONTEXT"
    docker version --format 'Docker client {{.Client.Version}}, Engine {{.Server.Version}}'
    docker info --format 'Cgroup v{{.CgroupVersion}}, CPUs {{.NCPU}}, driver {{.Driver}}'
    free -h
    df -h "$root"
}

compose_backup() (
    local backups="$state/backups" archive destination
    private_dir "$state"
    private_dir "$backups"
    archive=$(mktemp "$backups/.postgres-XXXXXXXX")
    trap 'rm -f -- "$archive"' EXIT
    destination="$backups/syncops-pg-$(date -u +%Y%m%dT%H%M%SZ).dump"
    compose exec -T db sh -ec '
        export PGPASSWORD="$POSTGRES_PASSWORD"
        exec pg_dump -h 127.0.0.1 -U postgres -d syncops -Fc --no-owner --no-acl
    ' >"$archive"
    compose exec -T db pg_restore --list <"$archive" >/dev/null
    ln -- "$archive" "$destination"
    printf 'Created PostgreSQL backup with a readable archive catalog: %s\n' "$destination"
)

restore_drill() {
    need python3
    private_dir "$state"
    private_dir "$state/backups"
    python3 -m ops.postgres_reliability.run --docker-context "$DOCKER_CONTEXT" \
        --evidence "$state/backups/postgres-restore-drill-$(date -u +%Y%m%dT%H%M%SZ).json"
}

compose_action() {
    local services running origin metrics=0
    local -a files=(-f "$root/compose.yaml")
    docker compose version >/dev/null
    scrub_compose_env
    if [[ "$action" == restore-drill ]]; then
        restore_drill
        return
    fi
    check_compose_owner
    services=$(containers -a --format '{{.Label "com.docker.compose.service"}}')
    if [[ "$action" == status || "$action" == diagnose ]]; then
        if [[ "$action" == diagnose ]]; then
            diagnostics
            docker compose version
        fi
        containers -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
        if [[ "$action" == status || -z "$services" ]]; then return; fi
    fi
    if [[ "$action" == start ]]; then
        running=$(containers --format '{{.Label "com.docker.compose.service"}}')
        if [[ "$profile" == compose && "$running" == *grafana* ]] ||
           [[ "$profile" != logs && "$running" == *alloy* ]]; then
            fail "Stop the current Compose stack before starting a smaller profile."
        fi
        init_settings
    elif [[ "$action" == stop && -z "$services" ]]; then
        printf 'No containers for the SyncOps Compose project.\n'
        return
    fi
    private_path "$settings" f 600
    if [[ "$profile" != compose || ( "$action" != start && "$services" == *grafana* ) ]]; then
        metrics=1
        files+=(-f "$root/compose.observability.yaml")
    fi
    if [[ "$profile" == logs || ( "$action" != start && "$services" == *alloy* ) ]]; then
        files+=(-f "$root/compose.logs.yaml")
    fi
    case "$action" in
        start)
            compose up -d --build --wait --wait-timeout 180
            compose_urls ;;
        stop)
            compose stop ;;
        urls|diagnose)
            compose_urls ;;
        demo)
            need curl python3
            origin=$(compose_origin web 8080) || fail "The web service needs a published loopback port."
            http_ok "$origin/healthz" || fail "The Compose web health check failed."
            env NO_PROXY='*' no_proxy='*' python3 scripts/seed_demo.py --base-url "$origin" --credentials "$settings" "${demo_options[@]}" ;;
        backup)
            compose_backup ;;
    esac
}

kube() { kubectl --context "$kind_context" "$@"; }

kind_tools() {
    need kind kubectl helm flock
    [[ $(docker info --format '{{.CgroupVersion}}') == 2 ]] || fail "The kind lab requires cgroup v2."
    export KIND_EXPERIMENTAL_PROVIDER=docker
    private_dir "$state"
}

kind_nodes() {
    docker ps -a --no-trunc --filter "label=io.x-k8s.kind.cluster=$1" --format '{{.ID}}'
}

kind_create() {
    kind create cluster --name "$1" --image "$node_image" --wait 180s --config=<(cat <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  apiServerAddress: "127.0.0.1"
EOF
    )
}

build_images() {
    docker build -t "$1" -f deploy/backend.Dockerfile backend
    docker build --build-context config=deploy -t "$2" -f deploy/frontend.Dockerfile frontend
}

load_images() (
    local cluster=$1
    shift
    local platform archive
    platform=$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')
    archive=$(mktemp)
    trap 'rm -f -- "$archive"' EXIT
    docker pull --platform "$platform" postgres:17-bookworm
    # The Docker containerd store can retain index entries for blobs absent locally.
    docker image save --platform "$platform" -o "$archive" "$@" postgres:17-bookworm
    kind load image-archive --name "$cluster" "$archive"
)

init_namespaces() {
    local context=$1 target found
    for target in syncops-staging syncops-production-lab; do
        found=$(kubectl --context "$context" get namespace "$target" --ignore-not-found -o name)
        if [[ -z "$found" ]]; then kubectl --context "$context" create namespace "$target"; fi
        kubectl --context "$context" label namespace "$target" \
            pod-security.kubernetes.io/enforce=restricted --overwrite
        pwsh -NoProfile -File deploy/kubernetes/Initialize-Secrets.ps1 -Context "$context" -Namespace "$target"
    done
}

owned_node() {
    private_path "$state/kind-local.id" f 600
    local id actual
    id=$(<"$state/kind-local.id")
    [[ "$id" =~ ^[0-9a-f]{64}$ ]] || fail "Invalid kind ownership record."
    actual=$(docker inspect --type container --format '{{.Id}} {{index .Config.Labels "io.x-k8s.kind.cluster"}}' "$id")
    [[ "$actual" == "$id $kind_name" ]] || fail "The kind node does not match its ownership record."
    printf '%s\n' "$id"
}

start_kind() {
    local id target backend frontend backend_id frontend_id
    need pwsh
    if [[ ! -e "$state/kind-local.id" && ! -L "$state/kind-local.id" ]]; then
        [[ -z $(kind_nodes "$kind_name") ]] || fail "The cluster name $kind_name is already in use."
        [[ ! -e "$KUBECONFIG" && ! -L "$KUBECONFIG" ]] || fail "The launcher kind kubeconfig already exists."
        kind_create "$kind_name"
        id=$(kind_nodes "$kind_name")
        [[ "$id" =~ ^[0-9a-f]{64}$ ]] || fail "Expected one kind node created by the launcher."
        (set -o noclobber; printf '%s\n' "$id" >"$state/kind-local.id")
    else
        id=$(owned_node)
        private_path "$KUBECONFIG" f 600
        if [[ $(docker inspect --type container --format '{{.State.Running}}' "$id") != true ]]; then
            docker start "$id" >/dev/null
            kind export kubeconfig --name "$kind_name" --kubeconfig "$KUBECONFIG"
        fi
    fi
    private_path "$KUBECONFIG" f 600
    local attempt
    for attempt in {1..20}; do
        if kube --request-timeout=3s get --raw /readyz >/dev/null 2>&1; then break; fi
        sleep 2
    done
    kube --request-timeout=5s get --raw /readyz >/dev/null
    if [[ $(kube get node "$kind_name-control-plane" -o 'jsonpath={.spec.unschedulable}') == true ]]; then
        kube uncordon "$kind_name-control-plane"
    fi
    kube wait --for=condition=Ready node --all --timeout=120s
    build_images syncops/backend:lab-build syncops/frontend:lab-build
    backend_id=$(docker image inspect syncops/backend:lab-build --format '{{.Id}}')
    frontend_id=$(docker image inspect syncops/frontend:lab-build --format '{{.Id}}')
    [[ "$backend_id" =~ ^sha256:[0-9a-f]{64}$ && "$frontend_id" =~ ^sha256:[0-9a-f]{64}$ ]] ||
        fail "Expected content identifiers for the built images."
    backend="syncops/backend:lab-${backend_id#sha256:}"
    frontend="syncops/frontend:lab-${frontend_id#sha256:}"
    docker tag syncops/backend:lab-build "$backend"
    docker tag syncops/frontend:lab-build "$frontend"
    load_images "$kind_name" "$backend" "$frontend"
    init_namespaces "$kind_context"
    for target in syncops-staging syncops-production-lab; do
        helm upgrade --install syncops charts/syncops --kube-context "$kind_context" \
            -n "$target" --wait --wait-for-jobs --timeout 5m \
            --set-string "images.backend.reference=$backend,images.frontend.reference=$frontend"
    done
    printf 'Open a local console with bash scripts/syncops.sh open kind staging\n'
}

kind_action() {
    kind_tools
    export KUBECONFIG="$state/kind-local.yaml"
    case "$action" in
        start|stop)
            exec 8>"$state/kind-local.lock"
            flock -n 8 || fail "A persistent kind lifecycle action is already running." ;;
    esac
    case "$action" in
        start) start_kind ;;
        stop)
            if [[ ! -e "$state/kind-local.id" && ! -L "$state/kind-local.id" ]]; then
                printf 'No launcher-owned persistent kind node.\n'
                return
            fi
            local id
            id=$(owned_node)
            if [[ $(docker inspect --type container --format '{{.State.Running}}' "$id") != true ]]; then
                printf 'The owned kind node is already stopped. Its data is retained.\n'
                return
            fi
            private_path "$KUBECONFIG" f 600
            kube --request-timeout=20s drain "$kind_name-control-plane" \
                --pod-selector 'app.kubernetes.io/name=syncops,app.kubernetes.io/instance=syncops' \
                --ignore-daemonsets --delete-emptydir-data --timeout=120s
            docker stop --timeout 75 "$id" >/dev/null
            printf 'Stopped the owned kind node. Its data is retained.\n' ;;
        status|diagnose)
            owned_node >/dev/null
            private_path "$KUBECONFIG" f 600
            if [[ "$action" == diagnose ]]; then diagnostics; fi
            kube --request-timeout=10s get nodes
            local target
            for target in syncops-staging syncops-production-lab; do
                kube --request-timeout=10s -n "$target" get deploy,sts,pod,job,pvc,svc
            done ;;
        open|urls)
            owned_node >/dev/null
            private_path "$KUBECONFIG" f 600
            local namespace=syncops-staging port=18080
            if [[ "$environment" == production-lab ]]; then namespace=syncops-production-lab; port=18081; fi
            if [[ "$action" == open ]]; then
                kube -n "$namespace" port-forward --address 127.0.0.1 svc/syncops-web "$port:8080"
            else
                need curl
                kube --request-timeout=10s -n "$namespace" get service syncops-web -o name >/dev/null
                show_url "$namespace" "http://127.0.0.1:$port" /healthz
            fi ;;
    esac
}

verify_cluster() (
    kind_tools
    need curl pwsh python3
    exec 8>"$state/kind-acceptance.lock"
    flock -n 8 || fail "A disposable acceptance run is already in progress."
    local cluster=syncops-ci registry_container= registry_id= temporary owned=0
    if [[ "$profile" == gitops ]]; then
        cluster=syncops-gitops-ci
        registry_container="syncops-registry-$cluster"
    fi
    [[ -z $(kind_nodes "$cluster") ]] || fail "The disposable cluster name $cluster is already in use."
    if [[ -n "$registry_container" ]] &&
       docker inspect --type container "$registry_container" >/dev/null 2>&1; then
        fail "The disposable registry name is already in use."
    fi
    temporary=$(mktemp -d "$state/acceptance.XXXXXXXX")
    export KUBECONFIG="$temporary/kubeconfig"
    cleanup() {
        local code=$?
        trap - EXIT
        if [[ -n "$registry_id" ]]; then docker rm -f "$registry_id" >/dev/null || code=1; fi
        if [[ "$owned" == 1 ]]; then kind delete cluster --name "$cluster" || code=1; fi
        rm -f -- "$KUBECONFIG"
        rmdir -- "$temporary" || code=1
        exit "$code"
    }
    trap cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    if [[ "$profile" == kind ]]; then
        kind_create "$cluster"
        owned=1
        build_images syncops/backend:local syncops/frontend:local
        load_images "$cluster" syncops/backend:local syncops/frontend:local
        init_namespaces "kind-$cluster"
        helm lint charts/syncops --strict --kube-version v1.35.0
        bash deploy/kubernetes/verify-kind.sh 2>&1 | sed '/^::add-mask::/d'
    else
        local bootstrap_ok=0 registry=localhost:5001/syncops
        bash deploy/gitops/bootstrap-kind.sh "$cluster" && bootstrap_ok=1
        if [[ -s "$KUBECONFIG" && -n $(kind_nodes "$cluster") ]]; then owned=1; fi
        registry_id=$(docker inspect --type container --format '{{.Id}}' "$registry_container" 2>/dev/null || true)
        [[ "$bootstrap_ok" == 1 ]] || fail "Argo CD bootstrap failed."
        build_images "$registry/backend:baseline" "$registry/frontend:baseline"
        docker push "$registry/backend:baseline"
        docker push "$registry/frontend:baseline"
        printf 'FROM %s/frontend:baseline\nLABEL org.syncops.lab.candidate=true\n' "$registry" |
            docker build -t "$registry/frontend:candidate" -
        docker push "$registry/frontend:candidate"
        docker build -t syncops/git-fixture:local -f deploy/gitops/git-fixture.Dockerfile deploy/gitops
        load_images "$cluster" syncops/git-fixture:local
        kubectl --context "kind-$cluster" apply -f deploy/gitops/git-fixture.yaml
        kubectl --context "kind-$cluster" -n argocd rollout status deployment/git-fixture --timeout=120s
        bash deploy/gitops/verify-argocd.sh 2>&1 | sed '/^::add-mask::/d'
    fi
)

if [[ "$#" == 0 || "$1" == help || "$1" == --help ]]; then usage; exit; fi
[[ "$#" -ge 2 && "$#" -le 3 ]] || { usage >&2; exit 2; }
action=$1
profile=$2
environment=${3:-staging}
demo_options=()
if [[ "$#" == 3 ]]; then
    case "$action/$profile/$environment" in
        open/kind/staging|open/kind/production-lab|urls/kind/staging|urls/kind/production-lab) ;;
        demo/compose/*)
            [[ "$3" =~ ^[a-z][a-z0-9-]{0,31}$ ]] || fail "Invalid demo batch name."
            demo_options=(--batch "$3") ;;
        *) fail "Unknown action, profile or environment." ;;
    esac
fi
case "$action/$profile" in
    start/compose|start/observability|start/logs|stop/compose|stop/observability|stop/logs|\
    status/compose|status/observability|status/logs|urls/compose|urls/observability|urls/logs|\
    diagnose/compose|diagnose/observability|diagnose/logs|demo/compose|backup/compose|restore-drill/compose)
        prepare_linux; docker_local; compose_action ;;
    start/kind|stop/kind|status/kind|urls/kind|diagnose/kind|open/kind)
        prepare_linux; docker_local; kind_action ;;
    verify/kind|verify/gitops)
        prepare_linux; docker_local; verify_cluster ;;
    *) usage >&2; exit 2 ;;
esac
