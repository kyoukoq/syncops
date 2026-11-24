import time
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def identifier() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(64), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(16))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(ForeignKey("users.username"), index=True)
    expires_at: Mapped[float] = mapped_column(Float, index=True)


class Integration(Base):
    __tablename__ = "integrations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(600))
    source: Mapped[str] = mapped_column(String(8))
    destination: Mapped[str] = mapped_column(String(8))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timeout_seconds: Mapped[float] = mapped_column(Float)
    max_attempts: Mapped[int] = mapped_column(Integer)
    retry_base_seconds: Mapped[float] = mapped_column(Float)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("integration_id", "idempotency_key", name="uq_event_idempotency"),
        Index("ix_events_queue", "status", "next_retry_at", "lease_until"),
        Index("ix_events_integration_created", "integration_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    correlation_id: Mapped[str] = mapped_column(String(36), default=identifier, index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("integrations.id"))
    integration_name: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(8))
    destination: Mapped[str] = mapped_column(String(8))
    timeout_seconds: Mapped[float] = mapped_column(Float)
    max_attempts: Mapped[int] = mapped_column(Integer)
    retry_base_seconds: Mapped[float] = mapped_column(Float)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    scenario: Mapped[str] = mapped_column(String(24))
    failure_count: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    budget_attempts: Mapped[int] = mapped_column(Integer, default=0)
    http_status: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)
    next_retry_at: Mapped[float | None] = mapped_column(Float)
    lease_until: Mapped[float | None] = mapped_column(Float)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer, default=0)


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("event_id", "number", name="uq_attempt_number"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[float] = mapped_column(Float)
    finished_at: Mapped[float | None] = mapped_column(Float)
    http_status: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(String(160))


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)


class MockOperation(Base):
    __tablename__ = "mock_operations"
    destination: Mapped[str] = mapped_column(String(8), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(36), default=identifier)
    event_type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    updated_at: Mapped[float] = mapped_column(Float)
