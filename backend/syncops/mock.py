import hmac
import os
import time
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .auth import Db
from .http import harden_http
from .models import MockOperation
from .schemas import MockInput, System

app = FastAPI(title="SyncOps mock enterprise systems", docs_url=None, redoc_url=None, openapi_url=None)
harden_http(app, maximum=73728)


@app.get("/healthz")
def healthz():
    return {"status": "alive"}


@app.get("/readyz")
def readyz(db: Db):
    if not os.getenv("SYNCOPS_MOCK_TOKEN"):
        raise HTTPException(503, "Missing internal authentication")
    try:
        db.scalar(select(MockOperation.operation_id).limit(1))
    except SQLAlchemyError as error:
        raise HTTPException(503, "Database is unavailable") from error
    return {"status": "ready"}


def validate_token(actual: str | None):
    expected = os.getenv("SYNCOPS_MOCK_TOKEN")
    if (
        not expected
        or not actual
        or not hmac.compare_digest(actual.encode(), f"Bearer {expected}".encode())
    ):
        raise HTTPException(401, "Internal authentication required")


def report_operation(operation: MockOperation, duplicate: bool) -> dict:
    return {"operation_id": operation.operation_id, "duplicate": duplicate}


@app.post("/internal/{destination}/deliver")
def deliver(
    destination: System,
    submission: MockInput,
    db: Db,
    authorization: Annotated[str | None, Header(max_length=300)] = None,
):
    validate_token(authorization)
    key = (destination, str(submission.event_id))
    existing = db.get(MockOperation, key)
    if existing:
        return report_operation(existing, True)
    db.rollback()
    if submission.latency_ms:
        time.sleep(submission.latency_ms / 1000)
    inject_fault = submission.failure_count == 0 or submission.attempt <= submission.failure_count
    if inject_fault:
        if submission.scenario.startswith("http_"):
            status = int(submission.scenario.removeprefix("http_"))
            headers = {"Retry-After": "2"} if status == 429 else None
            return JSONResponse(
                {"detail": "Simulated destination failure"}, status_code=status, headers=headers
            )
        if submission.scenario == "timeout":
            time.sleep(submission.timeout_seconds + 0.5)
            return JSONResponse({"detail": "Simulated timeout"}, status_code=504)
        if submission.scenario == "temporary_outage":
            return JSONResponse({"detail": "Simulated outage"}, status_code=503)
        if submission.scenario == "invalid_response":
            return PlainTextResponse("Simulated invalid destination response")

    operation = MockOperation(
        destination=destination,
        event_id=key[1],
        event_type=submission.event_type,
        payload=submission.payload,
    )
    try:
        db.add(operation)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(MockOperation, key)
        if existing is None:
            raise
        return report_operation(existing, True)
    return report_operation(operation, False)
