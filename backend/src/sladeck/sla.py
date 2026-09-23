from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import RequestPriority, RequestStatus

PRIORITY_FACTORS: dict[RequestPriority, float] = {
    RequestPriority.urgent: 0.25,
    RequestPriority.high: 0.5,
    RequestPriority.normal: 1.0,
    RequestPriority.low: 2.0,
}


@dataclass(frozen=True)
class SLADeadlines:
    first_response_due_at: datetime
    resolution_due_at: datetime


def _scaled_minutes(base_minutes: int, priority: RequestPriority) -> int:
    return max(1, round(base_minutes * PRIORITY_FACTORS[priority]))


def calculate_deadlines(
    created_at: datetime,
    priority: RequestPriority,
    first_response_minutes: int,
    resolution_minutes: int,
) -> SLADeadlines:
    if created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    if first_response_minutes <= 0 or resolution_minutes <= 0:
        raise ValueError("SLA durations must be positive")
    if resolution_minutes < first_response_minutes:
        raise ValueError("resolution SLA cannot be shorter than first-response SLA")

    return SLADeadlines(
        first_response_due_at=created_at
        + timedelta(minutes=_scaled_minutes(first_response_minutes, priority)),
        resolution_due_at=created_at
        + timedelta(minutes=_scaled_minutes(resolution_minutes, priority)),
    )


def calculate_sla_state(
    *,
    status: RequestStatus,
    created_at: datetime,
    first_response_due_at: datetime | None,
    first_responded_at: datetime | None,
    resolution_due_at: datetime | None,
    resolved_at: datetime | None,
    now: datetime | None = None,
) -> str:
    if status in {RequestStatus.resolved, RequestStatus.closed} or resolved_at is not None:
        return "completed"

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    active_due = (
        first_response_due_at
        if first_responded_at is None and first_response_due_at is not None
        else resolution_due_at
    )
    if active_due is None:
        return "healthy"

    if current >= active_due:
        return "breached"

    total_window = active_due - created_at
    warning_window = max(timedelta(minutes=15), total_window * 0.25)
    if active_due - current <= warning_window:
        return "warning"
    return "healthy"


def validate_status_transition(current: RequestStatus, target: RequestStatus) -> None:
    allowed: dict[RequestStatus, set[RequestStatus]] = {
        RequestStatus.open: {
            RequestStatus.in_progress,
            RequestStatus.waiting,
            RequestStatus.resolved,
        },
        RequestStatus.in_progress: {
            RequestStatus.open,
            RequestStatus.waiting,
            RequestStatus.resolved,
        },
        RequestStatus.waiting: {
            RequestStatus.open,
            RequestStatus.in_progress,
            RequestStatus.resolved,
        },
        RequestStatus.resolved: {
            RequestStatus.in_progress,
            RequestStatus.closed,
        },
        RequestStatus.closed: set(),
    }

    if target == current:
        return
    if target not in allowed[current]:
        raise ValueError(f"Invalid request status transition: {current.value} -> {target.value}")
