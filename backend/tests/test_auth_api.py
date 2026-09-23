from fastapi.testclient import TestClient


PASSWORD = "StrongPassword123!"


def register(
    client: TestClient,
    email: str,
    full_name: str = "Test User",
) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": full_name,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    return response.json()


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_register_login_and_me(client: TestClient) -> None:
    user = register(client, "USER@Example.com", "Example User")

    assert user["email"] == "user@example.com"
    assert "password" not in user
    assert "password_hash" not in user

    duplicate = client.post(
        "/auth/register",
        json={
            "email": "user@example.com",
            "full_name": "Duplicate",
            "password": PASSWORD,
        },
    )
    assert duplicate.status_code == 409

    bad_login = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401

    tokens = login(client, "user@example.com")
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    me = client.get("/auth/me", headers=bearer(tokens["access_token"]))
    assert me.status_code == 200
    assert me.json()["id"] == user["id"]
    assert me.json()["email"] == "user@example.com"


def test_access_token_is_required_and_validated(client: TestClient) -> None:
    missing = client.get("/auth/me")
    assert missing.status_code == 401

    invalid = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert invalid.status_code == 401


def test_refresh_token_rotation_and_logout(client: TestClient) -> None:
    register(client, "rotate@example.com")
    first = login(client, "rotate@example.com")

    rotated = client.post(
        "/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert rotated.status_code == 200
    second = rotated.json()
    assert second["refresh_token"] != first["refresh_token"]

    replay = client.post(
        "/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert replay.status_code == 401

    logout = client.post(
        "/auth/logout",
        json={"refresh_token": second["refresh_token"]},
    )
    assert logout.status_code == 204

    after_logout = client.post(
        "/auth/refresh",
        json={"refresh_token": second["refresh_token"]},
    )
    assert after_logout.status_code == 401
