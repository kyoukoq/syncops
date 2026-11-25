from conftest import TEST_PASSWORD


def login(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_session_logout(api):
    assert api.get("/api/v1/overview").status_code == 401
    response = api.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401
    headers = login(api)
    assert api.get("/api/v1/auth/me", headers=headers).json()["role"] == "admin"
    assert api.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert api.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_webhook_secret_and_idempotency(api, monkeypatch):
    headers = login(api)
    integration = api.get("/api/v1/integrations", headers=headers).json()[0]
    route = f"/api/v1/webhooks/{integration['id']}"
    payload = {"event_type": "company.created", "payload": {"customer": "Synthetic"}}
    custom_headers = {"X-Webhook-Secret": "only-for-tests", "Idempotency-Key": "order-42"}
    assert api.post(route, json=payload, headers=custom_headers).status_code == 404
    monkeypatch.setenv("SYNCOPS_WEBHOOK_SECRET", "only-for-tests")
    assert api.post(route, json=payload).status_code == 401
    assert (
        api.post(route, json=payload, headers={"X-Webhook-Secret": "only-for-tests"}).status_code == 422
    )
    event = api.post(route, json=payload, headers=custom_headers)
    assert event.status_code == 202
    assert api.post(route, json=payload, headers=custom_headers).json()["id"] == event.json()["id"]


def test_limits_and_no_credential_echo(api):
    invalid = "sensitive-placeholder-for-validation" * 10
    response = api.post("/api/v1/auth/login", json={"username": "admin", "password": invalid})
    assert response.status_code == 422
    assert invalid not in response.text
    response = api.post("/api/v1/auth/login", json={"username": "admin", "password": "A" * 70000})
    assert response.status_code == 413


def test_submit_shipment_creation(api):
    headers = {**login(api), "Idempotency-Key": "shipment-creation"}
    integrations = api.get("/api/v1/integrations", headers=headers).json()
    integration = next(item for item in integrations if item["source"] == "tms")
    response = api.post(
        "/api/v1/events",
        json={
            "integration_id": integration["id"],
            "event_type": "shipment.created",
            "payload": {"shipment": "LAB-S112"},
        },
        headers=headers,
    )
    assert response.status_code == 202
    event = api.get(f"/api/v1/events/{response.json()['id']}", headers=headers)
    assert event.json()["event_type"] == "shipment.created"
