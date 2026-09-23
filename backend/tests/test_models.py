from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sladeck.models import (
    Membership,
    MembershipRole,
    Organization,
    Request,
    RequestPriority,
    SLAPolicy,
    User,
)
from sladeck.repositories import list_requests_for_organization


def make_user(email: str, name: str) -> User:
    return User(
        email=email,
        full_name=name,
        password_hash="not-a-real-hash",
    )


def test_core_domain_relationships(db_session: Session) -> None:
    user = make_user("owner@example.com", "Owner")
    organization = Organization(name="Acme Support", slug="acme-support")
    membership = Membership(
        user=user,
        organization=organization,
        role=MembershipRole.owner,
    )
    policy = SLAPolicy(
        organization=organization,
        name="Standard",
        first_response_minutes=60,
        resolution_minutes=480,
    )
    db_session.add_all([user, organization, membership, policy])
    db_session.flush()

    request = Request(
        organization_id=organization.id,
        title="Production access request",
        description="Grant access to the production dashboard.",
        requester_id=user.id,
        assignee_id=user.id,
        priority=RequestPriority.high,
        sla_policy_id=policy.id,
    )
    db_session.add(request)
    db_session.commit()

    assert request.organization.id == organization.id
    assert request.sla_policy is not None
    assert request.sla_policy.name == "Standard"
    assert organization.memberships[0].role == MembershipRole.owner
    assert organization.requests[0].title == "Production access request"


def test_membership_is_unique_per_user_and_organization(db_session: Session) -> None:
    user = make_user("member@example.com", "Member")
    organization = Organization(name="Northwind", slug="northwind")
    db_session.add_all([user, organization])
    db_session.flush()

    db_session.add(
        Membership(
            user_id=user.id,
            organization_id=organization.id,
            role=MembershipRole.member,
        )
    )
    db_session.commit()

    db_session.add(
        Membership(
            user_id=user.id,
            organization_id=organization.id,
            role=MembershipRole.manager,
        )
    )

    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
    else:
        raise AssertionError("Expected duplicate membership to fail")


def test_request_rejects_requester_from_another_organization(db_session: Session) -> None:
    first_org = Organization(name="First", slug="first")
    second_org = Organization(name="Second", slug="second")
    first_user = make_user("first@example.com", "First User")
    second_user = make_user("second@example.com", "Second User")

    db_session.add_all([first_org, second_org, first_user, second_user])
    db_session.flush()

    db_session.add_all(
        [
            Membership(
                user_id=first_user.id,
                organization_id=first_org.id,
                role=MembershipRole.owner,
            ),
            Membership(
                user_id=second_user.id,
                organization_id=second_org.id,
                role=MembershipRole.owner,
            ),
        ]
    )
    db_session.commit()

    db_session.add(
        Request(
            organization_id=first_org.id,
            title="Cross-tenant request",
            description="This must fail.",
            requester_id=second_user.id,
        )
    )

    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
    else:
        raise AssertionError("Expected cross-tenant requester to violate membership constraint")


def test_request_repository_is_tenant_scoped(db_session: Session) -> None:
    first_org = Organization(name="Alpha", slug="alpha")
    second_org = Organization(name="Beta", slug="beta")
    first_user = make_user("alpha@example.com", "Alpha User")
    second_user = make_user("beta@example.com", "Beta User")
    db_session.add_all([first_org, second_org, first_user, second_user])
    db_session.flush()

    db_session.add_all(
        [
            Membership(
                user_id=first_user.id,
                organization_id=first_org.id,
                role=MembershipRole.owner,
            ),
            Membership(
                user_id=second_user.id,
                organization_id=second_org.id,
                role=MembershipRole.owner,
            ),
        ]
    )
    db_session.flush()

    db_session.add_all(
        [
            Request(
                organization_id=first_org.id,
                title="Alpha request",
                description="Only Alpha should see this.",
                requester_id=first_user.id,
            ),
            Request(
                organization_id=second_org.id,
                title="Beta request",
                description="Only Beta should see this.",
                requester_id=second_user.id,
            ),
        ]
    )
    db_session.commit()

    alpha_requests = list_requests_for_organization(db_session, first_org.id)

    assert [request.title for request in alpha_requests] == ["Alpha request"]
