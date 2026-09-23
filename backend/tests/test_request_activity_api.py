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
    name: str,
    first_response: int = 60,
    resolution: int = 480,
) -> dict:
    response = client.post(
        f"/organizations/{organization_id}/sla-policies",
        headers=headers(token),
        json={
            "name": name,
            "first_response_minutes": first_response,
            "resolution_minutes": resolution,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_comments_and_audit_activity_timeline(client: TestClient) -> None:
    owner = register(client, "activity-owner@example.com", "Activity Owner")
    member = register(client, "activity-member@example.com", "Activity Member")
    owner_token = login(client, owner["email"])
    member_token = login(client, member["email"])

    org = create_org(client, owner_token, "Activity Org", "activity-org")
    added = client.post(
        f"/organizations/{org['id']}/members",
        headers=headers(owner_token),
        json={"email": member["email"], "role": "member"},
    )
    assert added.status_code == 201

    standard = create_policy(client, owner_token, org["id"], "Standard")
    priority = create_policy(
        client,
        owner_token,
        org["id"],
        "Priority",
        first_response=30,
        resolution=240,
    )

    created = client.post(
        f"/organizations/{org['id']}/requests",
        headers=headers(member_token),
        json={
            "title": "Investigate customer outage",
            "description": "Customer reports an outage.",
            "priority": "normal",
            "assignee_id": member["id"],
            "sla_policy_id": standard["id"],
        },
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    comment = client.post(
        f"/organizations/{org['id']}/requests/{request_id}/comments",
        headers=headers(member_token),
        json={"body": "  Customer confirmed the issue is still active.  "},
    )
    assert comment.status_code == 201
    assert comment.json()["body"] == "Customer confirmed the issue is still active."

    blank = client.post(
        f"/organizations/{org['id']}/requests/{request_id}/comments",
        headers=headers(member_token),
        json={"body": "   "},
    )
    assert blank.status_code == 422

    first_response = client.post(
        f"/organizations/{org['id']}/requests/{request_id}/first-response",
        headers=headers(member_token),
    )
    assert first_response.status_code == 200

    changed = client.patch(
        f"/organizations/{org['id']}/requests/{request_id}",
        headers=headers(owner_token),
        json={
            "status": "in_progress",
            "priority": "high",
            "assignee_id": owner["id"],
            "sla_policy_id": priority["id"],
        },
    )
    assert changed.status_code == 200

    comments = client.get(
        f"/organizations/{org['id']}/requests/{request_id}/comments",
        headers=headers(member_token),
    )
    assert comments.status_code == 200
    assert [item["body"] for item in comments.json()] == [
        "Customer confirmed the issue is still active."
    ]

    activity = client.get(
        f"/organizations/{org['id']}/requests/{request_id}/activity",
        headers=headers(member_token),
    )
    assert activity.status_code == 200
    items = activity.json()

    assert items == sorted(items, key=lambda item: (item["created_at"], item["id"]))
    assert sum(item["kind"] == "comment" for item in items) == 1

    event_types = {
        item["event_type"]
        for item in items
        if item["kind"] == "audit_event"
    }
    assert {
        "request_created",
        "first_response_recorded",
        "status_changed",
        "priority_changed",
        "assignee_changed",
        "sla_policy_changed",
    }.issubset(event_types)

    status_event = next(
        item for item in items if item.get("event_type") == "status_changed"
    )
    assert status_event["data"] == {"from": "open", "to": "in_progress"}

    assignee_event = next(
        item for item in items if item.get("event_type") == "assignee_changed"
    )
    assert assignee_event["data"]["from"] == member["id"]
    assert assignee_event["data"]["to"] == owner["id"]


def test_activity_is_tenant_scoped_and_audit_has_no_mutation_api(client: TestClient) -> None:
    first = register(client, "activity-first@example.com", "First")
    second = register(client, "activity-second@example.com", "Second")
    first_token = login(client, first["email"])
    second_token = login(client, second["email"])

    first_org = create_org(client, first_token, "First Activity", "first-activity")
    second_org = create_org(client, second_token, "Second Activity", "second-activity")
    policy = create_policy(client, first_token, first_org["id"], "Standard")

    created = client.post(
        f"/organizations/{first_org['id']}/requests",
        headers=headers(first_token),
        json={
            "title": "Private activity",
            "description": "",
            "priority": "normal",
            "sla_policy_id": policy["id"],
        },
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    cross_tenant = client.get(
        f"/organizations/{first_org['id']}/requests/{request_id}/activity",
        headers=headers(second_token),
    )
    assert cross_tenant.status_code == 403

    own_activity = client.get(
        f"/organizations/{first_org['id']}/requests/{request_id}/activity",
        headers=headers(first_token),
    )
    assert own_activity.status_code == 200
    audit_event = next(
        item for item in own_activity.json() if item["kind"] == "audit_event"
    )

    mutation_path = (
        f"/organizations/{first_org['id']}/requests/{request_id}/activity/"
        f"{audit_event['id']}"
    )
    assert client.patch(
        mutation_path,
        headers=headers(first_token),
        json={"event_type": "tampered"},
    ).status_code in {404, 405}
    assert client.delete(
        mutation_path,
        headers=headers(first_token),
    ).status_code in {404, 405}

    retained = client.delete(
        f"/organizations/{first_org['id']}/requests/{request_id}",
        headers=headers(first_token),
    )
    assert retained.status_code == 409

    second_policy = create_policy(client, second_token, second_org["id"], "Other")
    assert second_policy["organization_id"] == second_org["id"]



def test_sla_notification_history_is_tenant_scoped(client: TestClient) -> None:
    first = register(client, "notification-first@example.com", "Notification First")
    second = register(client, "notification-second@example.com", "Notification Second")
    first_token = login(client, first["email"])
    second_token = login(client, second["email"])

    first_org = create_org(client, first_token, "Notification First Org", "notification-first")
    second_org = create_org(client, second_token, "Notification Second Org", "notification-second")
    policy = create_policy(
        client,
        first_token,
        first_org["id"],
        "Fast",
        first_response=10,
        resolution=60,
    )

    created = client.post(
        f"/organizations/{first_org['id']}/requests",
        headers=headers(first_token),
        json={
            "title": "SLA notification history",
            "description": "",
            "priority": "normal",
            "sla_policy_id": policy["id"],
        },
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    own = client.get(
        f"/organizations/{first_org['id']}/requests/{request_id}/sla-notifications",
        headers=headers(first_token),
    )
    assert own.status_code == 200
    assert own.json() == []

    cross_tenant = client.get(
        f"/organizations/{first_org['id']}/requests/{request_id}/sla-notifications",
        headers=headers(second_token),
    )
    assert cross_tenant.status_code == 403

    other_org_request = client.post(
        f"/organizations/{second_org['id']}/requests",
        headers=headers(second_token),
        json={
            "title": "Other SLA notification history",
            "description": "",
            "priority": "normal",
            "sla_policy_id": create_policy(
                client,
                second_token,
                second_org["id"],
                "Other Fast",
                first_response=10,
                resolution=60,
            )["id"],
        },
    )
    assert other_org_request.status_code == 201
