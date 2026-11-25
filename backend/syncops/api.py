import hmac
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .auth import (
    Actor,
    Admin,
    Db,
    Operator,
    bootstrap,
    current_session,
    issue_session,
)
from .events import replay_event, submit_event
from .http import harden_http
from .models import Attempt, Audit, AuthSession, Event, Integration, User, WorkerHeartbeat
from .presentation import all_integrations, format_attempt, format_audit, format_event, one_integration
from .schemas import (
    AuditPage,
    EventDetailView,
    EventInput,
    EventPage,
    EventView,
    HealthView,
    IntegrationInput,
    IntegrationPatch,
    IntegrationView,
    LoginInput,
    OverviewView,
    RetryInput,
    SessionView,
    Status,
    UserView,
    WebhookInput,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    bootstrap()
    yield


app = FastAPI(
    title="SyncOps",
    version="0.2.0",
    description="Integration monitoring and recovery for synthetic CRM, ERP and TMS systems.",
    lifespan=lifespan,
)
harden_http(app)
api = APIRouter(prefix="/api/v1")
IdempotencyKey = Annotated[str | None, Header(max_length=128, min_length=1, pattern=r"^[!-~]+$")]


def user_data(user: User) -> dict:
    return {"username": user.username, "role": user.role}


@api.post("/auth/login", response_model=SessionView)
def login(request: LoginInput, db: Db):
    token, user = issue_session(db, request.username, request.password)
    db.add(
        Audit(actor=user.username, action="auth.login", target_id=user.username, detail="Session issued")
    )
    db.commit()
    return {"token": token, "user": user_data(user)}


@api.get("/auth/me", response_model=UserView)
def me(user: Actor):
    return user_data(user)


@api.post("/auth/logout", status_code=204)
def logout(db: Db, auth: Annotated[tuple[User, AuthSession], Depends(current_session)]):
    user, session = auth
    db.delete(session)
    db.add(
        Audit(
            actor=user.username, action="auth.logout", target_id=user.username, detail="Session revoked"
        )
    )
    db.commit()


@api.get("/integrations", response_model=list[IntegrationView])
def integrations(db: Db, _user: Actor):
    return all_integrations(db)


def save_integration(db, integration, actor: str, action: str):
    try:
        db.flush()
        db.add(Audit(actor=actor, action=action, target_id=integration.id, detail=integration.name))
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "An integration with this name already exists") from error
    return one_integration(db, integration)


@api.post("/integrations", status_code=201, response_model=IntegrationView)
def create_integration(request: IntegrationInput, db: Db, user: Admin):
    integration = Integration(**request.model_dump())
    db.add(integration)
    return save_integration(db, integration, user.username, "integration.created")


@api.patch("/integrations/{integration_id}", response_model=IntegrationView)
def patch_integration(integration_id: UUID, request: IntegrationPatch, db: Db, user: Admin):
    integration = db.get(Integration, str(integration_id))
    if integration is None:
        raise HTTPException(404, "Integration not found")
    for field, value in request.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(422, f"{field} cannot be null")
        setattr(integration, field, value)
    return save_integration(db, integration, user.username, "integration.updated")


@api.post("/events", status_code=202, response_model=EventView)
def create_event(request: EventInput, db: Db, user: Operator, idempotency_key: IdempotencyKey = None):
    return format_event(submit_event(db, request, idempotency_key, user.username))


@api.post("/webhooks/{integration_id}", status_code=202, response_model=EventView)
def webhook(
    integration_id: UUID,
    request: WebhookInput,
    db: Db,
    idempotency_key: IdempotencyKey = None,
    x_webhook_secret: Annotated[str | None, Header(max_length=256)] = None,
):
    expected = os.getenv("SYNCOPS_WEBHOOK_SECRET")
    if not expected:
        raise HTTPException(404, "Webhook ingestion is disabled")
    if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret.encode(), expected.encode()):
        raise HTTPException(401, "Webhook authentication required")
    if idempotency_key is None:
        raise HTTPException(422, "Idempotency-Key is required")
    submission = EventInput(integration_id=integration_id, **request.model_dump())
    return format_event(submit_event(db, submission, idempotency_key, "webhook"))


@api.get("/events", response_model=EventPage)
def list_events(
    db: Db,
    _user: Actor,
    status: Status | None = None,
    integration_id: UUID | None = None,
    search: Annotated[str, Query(max_length=100, pattern=r"^[^\x00]*$")] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    sort: Literal["newest", "oldest"] = "newest",
):
    filters = []
    if status:
        filters.append(Event.status == status)
    if integration_id:
        filters.append(Event.integration_id == str(integration_id))
    if needle := search.strip().lower():
        filters.append(
            or_(
                *[
                    func.lower(column).contains(needle, autoescape=True)
                    for column in (
                        Event.id,
                        Event.correlation_id,
                        Event.integration_name,
                        Event.event_type,
                        Event.error,
                    )
                ]
            )
        )
    ordering = (
        (Event.created_at.desc(), Event.id.desc()) if sort == "newest" else (Event.created_at, Event.id)
    )
    total = db.scalar(select(func.count()).select_from(Event).where(*filters))
    items = db.scalars(select(Event).where(*filters).order_by(*ordering).limit(limit).offset(offset))
    return {"total": total, "items": [format_event(item) for item in items]}


