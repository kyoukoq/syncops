"""Check an isolated Compose delivery and its correlation ID in Grafana Loki."""

import base64
import json
import os
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

from smoke import NoRedirect

API = "http://127.0.0.1:8080/api/v1"
GRAFANA = "http://127.0.0.1:3000"
LOKI_PROXY = "/api/datasources/proxy/uid/syncops-loki/loki/api/v1"


def main() -> None:
    opener = build_opener(ProxyHandler({}), NoRedirect())
    token = ""
    basic = base64.b64encode(
        f"admin:{os.environ['SYNCOPS_GRAFANA_PASSWORD']}".encode()
    ).decode()

    def request(url: str, authorization: str = "", data=None, key: str = ""):
        headers = {"Content-Type": "application/json"}
        if authorization:
            headers["Authorization"] = authorization
        if key:
            headers["Idempotency-Key"] = key
        body = json.dumps(data).encode() if data is not None else None
        with opener.open(
            Request(url, data=body, headers=headers), timeout=5
        ) as response:
            content = response.read()
            return json.loads(content) if content else None

    def api(path: str, data=None, key: str = ""):
        return request(f"{API}{path}", f"Bearer {token}" if token else "", data, key)

    token = api(
        "/auth/login",
        {"username": "admin", "password": os.environ["SYNCOPS_ADMIN_PASSWORD"]},
    )["token"]
    marker = f"synthetic-private-{uuid.uuid4()}"
    try:
        integration = next(item for item in api("/integrations") if item["enabled"])
        event = api(
            "/events",
            {
                "integration_id": integration["id"],
                "event_type": "company.created",
                "scenario": "temporary_outage",
                "payload": {"name": "Northwind Logistics", "reference": marker},
            },
            str(uuid.uuid4()),
        )
        event_id = event["id"]
        correlation_id = str(uuid.UUID(event["correlation_id"]))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            detail = api(f"/events/{event_id}")
            if detail["status"] == "succeeded":
                break
            if detail["status"] == "dead_letter":
                raise RuntimeError("Synthetic event did not recover")
            time.sleep(0.5)
        else:
            raise RuntimeError("Synthetic delivery did not complete")
    finally:
        api("/auth/logout", {})

    grafana_auth = f"Basic {basic}"
    dashboard = request(
        f"{GRAFANA}/api/dashboards/uid/syncops-worker-incident", grafana_auth
    )
    assert dashboard["dashboard"]["uid"] == "syncops-worker-incident"
    query = '{job="syncops-worker"} | json | correlation_id = "' + correlation_id + '"'
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        params = urlencode({"query": query, "limit": 25})
        try:
            result = request(
                f"{GRAFANA}{LOKI_PROXY}/query_range?{params}", grafana_auth
            )
        except HTTPError as error:
            if error.code < 500:
                raise
            time.sleep(1)
            continue
        statuses = set()
        for stream in result["data"]["result"]:
            for _, line in stream["values"]:
                record = json.loads(line)
                assert marker not in line and "payload" not in record
                assert record["correlation_id"] == correlation_id
                assert record["event_id"] == event_id
                assert record["message"] == "attempt_finished"
                statuses.add(record["status"])
        if {"retry_scheduled", "succeeded"} <= statuses:
            print(f"Loki verified both attempts for correlation ID {correlation_id}.")
            return
        time.sleep(1)
    raise RuntimeError("Loki did not return both correlated worker attempt logs")


if __name__ == "__main__":
    main()
