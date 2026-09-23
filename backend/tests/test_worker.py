from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from sladeck.escalations import run_sla_check
from sladeck.models import (
    Membership,
    MembershipRole,
    Organization,
    Request,
    RequestPriority,
    RequestStatus,
    SLAPolicy,
    SLANotification,
    User,
)
from sladeck.worker import celery_app, check_sla_deadlines


def seed_request(
    session,
    *,
    now: datetime,
    first_response_due_at: datetime | None,
    resolution_due_at: datetime | None,
    first_responded_at: datetime | None = None,
    status: RequestStatus = RequestStatus.open,
) -> Request:
    user = User(
        email=f"worker-{now.timestamp()}@example.com",
        full_name="Worker Test User",
        password_hash="not-a-real-hash",
    )
    organization = Organization(
        name="Worker Test Organization",
        slug=f"worker-{int(now.timestamp() * 1000000)}",
    )
    session.add_all([user, organization])
    session.flush()

    session.add(
        Membership(
            user_id=user.id,
            organization_id=organization.id,
            role=MembershipRole.owner,
        )
    )
    policy = SLAPolicy(
        organization_id=organization.id,
        name=f"Worker Policy {int(now.timestamp() * 1000000)}",
        first_response_minutes=60,
        resolution_minutes=240,
    )
    session.add(policy)
    session.flush()

    request = Request(
        organization_id=organization.id,
        title="Worker test request",
        description="",
        status=status,
        priority=RequestPriority.normal,
        requester_id=user.id,
        sla_policy_id=policy.id,
        first_response_due_at=first_response_due_at,
        first_responded_at=first_responded_at,
        resolution_due_at=resolution_due_at,
        created_at=now - timedelta(hours=1),
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def test_warning_and_breach_are_created_once(db_session) -> None:
    created_at = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    first_due = created_at + timedelta(hours=1)
    request = seed_request(
        db_session,
        now=created_at,
        first_response_due_at=first_due,
        resolution_due_at=created_at + timedelta(hours=4),
    )

    warning_result = run_sla_check(
        db_session,
        now=created_at + timedelta(minutes=50),
    )
    assert warning_result == {"checked": 1, "created": 1}

    warning_again = run_sla_check(
        db_session,
        now=created_at + timedelta(minutes=55),
    )
    assert warning_again == {"checked": 1, "created": 0}

    breach_result = run_sla_check(
        db_session,
        now=created_at + timedelta(hours=1, minutes=1),
    )
    assert breach_result == {"checked": 1, "created": 1}

    notifications = list(
        db_session.scalars(
            select(SLANotification).where(SLANotification.request_id == request.id)
        )
    )
    assert {(item.stage, item.kind) for item in notifications} == {
        ("first_response", "warning"),
        ("first_response", "breached"),
    }

    events = db_session.execute(
        select(SLANotification.id).where(SLANotification.request_id == request.id)
    ).all()
    assert len(events) == 2


def test_resolution_warning_uses_resolution_deadline_after_first_response(db_session) -> None:
    created_at = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    request = seed_request(
        db_session,
        now=created_at,
        first_response_due_at=created_at + timedelta(minutes=30),
        resolution_due_at=created_at + timedelta(hours=2),
        first_responded_at=created_at + timedelta(minutes=10),
    )

    result = run_sla_check(
        db_session,
        now=created_at + timedelta(hours=1, minutes=40),
    )
    assert result == {"checked": 1, "created": 1}

    notification = db_session.scalar(
        select(SLANotification).where(SLANotification.request_id == request.id)
    )
    assert notification is not None
    assert notification.stage == "resolution"
    assert notification.kind == "warning"


def test_completed_requests_are_ignored(db_session) -> None:
    created_at = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    request = seed_request(
        db_session,
        now=created_at,
        first_response_due_at=created_at + timedelta(minutes=10),
        resolution_due_at=created_at + timedelta(minutes=20),
        status=RequestStatus.closed,
    )

    result = run_sla_check(
        db_session,
        now=created_at + timedelta(hours=1),
    )
    assert result == {"checked": 0, "created": 0}
    assert db_session.scalar(
        select(SLANotification.id).where(SLANotification.request_id == request.id)
    ) is None


def test_notification_uniqueness_is_database_enforced(db_session) -> None:
    created_at = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    request = seed_request(
        db_session,
        now=created_at,
        first_response_due_at=created_at + timedelta(minutes=10),
        resolution_due_at=created_at + timedelta(hours=2),
    )

    first = run_sla_check(
        db_session,
        now=created_at + timedelta(minutes=9),
    )
    assert first["created"] == 1

    duplicate = SLANotification(
        organization_id=request.organization_id,
        request_id=request.id,
        stage="first_response",
        kind="warning",
        due_at=request.first_response_due_at,
        data={},
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_celery_schedule_and_task_contract() -> None:
    schedule = celery_app.conf.beat_schedule["check-sla-deadlines-every-minute"]
    assert schedule["task"] == "sladeck.check_sla_deadlines"
    assert schedule["schedule"] == 60.0
    assert celery_app.conf.broker_url.endswith("/0")


def test_celery_task_delegates_to_database_service() -> None:
    fake_result = {"checked": 4, "created": 2}
    with (
        patch("sladeck.worker.create_engine") as create_engine,
        patch("sladeck.worker.run_sla_check", return_value=fake_result) as run_check,
    ):
        engine = create_engine.return_value
        with patch("sladeck.worker.Session") as session_factory:
            result = check_sla_deadlines.apply(
                kwargs={"now_iso": "2026-09-23T12:00:00+00:00"}
            ).get()

    assert result == fake_result
    create_engine.assert_called_once()
    run_check.assert_called_once()
    session_factory.assert_called_once_with(engine)


def test_redis_is_reachable_when_configured() -> None:
    import redis

    from sladeck.config import get_settings

    client = redis.from_url(get_settings().redis_url, socket_connect_timeout=1)
    try:
        try:
            assert client.ping() is True
        except redis.exceptions.ConnectionError:
            pytest.skip("Redis is not running locally")
    finally:
        client.close()