@api.get("/events/{event_id}", response_model=EventDetailView)
def event_detail(event_id: UUID, db: Db, user: Actor):
    event = db.get(Event, str(event_id))
    if event is None:
        raise HTTPException(404, "Event not found")
    attempts = db.scalars(select(Attempt).where(Attempt.event_id == event.id).order_by(Attempt.number))
    entries = []
    if user.role == "admin":
        entries = [
            format_audit(entry)
            for entry in db.scalars(
                select(Audit).where(Audit.target_id == event.id).order_by(Audit.created_at, Audit.id)
            )
        ]
    return {
        **format_event(event),
        "attempts": [format_attempt(attempt) for attempt in attempts],
        "audit": entries,
    }


@api.post("/events/{event_id}/retry", status_code=202, response_model=EventView)
def retry_event(event_id: UUID, request: RetryInput, db: Db, user: Operator):
    return format_event(replay_event(db, str(event_id), request, user.username))


@api.get("/audit", response_model=AuditPage)
def audit_entries(
    db: Db,
    _user: Admin,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
):
    entries = db.scalars(
        select(Audit).order_by(Audit.created_at.desc(), Audit.id).offset(offset).limit(limit)
    )
    return {
        "total": db.scalar(select(func.count()).select_from(Audit)),
        "items": [format_audit(entry) for entry in entries],
    }


def status_counts(db: Db):
    return dict(db.execute(select(Event.status, func.count()).group_by(Event.status)).all())


def activity(db: Db) -> list[dict]:
    bucket_size = 4 * 3600
    end = (int(time.time()) // bucket_size + 1) * bucket_size
    starts = list(range(end - 6 * bucket_size, end, bucket_size))
    bucket = case(
        *[(Event.created_at < start + bucket_size, index) for index, start in enumerate(starts)]
    ).label("bucket")
    rows = db.execute(
        select(bucket, Event.status, func.count())
        .where(Event.created_at >= starts[0], Event.created_at < end)
        .group_by(bucket, Event.status)
    )
    values = [
        {
            "label": datetime.fromtimestamp(start, UTC).strftime("%H:%M"),
            "succeeded": 0,
            "failed": 0,
            "pending": 0,
        }
        for start in starts
    ]
    for index, status, count in rows:
        category = {"succeeded": "succeeded", "dead_letter": "failed"}.get(status, "pending")
        values[index][category] += count
    return values


@api.get("/overview", response_model=OverviewView)
def overview(db: Db, _user: Actor):
    counts = status_counts(db)
    succeeded = counts.get("succeeded", 0)
    dead_letters = counts.get("dead_letter", 0)
    totals = succeeded + dead_letters
    integrations = all_integrations(db)
    recent = db.scalars(select(Event).order_by(Event.created_at.desc(), Event.id.desc()).limit(7))
    return {
        "total_events": sum(counts.values()),
        "succeeded": succeeded,
        "dead_letters": dead_letters,
        "success_rate": round(100 * succeeded / totals, 2) if totals else None,
        "avg_latency_ms": db.scalar(select(func.avg(Attempt.duration_ms))),
        "active_integrations": sum(item["enabled"] for item in integrations),
        "unhealthy_integrations": sum(item["health"] == "degraded" for item in integrations),
        "pending_retries": counts.get("retry_scheduled", 0),
        "queue_depth": sum(
            counts.get(status, 0) for status in ("queued", "processing", "retry_scheduled")
        ),
        "activity": activity(db),
        "integrations": integrations,
        "recent_events": [format_event(event) for event in recent],
    }


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "alive"}


@app.get("/readyz", include_in_schema=False)
def readyz(db: Db):
    try:
        db.scalar(select(User.username).limit(1))
    except SQLAlchemyError as error:
        raise HTTPException(503, "Database is unavailable") from error
    return {"status": "ready"}


@api.get("/health", response_model=HealthView)
def health(db: Db, _user: Actor):
    latest = db.scalar(select(func.max(WorkerHeartbeat.updated_at)))
    worker = "online" if latest is not None and time.time() - latest < 35 else "offline"
    return {
        "status": "healthy" if worker == "online" else "degraded",
        "database": "online",
        "worker": worker,
    }


@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def metrics(db: Db):
    counts = status_counts(db)
    latest = db.scalar(select(func.max(WorkerHeartbeat.updated_at))) or 0
    attempt_count = db.scalar(select(func.count()).select_from(Attempt))
    lines = [
        "# HELP syncops_events Current persisted events by status.",
        "# TYPE syncops_events gauge",
        *[
            f'syncops_events{{status="{status}"}} {counts.get(status, 0)}'
            for status in ("queued", "processing", "retry_scheduled", "succeeded", "dead_letter")
        ],
        "# HELP syncops_attempts_total Count of recorded worker attempts.",
        "# TYPE syncops_attempts_total counter",
        f"syncops_attempts_total {attempt_count}",
        "# HELP syncops_worker_heartbeat_timestamp_seconds Time of most recent worker heartbeat.",
        "# TYPE syncops_worker_heartbeat_timestamp_seconds gauge",
        f"syncops_worker_heartbeat_timestamp_seconds {latest}",
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


app.include_router(api)
