"""Add repeatable synthetic portfolio events through the local SyncOps API."""

import argparse
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from smoke import NoRedirect, read_admin_password

ROUTES = (
    ("Portfolio lab / Accounts", "crm", "erp"),
    ("Portfolio lab / Orders", "erp", "tms"),
    ("Portfolio lab / Shipments", "tms", "crm"),
)
CASES = (
    (
        0,
        "company.created",
        "success",
        {"company": "Aster Ridge Logistics", "region": "Great Lakes"},
    ),
    (
        0,
        "contact.created",
        "success",
        {"company": "Juniper Freight", "department": "Dispatch"},
    ),
    (
        0,
        "customer.updated",
        "temporary_outage",
        {"company": "Cedar Harbor Supply", "tier": "standard"},
    ),
    (
        0,
        "account.synced",
        "http_422",
        {"company": "Rainier Cold Chain", "account_class": "unmapped"},
    ),
    (
        1,
        "order.created",
        "success",
        {"order": "LAB-2401", "freight": "dry van", "pallets": 12},
    ),
    (
        1,
        "order.created",
        "http_429",
        {"order": "LAB-2402", "freight": "reefer", "pallets": 18},
    ),
    (
        1,
        "order.created",
        "success",
        {"order": "LAB-2403", "freight": "flatbed", "pallets": 4},
    ),
    (
        2,
        "shipment.updated",
        "temporary_outage",
        {"shipment": "LAB-S110", "status": "dispatched"},
    ),
    (
        2,
        "shipment.updated",
        "http_422",
        {"shipment": "LAB-S111", "status": "unknown_code"},
    ),
    (
        2,
        "shipment.created",
        "success",
        {"shipment": "LAB-S112", "order": "LAB-2403", "service": "regional freight"},
    ),
)
TERMINAL = {"succeeded", "dead_letter"}


def seed(base: str, password: str, batch: str | None = None) -> None:
    opener = build_opener(ProxyHandler({}), NoRedirect())
    token = ""

    def request(path: str, data: dict | None = None, key: str = ""):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if key:
            headers["Idempotency-Key"] = key
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
        stored = {route["name"]: route for route in request("/integrations")}
        route_ids = []
        for name, source, destination in ROUTES:
            route = stored.get(name) or request(
                "/integrations",
                {
                    "name": name,
                    "source": source,
                    "destination": destination,
                    "description": "Synthetic Advanced DevOps Lab demonstration route",
                },
            )
            if (
                route["source"] != source
                or route["destination"] != destination
                or not route["enabled"]
            ):
                raise RuntimeError(
                    f"Existing route {name} has a different configuration."
                )
            route_ids.append(route["id"])

        created = []
        for index, (route, event_type, scenario, payload) in enumerate(CASES, start=1):
            reference = f"SYNCOPS-LAB-{index:02d}"
            key = f"syncops-portfolio-v02-{index:02d}"
            if batch:
                reference = f"SYNCOPS-LAB-{batch}-{index:02d}"
                key = f"syncops-portfolio-v02-{batch}-{index:02d}"
            event = {
                "integration_id": route_ids[route],
                "event_type": event_type,
                "scenario": scenario,
                "payload": {**payload, "reference": reference},
            }
            if scenario == "http_429":
                event["failure_count"] = 1
            created.append(request("/events", event, key)["id"])

        deadline = time.monotonic() + 30
        results = []
        while time.monotonic() < deadline:
            results = [request(f"/events/{event_id}") for event_id in created]
            if all(result["status"] in TERMINAL for result in results):
                break
            time.sleep(0.5)
        if not all(result["status"] in TERMINAL for result in results):
            raise RuntimeError("Some seeded events have not reached a terminal state.")
        for result in results:
            print(
                f"{result['event_type']:18} {result['status']:12} {result['correlation_id']}"
            )
        print(
            f"Verified {len(created)} synthetic demo events across {len(route_ids)} integrations."
        )
    finally:
        request("/auth/logout", {})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--batch", help="Append a fresh named delivery batch and retain existing history.")
    args = parser.parse_args()
    if args.batch is not None and not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", args.batch):
        parser.error("Use a batch name of 1–32 lowercase letters, digits or hyphens, starting with a letter.")
    target = urlsplit(args.base_url)
    if (
        target.scheme != "http"
        or target.hostname not in {"127.0.0.1", "::1", "localhost"}
        or target.username is not None
        or target.path.rstrip("/")
        or target.query
        or target.fragment
    ):
        parser.error("Use an HTTP loopback origin.")
    seed(
        f"{args.base_url.rstrip('/')}/api/v1",
        read_admin_password(args.credentials),
        args.batch,
    )


if __name__ == "__main__":
    main()
