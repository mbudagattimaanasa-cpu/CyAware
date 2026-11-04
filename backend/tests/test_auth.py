import pytest
from flask import jsonify
from backend.app.middleware import admin_required, reset_all_rate_limits
from backend.app.database import query_db, execute_db


@pytest.fixture(autouse=True)
def clean_rate_limits():
    """Reset in-memory rate limiting state before every test."""
    reset_all_rate_limits()
    yield
    reset_all_rate_limits()


def test_register_success(client):
    """Test successful user registration."""
    res = client.post("/api/auth/register", json={
        "username": "alice_test",
        "email": "alice@example.com",
        "password": "Password123"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["user"]["username"] == "alice_test"
    assert data["data"]["user"]["email"] == "alice@example.com"
    assert data["data"]["user"]["role"] == "user"
    assert "password" not in data["data"]["user"]
    assert "password_hash" not in data["data"]["user"]

    # Verify audit log was recorded
    log = query_db(
        "SELECT * FROM audit_logs WHERE action = 'USER_REGISTERED' AND user_id = ?",
        (data["data"]["user"]["id"],),
        one=True
    )
    assert log is not None


def test_cannot_self_register_as_admin(client):
    """Verify any role parameter passed in registration is ignored and set to 'user'."""
    res = client.post("/api/auth/register", json={
        "username": "fake_admin",
        "email": "fakeadmin@example.com",
        "password": "Password123",
        "role": "admin"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["data"]["user"]["role"] == "user"

    # Query directly from DB
    user = query_db("SELECT role FROM users WHERE username = ?", ("fake_admin",), one=True)
    assert user["role"] == "user"


def test_register_validation_errors(client):
    """Test various invalid registration inputs."""
    # Short username
    res = client.post("/api/auth/register", json={
        "username": "ab",
        "email": "ab@example.com",
        "password": "Password123"
    })
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"

    # Invalid characters in username
    res = client.post("/api/auth/register", json={
        "username": "alice!@#",
        "email": "alice@example.com",
        "password": "Password123"
    })
    assert res.status_code == 400

    # Invalid email
    res = client.post("/api/auth/register", json={
        "username": "alice_valid",
        "email": "not-an-email",
        "password": "Password123"
    })
    assert res.status_code == 400

    # Weak password (less than 8 chars)
    res = client.post("/api/auth/register", json={
        "username": "alice_valid",
        "email": "alice@example.com",
        "password": "Pass1"
    })
    assert res.status_code == 400

    # Weak password (no numbers)
    res = client.post("/api/auth/register", json={
        "username": "alice_valid",
        "email": "alice@example.com",
        "password": "PasswordOnly"
    })
    assert res.status_code == 400


def test_register_duplicate_username_and_email(client):
    """Verify duplicate username and email are rejected with 409 Conflict."""
    client.post("/api/auth/register", json={
        "username": "bob_test",
        "email": "bob@example.com",
        "password": "Password123"
    })

    # Duplicate username
    res1 = client.post("/api/auth/register", json={
        "username": "bob_test",
        "email": "different@example.com",
        "password": "Password123"
    })
    assert res1.status_code == 409
    assert res1.get_json()["error"]["code"] == "USER_EXISTS"

    # Duplicate email
    res2 = client.post("/api/auth/register", json={
        "username": "different_bob",
        "email": "bob@example.com",
        "password": "Password123"
    })
    assert res2.status_code == 409
    assert res2.get_json()["error"]["code"] == "USER_EXISTS"


def test_login_success_with_username_and_email(client):
    """Test login works using either username or email."""
    client.post("/api/auth/register", json={
        "username": "charlie_test",
        "email": "charlie@example.com",
        "password": "Password123"
    })

    # Login with username
    res_user = client.post("/api/auth/login", json={
        "username_or_email": "charlie_test",
        "password": "Password123"
    })
    assert res_user.status_code == 200
    assert res_user.get_json()["success"] is True

    # Check /api/auth/me using the session established
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.get_json()["data"]["user"]["username"] == "charlie_test"

    # Logout
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200

    # Session should now be cleared
    me_after_logout = client.get("/api/auth/me")
    assert me_after_logout.status_code == 401

    # Login with email
    res_email = client.post("/api/auth/login", json={
        "username_or_email": "charlie@example.com",
        "password": "Password123"
    })
    assert res_email.status_code == 200


def test_login_invalid_credentials(client):
    """Test login failure with wrong password and nonexistent user."""
    client.post("/api/auth/register", json={
        "username": "dave_test",
        "email": "dave@example.com",
        "password": "Password123"
    })

    # Wrong password
    res1 = client.post("/api/auth/login", json={
        "username_or_email": "dave_test",
        "password": "WrongPassword999"
    })
    assert res1.status_code == 401
    assert res1.get_json()["error"]["code"] == "INVALID_CREDENTIALS"

    # Non-existent user
    res2 = client.post("/api/auth/login", json={
        "username_or_email": "nonexistent_user",
        "password": "Password123"
    })
    assert res2.status_code == 401


def test_login_deactivated_account(client, app):
    """Test that deactivated accounts cannot log in."""
    client.post("/api/auth/register", json={
        "username": "eve_test",
        "email": "eve@example.com",
        "password": "Password123"
    })

    # Deactivate account in DB
    with app.app_context():
        execute_db("UPDATE users SET is_active = 0 WHERE username = 'eve_test'")

    res = client.post("/api/auth/login", json={
        "username_or_email": "eve_test",
        "password": "Password123"
    })
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "ACCOUNT_DISABLED"


def test_login_throttling_rate_limit(client):
    """Test that 5 consecutive failed logins trigger 429 Too Many Requests."""
    client.post("/api/auth/register", json={
        "username": "target_user",
        "email": "target@example.com",
        "password": "Password123"
    })

    for i in range(5):
        fail_res = client.post("/api/auth/login", json={
            "username_or_email": "target_user",
            "password": f"WrongPass{i}"
        })
        assert fail_res.status_code == 401

    # 6th attempt should be throttled
    throttled_res = client.post("/api/auth/login", json={
        "username_or_email": "target_user",
        "password": "Password123"
    })
    assert throttled_res.status_code == 429
    assert throttled_res.get_json()["error"]["code"] == "RATE_LIMITED"


def test_role_based_access_control(app, client):
    """Test role authorization: normal users cannot access admin routes."""
    # Define a test admin route
    @app.route("/api/test-admin-only", methods=["GET"])
    @admin_required
    def test_admin_route():
        return jsonify({"success": True, "message": "Admin area accessed."}), 200

    # 1. Unauthenticated access
    res_unauth = client.get("/api/test-admin-only")
    assert res_unauth.status_code == 401

    # 2. Register and log in as normal user
    client.post("/api/auth/register", json={
        "username": "normal_user",
        "email": "normal@example.com",
        "password": "Password123"
    })
    client.post("/api/auth/login", json={
        "username_or_email": "normal_user",
        "password": "Password123"
    })

    # Accessing admin route as normal user -> 403 Forbidden
    res_user = client.get("/api/test-admin-only")
    assert res_user.status_code == 403
    assert res_user.get_json()["error"]["code"] == "FORBIDDEN"

    # 3. Elevate user to admin in DB
    with app.app_context():
        execute_db("UPDATE users SET role = 'admin' WHERE username = 'normal_user'")

    # Re-login to update session role
    client.post("/api/auth/login", json={
        "username_or_email": "normal_user",
        "password": "Password123"
    })

    # Accessing admin route as admin -> 200 OK
    res_admin = client.get("/api/test-admin-only")
    assert res_admin.status_code == 200
    assert res_admin.get_json()["success"] is True


def test_cli_create_admin(runner, client):
    """Test creating an administrator via the CLI command."""
    result = runner.invoke(args=[
        "create-admin",
        "--username", "superadmin",
        "--email", "admin@cyaware.org",
        "--password", "SuperAdmin123"
    ])
    assert result.exit_code == 0
    assert "created successfully" in result.output

    # Login as this admin via API
    res = client.post("/api/auth/login", json={
        "username_or_email": "superadmin",
        "password": "SuperAdmin123"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["data"]["user"]["role"] == "admin"
