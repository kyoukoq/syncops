#!/usr/bin/env bash
set -euo pipefail

source_root=$(git rev-parse --show-toplevel)
fixture_dir=$(mktemp -d)
worktree="$fixture_dir/source"
bare_repo="$fixture_dir/syncops.git"
context=kind-syncops-gitops-ci
registry=localhost:5001/syncops
git_endpoint=http://git-fixture.argocd.svc:8000/cgi-bin/git/syncops.git
forward_pid=

close_forward() {
    if [[ -n "$forward_pid" ]]; then
        kill "$forward_pid" 2>/dev/null || true
        wait "$forward_pid" 2>/dev/null || true
        forward_pid=
    fi
}
trap close_forward EXIT

kube() {
    kubectl --context "$context" "$@"
}

gitlab() {
    git -C "$worktree" "$@"
}

release() {
    (cd "$worktree" && python3 "$source_root/deploy/gitops/release.py" "$@")
}

publish_fixture() {
    gitlab push fixture refs/heads/syncops-lab-staging refs/heads/syncops-lab-production
    tar -C "$fixture_dir" -cf - syncops.git | kube -n argocd exec -i deploy/git-fixture -- sh -ec '
        snapshot=$(mktemp -d /repos/revision.XXXXXX)
        tar -xf - -C "$snapshot"
        ln -s "$snapshot/syncops.git" /repos/.next
        mv -Tf /repos/.next /repos/syncops.git
    '
}

refresh() {
    kube -n argocd annotate "application.argoproj.io/syncops-$1" argocd.argoproj.io/refresh=hard --overwrite
}

wait_for_release() {
    local environment="$1" revision="$2" log="$fixture_dir/release-gate.log"
    refresh "$environment"
    for _ in {1..80}; do
        if release verify --context "$context" --environment "$environment" --revision "$revision" > "$log" 2>&1; then
            cat "$log"
            return
        fi
        sleep 3
    done
    cat "$log" >&2
    return 1
}

run_smoke() {
    local namespace="syncops-$1" password port base_url log="$fixture_dir/port-forward.log"
    password=$(kube -n "$namespace" get secret "$namespace-api-auth" -o 'jsonpath={.data.admin-password}' | base64 -d)
    if [[ "${GITHUB_ACTIONS:-}" == true ]]; then
        echo "::add-mask::$password"
    fi
    kubectl --context "$context" -n "$namespace" port-forward --address 127.0.0.1 \
        "svc/$namespace-web" :8080 > "$log" 2>&1 &
    forward_pid=$!
    for _ in {1..20}; do
        port=$(sed -n 's/^Forwarding from 127\.0\.0\.1:\([0-9][0-9]*\) -> 8080$/\1/p' "$log")
        if [[ -n "$port" ]]; then
            break
        fi
        kill -0 "$forward_pid" 2>/dev/null || break
        sleep 1
    done
    if [[ -z "$port" ]]; then
        cat "$log" >&2
        return 1
    fi
    base_url="http://127.0.0.1:$port"
    curl --noproxy '*' -fsS --max-time 2 "$base_url/healthz"
    SYNCOPS_ADMIN_PASSWORD="$password" python3 "$source_root/scripts/smoke.py" --base-url "$base_url"
    close_forward
}

repo_digest() {
    docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$1" | awk -v prefix="${1%:*}@" 'index($0, prefix) == 1'
}

backend=$(repo_digest "$registry/backend:baseline")
frontend=$(repo_digest "$registry/frontend:baseline")
frontend_next=$(repo_digest "$registry/frontend:candidate")
[[ -n "$backend" && -n "$frontend" && -n "$frontend_next" && "$frontend" != "$frontend_next" ]]

git init --bare --initial-branch=syncops-lab-staging "$bare_repo"
git -C "$bare_repo" config http.receivepack false
git init --initial-branch=syncops-lab-staging "$worktree"
gitlab config user.name 'SyncOps lab'
gitlab config user.email 'lab@example.invalid'
gitlab config commit.gpgsign false
gitlab remote add fixture "$bare_repo"
git archive HEAD charts/syncops | tar -x -C "$worktree"
mkdir -p "$worktree/deploy/gitops"
release write-values --backend "$backend" --frontend "$frontend"
gitlab add charts deploy
gitlab commit -m 'Deploy the baseline SyncOps release'
baseline=$(gitlab rev-parse HEAD)
gitlab branch syncops-lab-production
publish_fixture

sed "s|https://github.com/kyoukoq/syncops.git|$git_endpoint|g" "$source_root/deploy/gitops/apps.yaml" | kube apply -f -
wait_for_release staging "$baseline"
wait_for_release production-lab "$baseline"
run_smoke staging

kube -n syncops-staging scale deployment syncops-staging-worker --replicas=1
[[ $(kube -n syncops-staging get deployment syncops-staging-worker -o 'jsonpath={.spec.replicas}') == 1 ]]
wait_for_release staging "$baseline"
echo 'Argo CD restored the staging worker replicas after live drift'

release write-values --backend "$backend" --frontend "$frontend_next"
gitlab commit -am 'Deploy the candidate SyncOps release to staging'
candidate=$(gitlab rev-parse HEAD)
publish_fixture
wait_for_release staging "$candidate"
run_smoke staging
release verify --context "$context" --environment staging --revision "$candidate"
release verify --context "$context" --environment production-lab --revision "$baseline"

gitlab switch syncops-lab-production
gitlab merge --no-ff "$candidate" -m 'Promote the healthy staging revision to the production lab'
promotion=$(gitlab rev-parse HEAD)
[[ $(gitlab rev-parse "$promotion^{tree}") == "$(gitlab rev-parse "$candidate^{tree}")" ]]
publish_fixture
wait_for_release production-lab "$promotion"
run_smoke production-lab

gitlab switch syncops-lab-staging
printf -v missing '%064d' 0
release write-values --backend "$backend" --frontend "$registry/frontend@sha256:$missing"
gitlab commit -am 'Introduce a missing staging image for the recovery drill'
broken=$(gitlab rev-parse HEAD)
publish_fixture
refresh staging
failed_image=false
for _ in {1..60}; do
    current_revision=$(kube -n argocd get application.argoproj.io/syncops-staging -o 'jsonpath={.status.sync.revision}')
    health=$(kube -n argocd get application.argoproj.io/syncops-staging -o 'jsonpath={.status.health.status}')
    pod_status=$(kube -n syncops-staging get pods -l app.kubernetes.io/component=web \
        -o 'jsonpath={..state.waiting.reason}')
    if [[ "$current_revision" == "$broken" && "$health" != Healthy && "$pod_status" =~ ErrImagePull|ImagePullBackOff ]]; then
        failed_image=true
        break
    fi
    sleep 3
done
[[ "$failed_image" == true ]]
if release verify --context "$context" --environment staging --revision "$broken"; then
    echo 'Promotion gate unexpectedly approved an unhealthy revision' >&2
    exit 1
fi
release verify --context "$context" --environment production-lab --revision "$promotion"

gitlab revert --no-edit "$broken"
recovered=$(gitlab rev-parse HEAD)
publish_fixture
wait_for_release staging "$recovered"
run_smoke staging

gitlab switch syncops-lab-production
gitlab revert -m 1 --no-edit "$promotion"
rollback=$(gitlab rev-parse HEAD)
[[ $(gitlab rev-parse "$rollback^{tree}") == "$(gitlab rev-parse "$baseline^{tree}")" ]]
publish_fixture
wait_for_release production-lab "$rollback"
run_smoke production-lab
echo 'Staging recovery and production rollback reconciled from Git reverts'
