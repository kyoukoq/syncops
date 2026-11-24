"""Prepare digest-pinned Helm values and verify a reconciled GitOps revision."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RELEASE_VALUES = "deploy/gitops/release-values.json"
CHART_PATH = "charts/syncops"
KUBE_SERVER = "https://kubernetes.default.svc"
TARGET_BRANCHES = {"staging": "syncops-lab-staging", "production-lab": "syncops-lab-production"}
COMPONENT_IMAGES = {"api": "backend", "mock": "backend", "web": "frontend", "worker": "backend"}
DIGEST_REFERENCE = re.compile(r"[a-z0-9][a-z0-9./:_-]+@sha256:[a-f0-9]{64}")


def digest_reference(reference: str) -> str:
    if not DIGEST_REFERENCE.fullmatch(reference):
        raise ValueError("Provide a repository reference pinned to a sha256 image manifest digest.")
    return reference


def write_values(backend: str, frontend: str) -> None:
    images = {}
    for image, reference in (("backend", backend), ("frontend", frontend)):
        images[image] = {"reference": digest_reference(reference), "pullPolicy": "IfNotPresent"}
    path = Path(RELEASE_VALUES)
    if not Path(CHART_PATH, "Chart.yaml").is_file() or not path.parent.is_dir():
        raise ValueError("Run the release helper from the SyncOps repository root.")
    path.write_text(json.dumps({"images": images}, indent=2) + "\n", encoding="utf-8")


def command_json(command: list[str]) -> dict:
    return json.loads(subprocess.check_output(command, text=True, timeout=20))


def verify_release(context: str, environment: str, revision: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Use the full Git commit SHA for the approved revision.")
    name = f"syncops-{environment}"
    kubectl = ["kubectl", "--context", context, "--request-timeout=10s"]
    app = command_json([*kubectl, "-n", "argocd", "get", "applications.argoproj.io", name, "-o", "json"])
    spec = app["spec"]
    source = spec["source"]
    destination = spec["destination"]
    target = f"refs/heads/{TARGET_BRANCHES[environment]}"
    if (
        destination.get("server") != KUBE_SERVER
        or destination.get("namespace") != name
        or spec["project"] != name
        or source["path"] != CHART_PATH
        or source["targetRevision"] != target
        or source["helm"].get("valueFiles") != [f"../../{RELEASE_VALUES}"]
        or any(
            source["helm"].get(option)
            for option in ("values", "valuesObject", "parameters", "fileParameters", "releaseName")
        )
    ):
        raise ValueError(f"{name} has unexpected destination or Helm source settings.")

    status = app.get("status", {})
    sync = status.get("sync", {})
    health = status.get("health", {}).get("status")
    if sync.get("revision") != revision or sync.get("status") != "Synced" or health != "Healthy":
        raise ValueError(f"{name} has not reconciled the requested revision as Synced and Healthy.")
    if app.get("operation") or any(item["type"].endswith("Error") for item in status.get("conditions", [])):
        raise ValueError(f"{name} has an active operation or an application error.")

    release = command_json(["git", "show", f"{revision}:{RELEASE_VALUES}"])
    pins = {
        image: digest_reference(release["images"][image]["reference"])
        for image in ("backend", "frontend")
    }
    deployed = command_json(
        [*kubectl, "-n", name, "get", "deployments", "-l", f"app.kubernetes.io/instance={name}", "-o", "json"]
    )
    workloads = {item["metadata"]["name"]: item for item in deployed["items"]}
    for component, image in COMPONENT_IMAGES.items():
        deployment = workloads[f"{name}-{component}"]
        containers = deployment["spec"]["template"]["spec"]["containers"]
        expected = pins[image]
        desired_replicas = release.get("worker", {}).get("replicas", 2) if component == "worker" else 1
        actual = deployment["status"]
        if (
            {item["name"]: item["image"] for item in containers} != {component: expected}
            or deployment["spec"]["replicas"] != desired_replicas
            or actual.get("observedGeneration") != deployment["metadata"]["generation"]
            or any(
                actual.get(field) != desired_replicas
                for field in ("readyReplicas", "updatedReplicas", "availableReplicas")
            )
        ):
            raise ValueError(f"{name}-{component} has not rolled out the expected pinned image and replica count.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    prepare = commands.add_parser("write-values")
    prepare.add_argument("--backend", required=True)
    prepare.add_argument("--frontend", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--context", required=True)
    verify.add_argument("--environment", choices=TARGET_BRANCHES, required=True)
    verify.add_argument("--revision", required=True)
    args = parser.parse_args()
    try:
        if args.operation == "write-values":
            write_values(args.backend, args.frontend)
        else:
            verify_release(args.context, args.environment, args.revision)
            print(f"syncops-{args.environment} reconciled {args.revision} with ready, digest-pinned workloads")
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print(f"Release gate failed. {error}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
