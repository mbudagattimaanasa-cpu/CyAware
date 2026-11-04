from datetime import timedelta
import pytest
from flask import jsonify, session
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
    """Test login works using either username or email and returns csrf_token."""
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
    user_data = res_user.get_json()
    assert user_data["success"] is True
    assert "csrf_token" in user_data["data"]
    csrf_token = user_data["data"]["csrf_token"]

    # Check /api/auth/me using the session established
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.get_json()["data"]["user"]["username"] == "charlie_test"

    # Logout with valid CSRF header
    logout_res = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_token})
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


# =========================================================================
# Additional Stage 2 Verification Tests: CSRF, Session Invalidation & Expiry
# =========================================================================

def test_csrf_token_endpoint(client):
    """Test GET /api/auth/csrf-token returns a valid 64-char hex token."""
    res = client.get("/api/auth/csrf-token")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "csrf_token" in data["data"]
    assert len(data["data"]["csrf_token"]) == 64


def test_csrf_protection_missing_token_rejected(client):
    """Verify state-changing POST on authenticated session without CSRF token is rejected with 403."""
    # Register and login
    client.post("/api/auth/register", json={
        "username": "csrf_user",
        "email": "csrf@example.com",
        "password": "Password123"
    })
    client.post("/api/auth/login", json={
        "username_or_email": "csrf_user",
        "password": "Password123"
    })

    # Attempt state-changing logout WITHOUT X-CSRF-Token header
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 403
    err = logout_res.get_json()["error"]
    assert err["code"] == "CSRF_ERROR"
    assert "CSRF token missing or invalid" in err["message"]


def test_csrf_protection_invalid_token_rejected(client):
    """Verify state-changing POST with an invalid CSRF token is rejected with 403."""
    client.post("/api/auth/register", json={
        "username": "csrf_user2",
        "email": "csrf2@example.com",
        "password": "Password123"
    })
    client.post("/api/auth/login", json={
        "username_or_email": "csrf_user2",
        "password": "Password123"
    })

    # Attempt logout with forged/wrong CSRF token
    logout_res = client.post("/api/auth/logout", headers={"X-CSRF-Token": "bad-forged-token-12345"})
    assert logout_res.status_code == 403
    assert logout_res.get_json()["error"]["code"] == "CSRF_ERROR"


def test_csrf_protection_valid_token_accepted(client):
    """Verify state-changing POST with valid CSRF token succeeds."""
    client.post("/api/auth/register", json={
        "username": "csrf_user3",
        "email": "csrf3@example.com",
        "password": "Password123"
    })
    login_res = client.post("/api/auth/login", json={
        "username_or_email": "csrf_user3",
        "password": "Password123"
    })
    csrf_token = login_res.get_json()["data"]["csrf_token"]

    # Logout with valid token
    logout_res = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert logout_res.status_code == 200
    assert logout_res.get_json()["success"] is True


def test_session_cookie_attributes(client):
    """Verify session cookies use HttpOnly, SameSite, and configured Secure settings."""
    client.post("/api/auth/register", json={
        "username": "cookie_user",
        "email": "cookie@example.com",
        "password": "Password123"
    })
    login_res = client.post("/api/auth/login", json={
        "username_or_email": "cookie_user",
        "password": "Password123"
    })
    assert login_res.status_code == 200

    set_cookie = login_res.headers.get("Set-Cookie", "")
    assert "session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie


def test_logout_invalidates_session(client):
    """Verify that logging out fully invalidates the authenticated session."""
    client.post("/api/auth/register", json={
        "username": "logout_user",
        "email": "logout@example.com",
        "password": "Password123"
    })
    login_res = client.post("/api/auth/login", json={
        "username_or_email": "logout_user",
        "password": "Password123"
    })
    csrf_token = login_res.get_json()["data"]["csrf_token"]

    # Verify session is authenticated
    assert client.get("/api/auth/me").status_code == 200

    # Logout
    logout_res = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert logout_res.status_code == 200

    # me endpoint must now return 401
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 401
    assert me_res.get_json()["error"]["code"] == "UNAUTHENTICATED"


def test_session_expiration_behavior(app, client):
    """Verify that expired sessions are rejected by the authentication middleware."""
    client.post("/api/auth/register", json={
        "username": "expiry_user",
        "email": "expiry@example.com",
        "password": "Password123"
    })
    client.post("/api/auth/login", json={
        "username_or_email": "expiry_user",
        "password": "Password123"
    })

    # Verify active
    assert client.get("/api/auth/me").status_code == 200

    # Simulate expired session lifetime by setting PERMANENT_SESSION_LIFETIME to negative duration
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=-1)

    # Next request with expired session should be treated as unauthenticated
    expired_res = client.get("/api/auth/me")
    assert expired_res.status_code == 401
    assert expired_res.get_json()["error"]["code"] == "UNAUTHENTICATED"
