from fastapi.testclient import TestClient


PASSWORD = "StrongPassword123!"


def register(client: TestClient, email: str, name: str) -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "full_name": name, "password": PASSWORD},
    )
    assert response.status_code == 201
    return response.json()


def token(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def create_org(client: TestClient, access_token: str, name: str, slug: str) -> dict:
    response = client.post(
        "/organizations",
        json={"name": name, "slug": slug},
        headers=headers(access_token),
    )
    assert response.status_code == 201
    return response.json()


def test_organization_isolation_and_role_permissions(client: TestClient) -> None:
    owner = register(client, "owner@example.com", "Owner")
    admin = register(client, "admin@example.com", "Admin")
    member = register(client, "member@example.com", "Member")
    candidate = register(client, "candidate@example.com", "Candidate")
    outsider = register(client, "outsider@example.com", "Outsider")

    owner_token = token(client, owner["email"])
    admin_token = token(client, admin["email"])
    member_token = token(client, member["email"])
    outsider_token = token(client, outsider["email"])

    org = create_org(client, owner_token, "Acme Operations", "acme-operations")
    organization_id = org["id"]

    outsider_read = client.get(
        f"/organizations/{organization_id}",
        headers=headers(outsider_token),
    )
    assert outsider_read.status_code == 403

    add_admin = client.post(
        f"/organizations/{organization_id}/members",
        json={"email": admin["email"], "role": "admin"},
        headers=headers(owner_token),
    )
    assert add_admin.status_code == 201
    assert add_admin.json()["role"] == "admin"

    add_member = client.post(
        f"/organizations/{organization_id}/members",
        json={"email": member["email"], "role": "member"},
        headers=headers(admin_token),
    )
    assert add_member.status_code == 201

    member_cannot_add = client.post(
        f"/organizations/{organization_id}/members",
        json={"email": candidate["email"], "role": "member"},
        headers=headers(member_token),
    )
    assert member_cannot_add.status_code == 403

    admin_cannot_create_admin = client.post(
        f"/organizations/{organization_id}/members",
        json={"email": candidate["email"], "role": "admin"},
        headers=headers(admin_token),
    )
    assert admin_cannot_create_admin.status_code == 403

    promote_member = client.patch(
        f"/organizations/{organization_id}/members/{member['id']}",
        json={"role": "manager"},
        headers=headers(owner_token),
    )
    assert promote_member.status_code == 200
    assert promote_member.json()["role"] == "manager"

    members = client.get(
        f"/organizations/{organization_id}/members",
        headers=headers(member_token),
    )
    assert members.status_code == 200
    roles = {item["email"]: item["role"] for item in members.json()}
    assert roles["owner@example.com"] == "owner"
    assert roles["admin@example.com"] == "admin"
    assert roles["member@example.com"] == "manager"


def test_valid_user_cannot_cross_tenant_boundary(client: TestClient) -> None:
    first = register(client, "first-owner@example.com", "First Owner")
    second = register(client, "second-owner@example.com", "Second Owner")

    first_token = token(client, first["email"])
    second_token = token(client, second["email"])

    first_org = create_org(client, first_token, "First Workspace", "first-workspace")
    second_org = create_org(client, second_token, "Second Workspace", "second-workspace")

    cross_read = client.get(
        f"/organizations/{second_org['id']}",
        headers=headers(first_token),
    )
    assert cross_read.status_code == 403

    own_read = client.get(
        f"/organizations/{first_org['id']}",
        headers=headers(first_token),
    )
    assert own_read.status_code == 200


def test_owner_role_cannot_be_assigned_through_member_endpoints(client: TestClient) -> None:
    owner = register(client, "root@example.com", "Root")
    target = register(client, "target@example.com", "Target")
    owner_token = token(client, owner["email"])
    org = create_org(client, owner_token, "Root Org", "root-org")

    direct_owner = client.post(
        f"/organizations/{org['id']}/members",
        json={"email": target["email"], "role": "owner"},
        headers=headers(owner_token),
    )
    assert direct_owner.status_code == 422

    added = client.post(
        f"/organizations/{org['id']}/members",
        json={"email": target["email"], "role": "member"},
        headers=headers(owner_token),
    )
    assert added.status_code == 201

    promote_owner = client.patch(
        f"/organizations/{org['id']}/members/{target['id']}",
        json={"role": "owner"},
        headers=headers(owner_token),
    )
    assert promote_owner.status_code == 403
