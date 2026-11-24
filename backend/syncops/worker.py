import argparse
import json
import os
import random
import signal
import threading
import time
from dataclasses import dataclass
from datetime import UTC
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import and_, func, or_, select, update

from .database import Session
from .models import Attempt, Audit, Event, WorkerHeartbeat, identifier

TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
SYSTEMS = {"crm", "erp", "tms"}


@dataclass(frozen=True)
class Result:
    http_status: int | None = None
    error: str | None = None
    retryable: bool = False
    retry_after: float = 0


def retry_after_seconds(value: str | None, now: float) -> float:
    if not value:
        return 0
    value = value.strip()
    if value.isascii() and value.isdecimal() and len(value) <= 12:
        return float(value)
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(0, parsed.timestamp() - now)
    except (ValueError, TypeError, OverflowError, OSError):
        return 0


def next_delay(event: Event, retry_after: float) -> float:
    ceiling = min(300.0, event.retry_base_seconds * 2 ** (event.budget_attempts - 1))
    return max(random.uniform(0.5 * ceiling, ceiling), retry_after)


def claim(now: float | None = None) -> Event | None:
    now = time.time() if now is None else now
    with Session.begin() as db:
        event = db.scalar(
            select(Event)
            .where(
                or_(
                    Event.status == "queued",
                    and_(Event.status == "retry_scheduled", Event.next_retry_at <= now),
                    and_(Event.status == "processing", Event.lease_until <= now),
                )
            )
            .order_by(func.coalesce(Event.lease_until, Event.next_retry_at, Event.created_at), Event.id)
            .limit(1)
        )
        if event is None:
            return None
        recovering = event.status == "processing"
        number = event.attempt_count + 1
        lease = identifier()
        saved = db.execute(
            update(Event)
            .where(Event.id == event.id, Event.revision == event.revision)
            .values(
                status="processing",
                revision=event.revision + 1,
                lease_token=lease,
                lease_until=now + 5 * event.timeout_seconds + 5,
                attempt_count=number,
                budget_attempts=event.budget_attempts + int(not recovering),
                next_retry_at=None,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if saved.rowcount != 1:
            return None
        if recovering:
            db.execute(
                update(Attempt)
                .where(
                    Attempt.event_id == event.id,
                    Attempt.number == number - 1,
                    Attempt.status == "processing",
                )
                .values(status="interrupted", finished_at=now, error="Worker lease expired")
            )
        db.add(Attempt(event_id=event.id, number=number, status="processing", started_at=now))
        db.refresh(event)
        return event


def process(
    client: httpx.Client,
    origin: str,
    token: str,
    event: Event,
) -> Result:
    if event.destination not in SYSTEMS:
        return Result(error="Unknown simulated destination")
    try:
        with client.stream(
            "POST",
            f"{origin}/internal/{event.destination}/deliver",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "event_id": event.id,
                "correlation_id": event.correlation_id,
                "event_type": event.event_type,
                "payload": event.payload,
                "scenario": event.scenario,
                "failure_count": event.failure_count,
                "latency_ms": event.latency_ms,
                "attempt": event.budget_attempts,
                "timeout_seconds": event.timeout_seconds,
            },
            timeout=event.timeout_seconds,
        ) as response:
            status = response.status_code
            if status in TRANSIENT_STATUS:
                delay = retry_after_seconds(response.headers.get("Retry-After"), time.time())
                return Result(status, f"Destination returned HTTP {status}", True, delay)
            if not 200 <= status < 300:
                return Result(status, f"Destination returned HTTP {status}")
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > 16384:
                    return Result(status, "Destination returned an oversized response")
            try:
                body = json.loads(content)
                UUID(body["operation_id"])
            except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
                return Result(status, "Destination returned an invalid response")
            return Result(status)
    except httpx.TimeoutException:
        return Result(error="Destination timed out", retryable=True)
    except httpx.TransportError:
        return Result(error="Destination connection failed", retryable=True)
    except httpx.DecodingError:
        return Result(error="Destination response could not be decoded")


def finish(event: Event, result: Result, duration_ms: float, now: float | None = None) -> str | None:
    now = time.time() if now is None else now
    status = "succeeded"
    next_retry = None
    if result.error is not None:
        status = "dead_letter"
        if result.retryable and event.budget_attempts < event.max_attempts:
            status = "retry_scheduled"
            next_retry = now + next_delay(event, result.retry_after)
    with Session.begin() as db:
        saved = db.execute(
            update(Event)
            .where(
                Event.id == event.id,
                Event.status == "processing",
                Event.lease_token == event.lease_token,
                Event.lease_until > now,
            )
            .values(
                status=status,
                http_status=result.http_status,
                duration_ms=duration_ms,
                error=result.error,
                next_retry_at=next_retry,
                lease_token=None,
                lease_until=None,
                updated_at=now,
                revision=Event.revision + 1,
            )
        )
        if saved.rowcount != 1:
            return None
        db.execute(
            update(Attempt)
            .where(Attempt.event_id == event.id, Attempt.number == event.attempt_count)
            .values(
                status=status,
                finished_at=now,
                duration_ms=duration_ms,
                http_status=result.http_status,
                error=result.error,
            )
        )
        if status == "dead_letter":
            db.add(
                Audit(
                    actor="worker",
                    action="event.dead_letter",
                    target_id=event.id,
                    detail=result.error,
                )
            )
    return status


def log(message: str, **fields) -> None:
    print(
        json.dumps({"component": "worker", "message": message, "timestamp": time.time(), **fields}),
        flush=True,
    )


def run() -> None:
    origin = os.getenv("SYNCOPS_MOCK_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
    uri = urlsplit(origin)
    if (
        uri.scheme not in {"http", "https"}
        or not uri.hostname
        or any((uri.username, uri.password, uri.path, uri.query, uri.fragment))
    ):
        raise SystemExit("SYNCOPS_MOCK_BASE_URL must be a trusted HTTP(S) origin")
    token = os.getenv("SYNCOPS_MOCK_TOKEN")
    if not token:
        raise SystemExit("Set SYNCOPS_MOCK_TOKEN for worker-to-mock authentication")

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    worker_id = identifier()
    next_heartbeat = 0.0
    log("started", worker_id=worker_id)
    try:
        with httpx.Client(follow_redirects=False, trust_env=False) as client:
            while not stop.is_set():
                if time.monotonic() >= next_heartbeat:
                    with Session.begin() as db:
                        db.merge(WorkerHeartbeat(id=worker_id, updated_at=time.time()))
                    next_heartbeat = time.monotonic() + 5
                event = claim()
                if event is None:
                    stop.wait(0.25)
                    continue
                started = time.monotonic()
                result = process(client, origin, token, event)
                status = finish(event, result, round((time.monotonic() - started) * 1000, 2))
                log(
                    "attempt_finished",
                    event_id=event.id,
                    correlation_id=event.correlation_id,
                    attempt=event.attempt_count,
                    status=status or "lease_lost",
                )
    finally:
        with Session.begin() as db:
            heartbeat = db.get(WorkerHeartbeat, worker_id)
            if heartbeat:
                db.delete(heartbeat)
        log("stopped", worker_id=worker_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SyncOps event worker")
    parser.add_argument("--check", action="store_true", help="Check the latest persisted heartbeat")
    args = parser.parse_args()
    if args.check:
        with Session() as db:
            latest = db.scalar(select(func.max(WorkerHeartbeat.updated_at)))
        raise SystemExit(0 if latest and time.time() - latest < 35 else 1)
    run()


if __name__ == "__main__":
    main()
