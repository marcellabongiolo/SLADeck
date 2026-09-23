from datetime import datetime

from fastapi.testclient import TestClient


PASSWORD = "StrongPassword123!"


def register(client: TestClient, email: str, name: str) -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "full_name": name, "password": PASSWORD},
    )
    assert response.status_code == 201
    return response.json()


def login(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_org(client: TestClient, token: str, name: str, slug: str) -> dict:
    response = client.post(
        "/organizations",
        headers=headers(token),
        json={"name": name, "slug": slug},
    )
    assert response.status_code == 201
    return response.json()


def create_policy(
    client: TestClient,
    token: str,
    organization_id: str,
    name: str = "Standard",
) -> dict:
    response = client.post(
        f"/organizations/{organization_id}/sla-policies",
        headers=headers(token),
        json={
            "name": name,
            "first_response_minutes": 60,
            "resolution_minutes": 480,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_request_workflow_calculates_deadlines_and_sla_state(client: TestClient) -> None:
    owner = register(client, "workflow-owner@example.com", "Owner")
    owner_token = login(client, owner["email"])
    org = create_org(client, owner_token, "Workflow Org", "workflow-org")
    policy = create_policy(client, owner_token, org["id"])

    create = client.post(
        f"/organizations/{org['id']}/requests",
        headers=headers(owner_token),
        json={
            "title": "Restore customer access",
            "description": "Customer cannot reach the dashboard.",
            "priority": "urgent",
            "assignee_id": owner["id"],
            "sla_policy_id": policy["id"],
        },
    )
    assert create.status_code == 201
    request = create.json()

    created_at = datetime.fromisoformat(request["created_at"])
    first_due = datetime.fromisoformat(request["first_response_due_at"])
    resolution_due = datetime.fromisoformat(request["resolution_due_at"])

    assert int((first_due - created_at).total_seconds()) == 15 * 60
    assert int((resolution_due - created_at).total_seconds()) == 120 * 60
    assert request["sla_state"] == "healthy"
    assert request["status"] == "open"

    first_response = client.post(
        f"/organizations/{org['id']}/requests/{request['id']}/first-response",
        headers=headers(owner_token),
    )
    assert first_response.status_code == 200
    assert first_response.json()["first_responded_at"] is not None

    progress = client.patch(
        f"/organizations/{org['id']}/requests/{request['id']}",
        headers=headers(owner_token),
        json={"status": "in_progress", "priority": "high"},
    )
    assert progress.status_code == 200
    updated = progress.json()
    assert updated["status"] == "in_progress"
    assert updated["priority"] == "high"

    resolved = client.patch(
        f"/organizations/{org['id']}/requests/{request['id']}",
        headers=headers(owner_token),
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["sla_state"] == "completed"
    assert resolved.json()["resolved_at"] is not None

    closed = client.patch(
        f"/organizations/{org['id']}/requests/{request['id']}",
        headers=headers(owner_token),
        json={"status": "closed"},
    )
    assert closed.status_code == 200

    invalid_reopen = client.patch(
        f"/organizations/{org['id']}/requests/{request['id']}",
        headers=headers(owner_token),
        json={"status": "open"},
    )
    assert invalid_reopen.status_code == 400


def test_member_can_create_and_assignee_can_mark_first_response(client: TestClient) -> None:
    owner = register(client, "team-owner@example.com", "Owner")
    member = register(client, "team-member@example.com", "Member")
    other = register(client, "other-member@example.com", "Other")
    owner_token = login(client, owner["email"])
    member_token = login(client, member["email"])
    other_token = login(client, other["email"])
    org = create_org(client, owner_token, "Team Org", "team-org")
    policy = create_policy(client, owner_token, org["id"])

    for email in (member["email"], other["email"]):
        response = client.post(
            f"/organizations/{org['id']}/members",
            headers=headers(owner_token),
            json={"email": email, "role": "member"},
        )
        assert response.status_code == 201

    created = client.post(
        f"/organizations/{org['id']}/requests",
        headers=headers(member_token),
        json={
            "title": "Member request",
            "description": "",
            "priority": "normal",
            "assignee_id": member["id"],
            "sla_policy_id": policy["id"],
        },
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    forbidden = client.post(
        f"/organizations/{org['id']}/requests/{request_id}/first-response",
        headers=headers(other_token),
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        f"/organizations/{org['id']}/requests/{request_id}/first-response",
        headers=headers(member_token),
    )
    assert allowed.status_code == 200


def test_request_and_policy_are_tenant_scoped(client: TestClient) -> None:
    first = register(client, "tenant-one@example.com", "Tenant One")
    second = register(client, "tenant-two@example.com", "Tenant Two")
    first_token = login(client, first["email"])
    second_token = login(client, second["email"])
    first_org = create_org(client, first_token, "Tenant One", "tenant-one")
    second_org = create_org(client, second_token, "Tenant Two", "tenant-two")
    first_policy = create_policy(client, first_token, first_org["id"], "First")
    second_policy = create_policy(client, second_token, second_org["id"], "Second")

    wrong_policy = client.post(
        f"/organizations/{first_org['id']}/requests",
        headers=headers(first_token),
        json={
            "title": "Wrong policy",
            "description": "",
            "priority": "normal",
            "sla_policy_id": second_policy["id"],
        },
    )
    assert wrong_policy.status_code == 400

    created = client.post(
        f"/organizations/{first_org['id']}/requests",
        headers=headers(first_token),
        json={
            "title": "Private request",
            "description": "",
            "priority": "normal",
            "sla_policy_id": first_policy["id"],
        },
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    cross_tenant = client.get(
        f"/organizations/{first_org['id']}/requests/{request_id}",
        headers=headers(second_token),
    )
    assert cross_tenant.status_code == 403


def test_policy_crud_and_in_use_policy_cannot_be_deleted(client: TestClient) -> None:
    owner = register(client, "policy-owner@example.com", "Policy Owner")
    owner_token = login(client, owner["email"])
    org = create_org(client, owner_token, "Policy Org", "policy-org")
    policy = create_policy(client, owner_token, org["id"])

    invalid = client.patch(
        f"/organizations/{org['id']}/sla-policies/{policy['id']}",
        headers=headers(owner_token),
        json={"first_response_minutes": 600},
    )
    assert invalid.status_code == 400

    updated = client.patch(
        f"/organizations/{org['id']}/sla-policies/{policy['id']}",
        headers=headers(owner_token),
        json={"name": "Priority", "resolution_minutes": 600},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Priority"

    request = client.post(
        f"/organizations/{org['id']}/requests",
        headers=headers(owner_token),
        json={
            "title": "Tracked request",
            "description": "",
            "priority": "normal",
            "sla_policy_id": policy["id"],
        },
    )
    assert request.status_code == 201

    blocked_delete = client.delete(
        f"/organizations/{org['id']}/sla-policies/{policy['id']}",
        headers=headers(owner_token),
    )
    assert blocked_delete.status_code == 409

    retained_request = client.delete(
        f"/organizations/{org['id']}/requests/{request.json()['id']}",
        headers=headers(owner_token),
    )
    assert retained_request.status_code == 409
    assert "retained for audit history" in retained_request.json()["detail"]

    still_blocked = client.delete(
        f"/organizations/{org['id']}/sla-policies/{policy['id']}",
        headers=headers(owner_token),
    )
    assert still_blocked.status_code == 409

    unused_policy = create_policy(client, owner_token, org["id"], "Unused")
    deleted_policy = client.delete(
        f"/organizations/{org['id']}/sla-policies/{unused_policy['id']}",
        headers=headers(owner_token),
    )
    assert deleted_policy.status_code == 204


def test_request_filters_work(client: TestClient) -> None:
    owner = register(client, "filter-owner@example.com", "Filter Owner")
    token = login(client, owner["email"])
    org = create_org(client, token, "Filter Org", "filter-org")
    policy = create_policy(client, token, org["id"])

    for title, priority in (("Urgent task", "urgent"), ("Low task", "low")):
        response = client.post(
            f"/organizations/{org['id']}/requests",
            headers=headers(token),
            json={
                "title": title,
                "description": "",
                "priority": priority,
                "sla_policy_id": policy["id"],
            },
        )
        assert response.status_code == 201

    filtered = client.get(
        f"/organizations/{org['id']}/requests?priority=urgent",
        headers=headers(token),
    )
    assert filtered.status_code == 200
    assert [item["title"] for item in filtered.json()] == ["Urgent task"]
