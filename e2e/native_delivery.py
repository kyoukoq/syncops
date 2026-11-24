"""Verify the delivery lifecycle against a running native SyncOps lab."""

import argparse
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4


class LocalRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Lab:
    def __init__(self, base_url):
        self.base_url = f"{base_url}/api/v1"
        self.sessions = {}

    def request(self, method, path, *, role=None, data=None, status=200, key=None):
        headers = {"Accept": "application/json"}
        if role:
            headers["Authorization"] = f"Bearer {self.sessions[role]}"
        if key:
            headers["Idempotency-Key"] = key
        if data is not None:
            headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode() if data is not None else None
        request = Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        opener = build_opener(ProxyHandler({}), LocalRedirectHandler())
        try:
            response = opener.open(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            if response.code != status:
                raise AssertionError(
                    f"{method} {path} expected {status}, got {response.code}"
                )
            content = response.read()
            return json.loads(content) if content else None

    def login(self, role, password):
        session = self.request(
            "POST", "/auth/login", data={"username": role, "password": password}
        )
        self.sessions[role] = session["token"]
        assert self.request("GET", "/auth/me", role=role) == {
            "username": role,
            "role": role,
        }

    def logout(self, role):
        self.request("POST", "/auth/logout", role=role, status=204)
        self.request("GET", "/auth/me", role=role, status=401)
        del self.sessions[role]

    def detail(self, event_id, role="operator"):
        return self.request("GET", f"/events/{event_id}", role=role)

    def wait_for(self, event_id, status):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            event = self.detail(event_id)
            if event["status"] == status:
                return event
            if event["status"] in {"succeeded", "dead_letter"}:
                raise AssertionError(
                    f"Expected {status}, event reached {event['status']}"
                )
            time.sleep(0.05)
        raise AssertionError(f"Event did not reach {status} within 25 seconds")


def as_time(value):
    return datetime.fromisoformat(value).timestamp()


def verify_deliveries(lab, integration, db, run_id):
    integration_id = integration["id"]

    def submission(name, scenario, failure_count=None):
        return {
            "integration_id": integration_id,
            "event_type": "company.created",
            "payload": {"name": f"Synthetic QA {run_id} {name}"},
            "scenario": scenario,
            "failure_count": failure_count,
        }

    def submit(name, scenario, failure_count=None):
        return lab.request(
            "POST",
            "/events",
            role="operator",
            data=submission(name, scenario, failure_count),
            status=202,
        )["id"]

    def effects(event_id):
        return db.execute(
            "SELECT COUNT(*) FROM mock_operations WHERE event_id = ?", (event_id,)
        ).fetchone()[0]

    def attempts(event):
        return [
            (attempt["status"], attempt["http_status"]) for attempt in event["attempts"]
        ]

    success_id = submit("success", "success")
    success = lab.wait_for(success_id, "succeeded")
    assert attempts(success) == [("succeeded", 200)]
    assert effects(success_id) == 1
    assert "payload" not in lab.detail(success_id, role="viewer")
    print(
        "PASS A | successful HTTP delivery, one persisted mock effect, sanitized event detail"
    )

    outage_id = submit("outage", "temporary_outage")
    outage = lab.wait_for(outage_id, "succeeded")
    assert attempts(outage) == [("retry_scheduled", 503), ("succeeded", 200)]
    assert effects(outage_id) == 1
    print("PASS B | real HTTP 503 followed by scheduled retry and successful delivery")

    throttled_id = submit("rate-limited", "http_429", 1)
    scheduled = lab.wait_for(throttled_id, "retry_scheduled")
    assert attempts(scheduled) == [("retry_scheduled", 429)]
    first_finished = as_time(scheduled["attempts"][0]["finished_at"])
    due = as_time(scheduled["next_retry_at"])
    assert due - first_finished >= 1.999, (
        "Retry was scheduled earlier than Retry-After: 2"
    )
    throttled = lab.wait_for(throttled_id, "succeeded")
    assert attempts(throttled) == [("retry_scheduled", 429), ("succeeded", 200)]
    actual = as_time(throttled["attempts"][1]["started_at"])
    assert actual >= due, "Worker dispatched before the persisted retry deadline"
    assert effects(throttled_id) == 1
    print(
        f"PASS C | Retry-After scheduled {due - first_finished:.3f}s, dispatched after {actual - first_finished:.3f}s"
    )

    invalid_id = submit("invalid", "http_422")
    invalid = lab.wait_for(invalid_id, "dead_letter")
    assert attempts(invalid) == [("dead_letter", 422)]
    assert invalid["next_retry_at"] is None and effects(invalid_id) == 0
    print("PASS D | permanent HTTP 422 entered dead letter after one attempt")

    timeout_id = submit("timeout", "timeout")
    timed_out = lab.wait_for(timeout_id, "dead_letter")
    assert attempts(timed_out) == [("retry_scheduled", None), ("dead_letter", None)]
    assert all(
        "timed out" in attempt["error"].lower() for attempt in timed_out["attempts"]
    )
    assert effects(timeout_id) == 0
    query = urlencode(
        {
            "integration_id": integration_id,
            "status": "dead_letter",
            "sort": "oldest",
            "limit": 1,
        }
    )
    page = lab.request("GET", f"/events?{query}", role="viewer")
    assert page["total"] == 2 and [row["id"] for row in page["items"]] == [invalid_id]
    second_page = lab.request("GET", f"/events?{query}&offset=1", role="viewer")
    assert [row["id"] for row in second_page["items"]] == [timeout_id]
    search = urlencode({"search": timed_out["correlation_id"]})
    result = lab.request("GET", f"/events?{search}", role="viewer")
    assert result["total"] == 1 and result["items"][0]["id"] == timeout_id

    reason = f"Synthetic QA run {run_id} cleared timeout"
    replay_path = f"/events/{timeout_id}/retry"
    replay = {"reason": reason, "clear_simulation": True}
    lab.request("POST", replay_path, role="viewer", data=replay, status=403)
    accepted = lab.request(
        "POST", replay_path, role="operator", data=replay, status=202
    )
    assert accepted["id"] == timeout_id
    lab.request("POST", replay_path, role="operator", data=replay, status=409)
    recovered = lab.wait_for(timeout_id, "succeeded")
    assert recovered["correlation_id"] == timed_out["correlation_id"]
    assert recovered["attempts"][:2] == timed_out["attempts"]
    assert attempts(recovered)[-1] == ("succeeded", 200) and effects(timeout_id) == 1
    audit = lab.request("GET", "/audit?limit=100", role="admin")
    assert any(
        row["actor"] == "operator"
        and row["action"] == "event.replayed"
        and row["target_id"] == timeout_id
        and row["detail"] == reason
        for row in audit["items"]
    )
    print(
        "PASS E | retry budget exhausted, operator replay retained identity and history, audit recorded"
    )

    identical = submission("duplicate", "success")
    idempotency_key = f"qa-{run_id}"

    def duplicate_submit(_):
        return lab.request(
            "POST",
            "/events",
            role="operator",
            data=identical,
            key=idempotency_key,
            status=202,
        )["id"]

    with ThreadPoolExecutor(max_workers=4) as executor:
        ids = set(executor.map(duplicate_submit, range(8)))
    assert len(ids) == 1
    duplicate_id = ids.pop()
    lab.request(
        "POST",
        "/events",
        role="operator",
        data=submission("conflict", "success"),
        key=idempotency_key,
        status=409,
    )
    assert attempts(lab.wait_for(duplicate_id, "succeeded")) == [("succeeded", 200)]
    assert effects(duplicate_id) == 1
    print(
        "PASS F | eight concurrent duplicate submissions produced one event and effect; conflict returned 409"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument(
        "--credentials", type=Path, default=Path(".syncops/credentials.json")
    )
    parser.add_argument("--database", type=Path, default=Path(".syncops/syncops.db"))
    args = parser.parse_args()
    origin = urlsplit(args.base_url)
    if (
        origin.scheme != "http"
        or origin.hostname != "127.0.0.1"
        or origin.netloc != f"127.0.0.1:{origin.port}"
        or origin.path not in {"", "/"}
        or origin.query
        or origin.fragment
    ):
        parser.error(
            "--base-url must be an HTTP origin with an explicit IPv4 loopback port"
        )

    passwords = json.loads(args.credentials.read_text(encoding="utf-8"))
    db_uri = f"{args.database.resolve(strict=True).as_uri()}?mode=ro"
    run_id = uuid4().hex[:8]
    lab = Lab(args.base_url.rstrip("/"))
    integration = None
    try:
        lab.request("GET", "/overview", status=401)
        for role in ("admin", "operator", "viewer"):
            lab.login(role, passwords[role])
        lab.request("GET", "/overview", role="viewer")
        for role in ("viewer", "operator"):
            lab.request("GET", "/audit", role=role, status=403)
        config = {
            "name": f"Synthetic QA {run_id}",
            "description": "Isolated integration for the native HTTP acceptance suite.",
            "source": "crm",
            "destination": "erp",
            "timeout_seconds": 0.75,
            "max_attempts": 2,
            "retry_base_seconds": 0.7,
        }
        lab.request("POST", "/integrations", role="operator", data=config, status=403)
        integration = lab.request(
            "POST", "/integrations", role="admin", data=config, status=201
        )
        lab.request(
            "POST",
            "/events",
            role="viewer",
            status=403,
            data={
                "integration_id": integration["id"],
                "event_type": "company.created",
                "payload": {"name": "Synthetic QA"},
            },
        )
        assert any(
            item["id"] == integration["id"]
            for item in lab.request("GET", "/integrations", role="viewer")
        )
        print(
            "PASS RBAC | anonymous reads, viewer writes and operator administration rejected"
        )
        with closing(sqlite3.connect(db_uri, uri=True)) as db:
            verify_deliveries(lab, integration, db, run_id)
    finally:
        if integration:
            lab.request(
                "PATCH",
                f"/integrations/{integration['id']}",
                role="admin",
                data={"enabled": False},
            )
        for role in tuple(lab.sessions):
            lab.logout(role)
    print(
        f"PASS SESSION | three sessions revoked. Synthetic run {run_id} retained for review."
    )


if __name__ == "__main__":
    main()
