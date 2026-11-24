import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import httpx
import pytest
from conftest import MOCK_TOKEN, TEST_PASSWORD
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from syncops.database import Session
from syncops.mock import app as mock_app
from syncops.models import Event, MockOperation
from syncops.worker import claim, finish, process, retry_after_seconds


def authenticate(api, role="admin"):
    response = api.post("/api/v1/auth/login", json={"username": role, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def enqueue(api, headers, scenario="success", failure_count=0, key=None):
    integration = api.get("/api/v1/integrations", headers=headers).json()[0]
    if key is not None:
        headers = {**headers, "Idempotency-Key": key}
    return api.post(
        "/api/v1/events",
        headers=headers,
        json={
            "integration_id": integration["id"],
            "event_type": "company.created",
            "payload": {"name": "Fictional Logistics"},
            "scenario": scenario,
            "failure_count": failure_count,
        },
    )


def detail(api, headers, event_id):
    return api.get(f"/api/v1/events/{event_id}", headers=headers).json()


@pytest.fixture
def simulator(api):
    from contextlib import contextmanager

    with TestClient(mock_app) as mock_client:
        client = MagicMock()

        @contextmanager
        def simulate(method, _url, **kwargs):
            response = mock_client.request(
                method,
                _url.removeprefix("http://mock"),
                headers=kwargs["headers"],
                json=kwargs["json"],
            )
            yield response

        client.stream.side_effect = simulate
        yield client


def deliver(client, event):
    return process(client, "http://mock", MOCK_TOKEN, event)


def test_success_and_duplicate_key(api, simulator):
    headers = authenticate(api)
    first = enqueue(api, headers, key="company-42")
    duplicate = enqueue(api, headers, key="company-42")
    conflict = enqueue(api, headers, "http_500", key="company-42")
    assert first.status_code == duplicate.status_code == 202
    assert first.json()["id"] == duplicate.json()["id"]
    assert conflict.status_code == 409
    claimed = claim()
    assert claimed.id == first.json()["id"]
    assert finish(claimed, deliver(simulator, claimed), 10) == "succeeded"
    stored = detail(api, headers, claimed.id)
    assert stored["status"] == "succeeded"
    assert stored["attempts"][0]["http_status"] == 200
    assert "payload" not in stored
    overview = api.get("/api/v1/overview", headers=headers).json()
    assert overview["total_events"] == 1
    assert overview["succeeded"] == 1
    assert overview["success_rate"] == 100
    assert overview["queue_depth"] == 0
    assert overview["avg_latency_ms"] == 10
    assert sum(bucket["succeeded"] for bucket in overview["activity"]) == 1


@pytest.mark.parametrize("scenario,delay", [("http_503", 0), ("http_429", 2)])
def test_transient_delivery_retries_when_due(api, simulator, scenario, delay):
    headers = authenticate(api)
    submitted = enqueue(api, headers, scenario, failure_count=1)
    assert submitted.status_code == 202
    first = claim()
    now = time.time()
    assert finish(first, deliver(simulator, first), 10, now=now) == "retry_scheduled"
    assert claim(now=now + 0.01) is None
    with Session() as db:
        next_retry = db.get(Event, first.id).next_retry_at
    assert next_retry >= now + delay
    second = claim(now=next_retry + 0.01)
    assert finish(second, deliver(simulator, second), 12, now=next_retry + 0.05) == "succeeded"
    assert [item["status"] for item in detail(api, headers, second.id)["attempts"]] == [
        "retry_scheduled",
        "succeeded",
    ]


@pytest.mark.parametrize(
    "scenario,expected", [("http_400", 400), ("http_422", 422), ("invalid_response", 200)]
)
def test_permanent_errors_enter_dead_letter(api, simulator, scenario, expected):
    headers = authenticate(api)
    enqueue(api, headers, scenario)
    event = claim()
    assert finish(event, deliver(simulator, event), 4) == "dead_letter"
    stored = detail(api, headers, event.id)
    assert stored["attempt_count"] == 1
    assert stored["http_status"] == expected
    assert stored["next_retry_at"] is None


def test_exhaustion_replay_roles_and_audit(api, simulator):
    admin = authenticate(api)
    operator = authenticate(api, "operator")
    viewer = authenticate(api, "viewer")
    integration = api.get("/api/v1/integrations", headers=admin).json()[0]
    update = api.patch(
        f"/api/v1/integrations/{integration['id']}",
        headers=admin,
        json={"max_attempts": 1},
    )
    assert update.status_code == 200
    assert enqueue(api, viewer).status_code == 403
    enqueue(api, operator, "http_500")
    event = claim()
    assert finish(event, deliver(simulator, event), 25) == "dead_letter"
    route = f"/api/v1/events/{event.id}/retry"
    body = {"reason": "Mock dependency has recovered", "clear_simulation": True}
    assert api.post(route, headers=viewer, json=body).status_code == 403
    assert api.post(route, headers=operator, json=body).status_code == 202
    assert api.post(route, headers=operator, json=body).status_code == 409
    retry = claim()
    assert retry.id == event.id
    assert retry.attempt_count == 2
    assert finish(retry, deliver(simulator, retry), 17) == "succeeded"
    audit = api.get("/api/v1/audit", headers=admin).json()["items"]
    assert any(row["action"] == "event.replayed" and row["actor"] == "operator" for row in audit)
    assert api.get("/api/v1/audit", headers=operator).status_code == 403
    assert any(row["action"] == "event.replayed" for row in detail(api, admin, event.id)["audit"])
    assert detail(api, operator, event.id)["audit"] == []
    assert detail(api, viewer, event.id)["audit"] == []


def test_crashed_worker_does_not_duplicate_business_effect(api, simulator):
    headers = authenticate(api)
    enqueue(api, headers)
    crashed = claim()
    assert deliver(simulator, crashed).error is None
    reclaimed = claim(now=crashed.lease_until + 0.01)
    assert reclaimed.id == crashed.id
    assert reclaimed.lease_token != crashed.lease_token
    assert finish(crashed, deliver(simulator, crashed), 10, now=crashed.lease_until - 1) is None
    assert (
        finish(reclaimed, deliver(simulator, reclaimed), 10, now=crashed.lease_until + 0.02)
        == "succeeded"
    )
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(MockOperation)) == 1
    stored = detail(api, headers, crashed.id)
    assert [item["status"] for item in stored["attempts"]] == ["interrupted", "succeeded"]


def test_concurrent_ingress_and_claims(api):
    headers = authenticate(api)
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(lambda _: enqueue(api, headers, key="same-request"), range(8)))
        assert all(response.status_code == 202 for response in responses)
        assert len({response.json()["id"] for response in responses}) == 1
        claims = list(executor.map(lambda _: claim(), range(4)))
        assert sum(isinstance(result, Event) for result in claims) == 1


def test_transport_timeout_is_retryable(api):
    event = enqueue(api, authenticate(api))
    assert event.status_code == 202
    client = MagicMock(spec=httpx.Client)
    client.stream.side_effect = httpx.ReadTimeout("simulated timeout")
    result = deliver(client, claim())
    assert result.retryable
    assert result.http_status is None


def test_retry_after_supports_http_date():
    assert retry_after_seconds("Thu, 01 Jan 1970 00:02:00 GMT", 110) == 10
    assert retry_after_seconds("Thu, 01 Jan 1970 00:02:00 GMT", 121) == 0
    assert retry_after_seconds("5", 110) == 5
    assert retry_after_seconds("broken", 110) == 0
