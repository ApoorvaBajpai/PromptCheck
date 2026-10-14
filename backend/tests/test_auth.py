def test_user_registration(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "strongpassword123",
            "full_name": "New User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "newuser@example.com"
    assert data["user"]["full_name"] == "New User"


def test_user_duplicate_email(client, user1):
    response = client.post(
        "/api/auth/register",
        json={
            "email": user1.email,
            "password": "anotherpassword",
        },
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_user_login_success(client, user1):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "user1@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == user1.email


def test_user_login_wrong_password(client, user1):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "user1@example.com",
            "password": "incorrectpassword",
        },
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_get_current_user_profile(client, auth_headers_user1, user1):
    response = client.get("/api/auth/me", headers=auth_headers_user1)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user1.email
    assert data["id"] == user1.id


def test_get_profile_unauthorized(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
