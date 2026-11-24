#!/usr/bin/env bash
set -euo pipefail

# Pin upstream release artifacts independently of a package manager cache.
tools_dir=$(mktemp -d)
trap 'rm -rf -- "$tools_dir"' EXIT
cd "$(git rev-parse --show-toplevel)"
report_dir="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/syncops-assurance"
mkdir -p "$report_dir"

fetch_tool() {
  local project=$1 version=$2 archive=$3 checksum=$4
  curl --proto '=https' --fail --silent --show-error --location --retry 3 \
    --output "$tools_dir/$archive" "https://github.com/$project/releases/download/v$version/$archive"
  printf '%s  %s\n' "$checksum" "$tools_dir/$archive" | sha256sum --check --status
  tar -xzf "$tools_dir/$archive" -C "$tools_dir"
}

fetch_tool gitleaks/gitleaks 8.30.1 gitleaks_8.30.1_linux_x64.tar.gz \
  551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
"$tools_dir/gitleaks" git . --log-opts=--all --redact=100 --no-banner --no-color

fetch_tool aquasecurity/trivy 0.76.2 trivy_0.76.2_Linux-64bit.tar.gz \
  bc0fc726e017b8927a62b2d3531d7a84ee01769daf5c99ed866dced54089fdbf

revision=$(git rev-parse HEAD)
version="${SYNCOPS_IMAGE_VERSION:-sha-$revision}"
source_url="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-kyoukoq/syncops}"
common_labels=(
  --label "org.opencontainers.image.source=$source_url"
  --label "org.opencontainers.image.revision=$revision"
  --label "org.opencontainers.image.version=$version"
)
docker build "${common_labels[@]}" -t syncops/backend:assurance -f deploy/backend.Dockerfile backend
docker build "${common_labels[@]}" -t syncops/frontend:assurance \
  --build-context config=deploy -f deploy/frontend.Dockerfile frontend

status=0
for component in backend frontend; do
  image="syncops/$component:assurance"
  user=$(docker image inspect "$image" --format '{{.Config.User}}')
  case "$user" in
    ''|0|0:*|root|root:*) printf '%s defaults to root\n' "$image" >&2; exit 1 ;;
  esac
  printf '%s runtime user %s\n' "$image" "$user"
  "$tools_dir/trivy" image --timeout 8m --image-src docker --format cyclonedx \
    --output "$report_dir/$component.cdx.json" "$image"
  jq -e '.bomFormat == "CycloneDX" and (.components | length > 0)' \
    "$report_dir/$component.cdx.json" >/dev/null
  "$tools_dir/trivy" image --timeout 8m --image-src docker --scanners vuln \
    --severity HIGH,CRITICAL --format json --output "$report_dir/$component.trivy.json" "$image"
  jq -r --arg image "$image" '
    [.Results[]?.Vulnerabilities[]?] as $findings |
    "\($image): \($findings|length) HIGH/CRITICAL findings, " +
    "\([$findings[] | select((.FixedVersion // "") != "")]|length) with fixes"
  ' "$report_dir/$component.trivy.json"
  jq -r '.Results[]?.Vulnerabilities[]? | [.VulnerabilityID,.PkgName,.InstalledVersion,(.FixedVersion // ""),.Severity] | @tsv' \
    "$report_dir/$component.trivy.json" | sort -u
  if ! jq -e '[.Results[]?.Vulnerabilities[]? | select((.FixedVersion // "") != "")] | length == 0' \
    "$report_dir/$component.trivy.json" >/dev/null; then
    status=1
  fi
done
printf 'CycloneDX and vulnerability reports generated for backend and frontend.\n'
exit "$status"
