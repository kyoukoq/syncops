from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Attempt, Audit, Event, Integration


def timestamp(value: float | None) -> str | None:
    return (
        datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")
        if value is not None
        else None
    )


def format_event(event: Event) -> dict:
    return {
        "id": event.id,
        "correlation_id": event.correlation_id,
        "integration_id": event.integration_id,
        "integration_name": event.integration_name,
        "event_type": event.event_type,
        "status": event.status,
        "source": event.source,
        "destination": event.destination,
        "attempt_count": event.attempt_count,
        "http_status": event.http_status,
        "duration_ms": event.duration_ms,
        "error": event.error,
        "created_at": timestamp(event.created_at),
        "updated_at": timestamp(event.updated_at),
        "next_retry_at": timestamp(event.next_retry_at),
    }


def format_attempt(attempt: Attempt) -> dict:
    return {
        "number": attempt.number,
        "status": attempt.status,
        "started_at": timestamp(attempt.started_at),
        "finished_at": timestamp(attempt.finished_at),
        "http_status": attempt.http_status,
        "duration_ms": attempt.duration_ms,
        "error": attempt.error,
    }


def format_audit(entry: Audit) -> dict:
    return {
        "id": entry.id,
        "actor": entry.actor,
        "action": entry.action,
        "target_id": entry.target_id,
        "detail": entry.detail,
        "created_at": timestamp(entry.created_at),
    }


def integration_data(integration: Integration, latest: str | None) -> dict:
    health = "idle"
    if not integration.enabled:
        health = "disabled"
    elif latest == "succeeded":
        health = "healthy"
    elif latest in {"retry_scheduled", "dead_letter"}:
        health = "degraded"
    return {
        "id": integration.id,
        "name": integration.name,
        "description": integration.description,
        "source": integration.source,
        "destination": integration.destination,
        "enabled": integration.enabled,
        "timeout_seconds": integration.timeout_seconds,
        "max_attempts": integration.max_attempts,
        "retry_base_seconds": integration.retry_base_seconds,
        "health": health,
    }


OBSERVED = ("succeeded", "retry_scheduled", "dead_letter")


def all_integrations(db: Session) -> list[dict]:
    ranked = (
        select(
            Event.integration_id,
            Event.status,
            func.row_number()
            .over(
                partition_by=Event.integration_id,
                order_by=(Event.updated_at.desc(), Event.id.desc()),
            )
            .label("rank"),
        )
        .where(Event.status.in_(OBSERVED))
        .subquery()
    )
    rows = db.execute(
        select(Integration, ranked.c.status)
        .outerjoin(ranked, (ranked.c.integration_id == Integration.id) & (ranked.c.rank == 1))
        .order_by(Integration.name)
    )
    return [integration_data(integration, latest) for integration, latest in rows]


def one_integration(db: Session, integration: Integration) -> dict:
    latest = db.scalar(
        select(Event.status)
        .where(Event.integration_id == integration.id, Event.status.in_(OBSERVED))
        .order_by(Event.updated_at.desc(), Event.id.desc())
        .limit(1)
    )
    return integration_data(integration, latest)
