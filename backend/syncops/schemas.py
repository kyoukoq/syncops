from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

System = Literal["crm", "erp", "tms"]
EventType = Literal[
    "company.created",
    "contact.created",
    "customer.updated",
    "account.synced",
    "order.created",
    "shipment.created",
    "shipment.updated",
]
Status = Literal["queued", "processing", "retry_scheduled", "succeeded", "dead_letter"]
Scenario = Literal[
    "success",
    "http_400",
    "http_401",
    "http_429",
    "http_500",
    "http_503",
    "timeout",
    "temporary_outage",
    "invalid_response",
    "http_422",
    "http_403",
    "http_404",
    "http_409",
    "http_502",
    "http_504",
]
Name = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[^\x00]+$")]
Description = Annotated[str, Field(max_length=600, pattern=r"^[^\x00]*$")]
Timeout = Annotated[float, Field(ge=0.2, le=15)]
Attempts = Annotated[int, Field(ge=1, le=12)]
Backoff = Annotated[float, Field(ge=0.2, le=60)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class IntegrationInput(Input):
    name: Name
    description: Description = ""
    source: System
    destination: System
    enabled: bool = True
    timeout_seconds: Timeout = 2
    max_attempts: Attempts = 4
    retry_base_seconds: Backoff = 1


class IntegrationPatch(Input):
    name: Name | None = None
    description: Description | None = None
    source: System | None = None
    destination: System | None = None
    enabled: bool | None = None
    timeout_seconds: Timeout | None = None
    max_attempts: Attempts | None = None
    retry_base_seconds: Backoff | None = None


class WebhookInput(Input):
    event_type: EventType
    payload: dict[str, JsonValue] = Field(max_length=100)


class EventInput(WebhookInput):
    integration_id: UUID
    scenario: Scenario = "success"
    failure_count: int | None = Field(default=None, ge=0, le=50)
    latency_ms: int = Field(default=0, ge=0, le=10000)


class RetryInput(Input):
    reason: str = Field(min_length=1, max_length=300, pattern=r"^[^\x00]+$")
    clear_simulation: bool = True


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64, pattern=r"^[^\x00]+$")
    password: str = Field(min_length=1, max_length=256)


class MockInput(WebhookInput):
    event_id: UUID
    correlation_id: UUID
    scenario: Scenario
    failure_count: int = Field(ge=0, le=50)
    latency_ms: int = Field(ge=0, le=10000)
    attempt: int = Field(ge=1)
    timeout_seconds: Timeout


class UserView(BaseModel):
    username: str
    role: Literal["admin", "operator", "viewer"]


class SessionView(BaseModel):
    token: str
    user: UserView


class IntegrationView(IntegrationInput):
    id: UUID
    health: Literal["healthy", "degraded", "idle", "disabled"]


class EventView(BaseModel):
    id: UUID
    correlation_id: UUID
    integration_id: UUID
    integration_name: str
    event_type: EventType
    status: Status
    source: System
    destination: System
    attempt_count: int
    http_status: int | None
    duration_ms: float | None
    error: str | None
    created_at: str
    updated_at: str
    next_retry_at: str | None


class AttemptView(BaseModel):
    number: int
    status: str
    started_at: str
    finished_at: str | None
    http_status: int | None
    duration_ms: float | None
    error: str | None


class AuditView(BaseModel):
    id: UUID
    actor: str
    action: str
    target_id: str
    detail: str
    created_at: str


class EventDetailView(EventView):
    attempts: list[AttemptView]
    audit: list[AuditView]


class EventPage(BaseModel):
    items: list[EventView]
    total: int


class AuditPage(BaseModel):
    items: list[AuditView]
    total: int


class ActivityView(BaseModel):
    label: str
    succeeded: int
    failed: int
    pending: int


class OverviewView(BaseModel):
    total_events: int
    succeeded: int
    dead_letters: int
    success_rate: float | None
    avg_latency_ms: float | None
    active_integrations: int
    unhealthy_integrations: int
    pending_retries: int
    queue_depth: int
    activity: list[ActivityView]
    integrations: list[IntegrationView]
    recent_events: list[EventView]


class HealthView(BaseModel):
    status: Literal["healthy", "degraded"]
    database: Literal["online"]
    worker: Literal["online", "offline"]
