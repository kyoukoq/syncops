import hashlib
import json
import time

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Audit, Event, Integration
from .schemas import EventInput, RetryInput


def submit_event(db: Session, request: EventInput, key: str | None, actor: str) -> Event:
    query = select(Event).where(
        Event.integration_id == str(request.integration_id),
        Event.idempotency_key == key,
    )
    failure_count = request.failure_count
    if failure_count is None:
        failure_count = int(request.scenario == "temporary_outage")
    content = {
        "event_type": request.event_type,
        "payload": request.payload,
        "scenario": request.scenario,
        "failure_count": failure_count,
        "latency_ms": request.latency_ms,
    }
    try:
        canonical = json.dumps(content, allow_nan=False, sort_keys=True, separators=(",", ":"))
        request_hash = hashlib.sha256(canonical.encode()).hexdigest()
    except (ValueError, RecursionError) as error:
        raise HTTPException(422, "Payload must be a finite JSON value") from error
    if key is not None:
        existing = db.scalar(query)
        if existing:
            return verify_duplicate(existing, request_hash)
    integration = db.get(Integration, str(request.integration_id))
    if integration is None:
        raise HTTPException(404, "Integration not found")
    if not integration.enabled:
        raise HTTPException(409, "Integration is disabled")
    event = Event(
        integration_id=integration.id,
        integration_name=integration.name,
        source=integration.source,
        destination=integration.destination,
        timeout_seconds=integration.timeout_seconds,
        max_attempts=integration.max_attempts,
        retry_base_seconds=integration.retry_base_seconds,
        idempotency_key=key,
        request_hash=request_hash,
        **content,
    )
    try:
        db.add(event)
        db.flush()
        db.add(Audit(actor=actor, action="event.received", target_id=event.id, detail=event.event_type))
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(query) if key is not None else None
        if existing is None:
            raise
        return verify_duplicate(existing, request_hash)
    return event


def verify_duplicate(existing: Event, supplied_hash: str) -> Event:
    if existing.request_hash != supplied_hash:
        raise HTTPException(409, "Idempotency key already used for a different request")
    return existing


def replay_event(db: Session, event_id: str, request: RetryInput, actor: str) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    integration = db.get(Integration, event.integration_id)
    if not integration.enabled:
        raise HTTPException(409, "Integration is disabled")
    changes = {
        "status": "queued",
        "budget_attempts": 0,
        "next_retry_at": None,
        "error": None,
        "http_status": None,
        "duration_ms": None,
        "updated_at": time.time(),
        "revision": Event.revision + 1,
    }
    if request.clear_simulation:
        changes.update(scenario="success", failure_count=0, latency_ms=0)
    claimed = db.execute(
        update(Event).where(Event.id == event_id, Event.status == "dead_letter").values(**changes)
    )
    if claimed.rowcount != 1:
        raise HTTPException(409, "Only a dead-letter event can be requeued")
    db.add(Audit(actor=actor, action="event.replayed", target_id=event.id, detail=request.reason))
    db.commit()
    db.refresh(event)
    return event
