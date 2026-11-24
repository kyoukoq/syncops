"""Verify sign-in, event delivery and ingress deduplication on a running lab."""

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_admin_password(env_file: Path | None) -> str:
    password = os.environ.get("SYNCOPS_ADMIN_PASSWORD")
    if password:
        return password
    if env_file and env_file.suffix == ".json":
        return json.loads(env_file.read_text(encoding="utf-8"))["admin"]
    if env_file:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("SYNCOPS_ADMIN_PASSWORD="):
                return line.partition("=")[2]
    raise RuntimeError(
        "Provide an admin password through the environment or --credentials."
    )


def run_smoke(base: str, password: str) -> None:
    opener = build_opener(ProxyHandler({}), NoRedirect())
    token = ""

    def request(path: str, data: dict | None = None, key: str | None = None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if key:
            headers["Idempotency-Key"] = key
        if data is not None:
            headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode() if data is not None else None
        try:
            with opener.open(
                Request(f"{base}{path}", data=body, headers=headers), timeout=5
            ) as response:
                content = response.read()
                return json.loads(content) if content else None
        except HTTPError as error:
            raise RuntimeError(f"{path} returned HTTP {error.code}.") from None

    token = request("/auth/login", {"username": "admin", "password": password})["token"]
    try:
        integration = next(
            (item for item in request("/integrations") if item["enabled"]), None
        )
        if not integration:
            raise RuntimeError("An enabled integration is required for the smoke test.")
        key = str(uuid.uuid4())
        event = {
            "integration_id": integration["id"],
            "event_type": "company.created",
            "payload": {"name": "Synthetic Smoke Company", "reference": key},
        }
        submitted = request("/events", event, key)
        duplicate = request("/events", event, key)
        if submitted["id"] != duplicate["id"]:
            raise RuntimeError("Idempotent submission created more than one event.")

        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            result = request(f"/events/{submitted['id']}")
            if result["status"] == "succeeded":
                if not result["attempts"]:
                    raise RuntimeError("A delivered event has no attempt history.")
                print(
                    "Smoke passed: sign-in, submission, deduplication, worker and mock delivery."
                )
                return
            if result["status"] == "dead_letter":
                raise RuntimeError(
                    f"The simulated delivery entered the dead-letter queue: {result['error']}."
                )
            time.sleep(0.25)
        raise RuntimeError("The simulated delivery did not complete within 25 seconds.")
    finally:
        request("/auth/logout", {})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--credentials", type=Path)
    args = parser.parse_args()
    target = urlsplit(args.base_url)
    if (
        target.scheme != "http"
        or target.hostname not in {"localhost", "127.0.0.1", "::1"}
        or target.username is not None
        or target.path.rstrip("/")
        or target.query
        or target.fragment
    ):
        parser.error("Use an HTTP loopback origin for the isolated smoke test.")
    run_smoke(
        f"{args.base_url.rstrip('/')}/api/v1", read_admin_password(args.credentials)
    )


if __name__ == "__main__":
    main()
