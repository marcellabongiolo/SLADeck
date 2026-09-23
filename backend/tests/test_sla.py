from datetime import datetime, timedelta, timezone

import pytest

from sladeck.models import RequestPriority, RequestStatus
from sladeck.sla import calculate_deadlines, calculate_sla_state, validate_status_transition


def test_priority_changes_deadline_windows() -> None:
    created = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)

    urgent = calculate_deadlines(created, RequestPriority.urgent, 60, 480)
    normal = calculate_deadlines(created, RequestPriority.normal, 60, 480)
    low = calculate_deadlines(created, RequestPriority.low, 60, 480)

    assert urgent.first_response_due_at == created + timedelta(minutes=15)
    assert urgent.resolution_due_at == created + timedelta(minutes=120)
    assert normal.first_response_due_at == created + timedelta(minutes=60)
    assert normal.resolution_due_at == created + timedelta(minutes=480)
    assert low.first_response_due_at == created + timedelta(minutes=120)
    assert low.resolution_due_at == created + timedelta(minutes=960)


def test_sla_state_moves_from_healthy_to_warning_to_breached() -> None:
    created = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    first_due = created + timedelta(minutes=60)
    resolution_due = created + timedelta(hours=8)

    healthy = calculate_sla_state(
        status=RequestStatus.open,
        created_at=created,
        first_response_due_at=first_due,
        first_responded_at=None,
        resolution_due_at=resolution_due,
        resolved_at=None,
        now=created + timedelta(minutes=10),
    )
    warning = calculate_sla_state(
        status=RequestStatus.open,
        created_at=created,
        first_response_due_at=first_due,
        first_responded_at=None,
        resolution_due_at=resolution_due,
        resolved_at=None,
        now=created + timedelta(minutes=50),
    )
    breached = calculate_sla_state(
        status=RequestStatus.open,
        created_at=created,
        first_response_due_at=first_due,
        first_responded_at=None,
        resolution_due_at=resolution_due,
        resolved_at=None,
        now=created + timedelta(minutes=61),
    )

    assert healthy == "healthy"
    assert warning == "warning"
    assert breached == "breached"


def test_first_response_switches_active_deadline_to_resolution() -> None:
    created = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)

    state = calculate_sla_state(
        status=RequestStatus.in_progress,
        created_at=created,
        first_response_due_at=created + timedelta(minutes=15),
        first_responded_at=created + timedelta(minutes=5),
        resolution_due_at=created + timedelta(hours=4),
        resolved_at=None,
        now=created + timedelta(minutes=30),
    )

    assert state == "healthy"


def test_resolved_and_closed_requests_are_completed() -> None:
    created = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)

    for status in (RequestStatus.resolved, RequestStatus.closed):
        state = calculate_sla_state(
            status=status,
            created_at=created,
            first_response_due_at=created + timedelta(minutes=10),
            first_responded_at=None,
            resolution_due_at=created + timedelta(minutes=20),
            resolved_at=created + timedelta(minutes=5),
            now=created + timedelta(hours=2),
        )
        assert state == "completed"


def test_invalid_status_transition_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid request status transition"):
        validate_status_transition(RequestStatus.closed, RequestStatus.open)


def test_invalid_sla_duration_is_rejected() -> None:
    created = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="resolution SLA"):
        calculate_deadlines(created, RequestPriority.normal, 120, 60)
