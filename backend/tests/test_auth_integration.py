import pytest
from backend.app.middleware import reset_all_rate_limits


@pytest.fixture(autouse=True)
def reset_limits():
    reset_all_rate_limits()
    yield
    reset_all_rate_limits()


def test_registration_success_flow(client):
    """Verify registration endpoint succeeds with valid username, email, and password."""
    payload = {
        "username": "auth_test_user",
        "email": "authtest@example.com",
        "password": "SecurePass123"
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    assert res.is_json
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["user"]["username"] == "auth_test_user"
    assert data["data"]["user"]["email"] == "authtest@example.com"
    assert data["data"]["user"]["role"] == "user"
    assert "password" not in data["data"]["user"]


def test_registration_duplicate_handling(client):
    """Verify duplicate username and email are rejected with 409 USER_EXISTS."""
    payload = {
        "username": "duplicate_user",
        "email": "duplicate@example.com",
        "password": "SecurePass123"
    }
    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    # Duplicate username
    res_dup_user = client.post("/api/auth/register", json={
        "username": "duplicate_user",
        "email": "other@example.com",
        "password": "SecurePass123"
    })
    assert res_dup_user.status_code == 409
    assert res_dup_user.get_json()["error"]["code"] == "USER_EXISTS"

    # Duplicate email
    res_dup_email = client.post("/api/auth/register", json={
        "username": "other_username",
        "email": "duplicate@example.com",
        "password": "SecurePass123"
    })
    assert res_dup_email.status_code == 409
    assert res_dup_email.get_json()["error"]["code"] == "USER_EXISTS"


def test_registration_invalid_username_handling(client):
    """Verify invalid usernames are rejected with 400 VALIDATION_ERROR."""
    # Username with spaces (Full Name style)
    res_spaces = client.post("/api/auth/register", json={
        "username": "Alex Morgan",
        "email": "alex@example.com",
        "password": "SecurePass123"
    })
    assert res_spaces.status_code == 400
    assert res_spaces.get_json()["error"]["code"] == "VALIDATION_ERROR"

    # Username too short (<3 chars)
    res_short = client.post("/api/auth/register", json={
        "username": "ab",
        "email": "ab@example.com",
        "password": "SecurePass123"
    })
    assert res_short.status_code == 400
    assert res_short.get_json()["error"]["code"] == "VALIDATION_ERROR"

    # Username with special characters
    res_special = client.post("/api/auth/register", json={
        "username": "alex@admin!",
        "email": "special@example.com",
        "password": "SecurePass123"
    })
    assert res_special.status_code == 400
    assert res_special.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_registration_password_validation(client):
    """Verify password rules (min 8 chars, letters, numbers) are enforced."""
    # Under 8 chars
    res_short = client.post("/api/auth/register", json={
        "username": "valid_user_1",
        "email": "valid1@example.com",
        "password": "Pass1"
    })
    assert res_short.status_code == 400
    assert res_short.get_json()["error"]["code"] == "VALIDATION_ERROR"

    # Missing numbers
    res_no_num = client.post("/api/auth/register", json={
        "username": "valid_user_2",
        "email": "valid2@example.com",
        "password": "PasswordOnly"
    })
    assert res_no_num.status_code == 400
    assert res_no_num.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_success_using_username(client):
    """Verify login succeeds using username, sets session cookie, and returns CSRF token."""
    client.post("/api/auth/register", json={
        "username": "login_user_a",
        "email": "logina@example.com",
        "password": "Password123"
    })

    res = client.post("/api/auth/login", json={
        "username_or_email": "login_user_a",
        "password": "Password123"
    })
    assert res.status_code == 200
    assert res.is_json
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["user"]["username"] == "login_user_a"
    assert "csrf_token" in data["data"]
    # Check session cookie set
    cookies = res.headers.get_all("Set-Cookie")
    assert any("session=" in c for c in cookies)
    assert any("HttpOnly" in c for c in cookies)


def test_login_success_using_email(client):
    """Verify login succeeds using email address."""
    client.post("/api/auth/register", json={
        "username": "login_user_b",
        "email": "loginb@example.com",
        "password": "Password123"
    })

    res = client.post("/api/auth/login", json={
        "username_or_email": "loginb@example.com",
        "password": "Password123"
    })
    assert res.status_code == 200
    assert res.get_json()["data"]["user"]["username"] == "login_user_b"


def test_login_incorrect_password(client):
    """Verify wrong password returns 401 INVALID_CREDENTIALS."""
    client.post("/api/auth/register", json={
        "username": "login_user_c",
        "email": "loginc@example.com",
        "password": "Password123"
    })

    res = client.post("/api/auth/login", json={
        "username_or_email": "login_user_c",
        "password": "WrongPassword999"
    })
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_rate_limiting(client):
    """Verify rate-limiting triggers after 5 failed attempts within 300 seconds."""
    client.post("/api/auth/register", json={
        "username": "throttle_target",
        "email": "throttle@example.com",
        "password": "Password123"
    })

    for _ in range(5):
        r = client.post("/api/auth/login", json={
            "username_or_email": "throttle_target",
            "password": "BadPassword1"
        })
        assert r.status_code == 401

    # 6th attempt should be rate limited (429)
    res_throttled = client.post("/api/auth/login", json={
        "username_or_email": "throttle_target",
        "password": "BadPassword1"
    })
    assert res_throttled.status_code == 429
    assert res_throttled.get_json()["error"]["code"] == "RATE_LIMITED"


def test_session_persistence_after_login(client):
    """Verify session cookie persists across requests and authenticates /api/auth/me."""
    client.post("/api/auth/register", json={
        "username": "persist_user",
        "email": "persist@example.com",
        "password": "Password123"
    })

    # Login
    login_res = client.post("/api/auth/login", json={
        "username_or_email": "persist_user",
        "password": "Password123"
    })
    assert login_res.status_code == 200

    # Test /api/auth/me with persistent test client session
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.get_json()["data"]["user"]["username"] == "persist_user"


def test_frontend_auth_html_form_elements(client):
    """Verify register.html and login.html contain aligned input IDs and script dependencies."""
    # register.html
    res_reg = client.get("/register.html")
    assert res_reg.status_code == 200
    assert b'id="register-username"' in res_reg.data
    assert b'name="username"' in res_reg.data
    assert b'js/api.js' in res_reg.data
    assert b'js/auth-validation.js' in res_reg.data

    # login.html
    res_login = client.get("/login.html")
    assert res_login.status_code == 200
    assert b'id="login-email"' in res_login.data
    assert b'name="username_or_email"' in res_login.data
    assert b'js/api.js' in res_login.data
    assert b'js/auth-validation.js' in res_login.data
