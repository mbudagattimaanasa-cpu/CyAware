import json
import pytest
from backend.app.database import execute_db, query_db


def _register_and_login(client, username="export_user", email="export@example.com", password="Password123"):
    """Helper to register and login a user, returning user data and CSRF token."""
    client.post("/api/auth/register", json={
        "username": username,
        "email": email,
        "password": password
    })
    res = client.post("/api/auth/login", json={
        "username_or_email": username,
        "password": password
    })
    data = res.get_json()["data"]
    return {
        "user": data["user"],
        "csrf_token": data["csrf_token"]
    }


def test_export_unauthenticated_rejected(client):
    """Verify GET /api/user/export without authentication returns 401 UNAUTHENTICATED with no-store cache header."""
    res = client.get("/api/user/export")
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHENTICATED"
    assert res.headers.get("Cache-Control") == "no-store"


def test_export_success_with_complete_data(client):
    """Verify authenticated user can export their profile, saved analyses, and feedback."""
    auth = _register_and_login(client, "export_alice", "alice@example.com")
    user_id = auth["user"]["id"]

    # Insert saved analysis
    analysis_id = execute_db(
        """
        INSERT INTO saved_analyses (user_id, text_content, category, confidence, explanation, highlighted_terms_json)
        VALUES (?, 'Alice saved note', 'Normal', 0.94, 'Safe content', ?);
        """,
        (user_id, json.dumps(["alice"]))
    )

    # Insert feedback
    fb_id = execute_db(
        """
        INSERT INTO feedback (analysis_id, user_id, feedback_type, rating, comment)
        VALUES (?, ?, 'general', 5, 'Great analysis');
        """,
        (analysis_id, user_id)
    )

    res = client.get("/api/user/export")
    assert res.status_code == 200
    assert res.headers.get("Cache-Control") == "no-store"

    data = res.get_json()["data"]
    assert "user" in data
    assert "saved_analyses" in data
    assert "feedback" in data

    # Verify user profile
    profile = data["user"]
    assert profile["id"] == user_id
    assert profile["username"] == "export_alice"
    assert profile["email"] == "alice@example.com"
    assert "password_hash" not in profile

    # Verify saved analysis
    analyses = data["saved_analyses"]
    assert len(analyses) == 1
    assert analyses[0]["id"] == analysis_id
    assert analyses[0]["text_content"] == "Alice saved note"
    assert analyses[0]["highlighted_terms"] == ["alice"]

    # Verify feedback
    feedback = data["feedback"]
    assert len(feedback) == 1
    assert feedback[0]["id"] == fb_id
    assert feedback[0]["comment"] == "Great analysis"


def test_export_ownership_isolation(client):
    """Verify User A's export contains exclusively User A's records and never User B's data."""
    auth_a = _register_and_login(client, "export_user_a", "usera@example.com")
    user_a_id = auth_a["user"]["id"]

    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'User A note', 'Normal');", (user_a_id,))
    execute_db("INSERT INTO feedback (user_id, feedback_type, comment) VALUES (?, 'general', 'User A feedback');", (user_a_id,))

    # Insert User B in database directly
    user_b_id = execute_db("INSERT INTO users (username, email, password_hash) VALUES ('export_user_b', 'userb@example.com', 'hash');")
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'User B secret note', 'Threat');", (user_b_id,))
    execute_db("INSERT INTO feedback (user_id, feedback_type, comment) VALUES (?, 'general', 'User B private feedback');", (user_b_id,))

    res = client.get("/api/user/export")
    assert res.status_code == 200
    data = res.get_json()["data"]

    # Check analyses isolation
    assert len(data["saved_analyses"]) == 1
    assert data["saved_analyses"][0]["text_content"] == "User A note"

    # Check feedback isolation
    assert len(data["feedback"]) == 1
    assert data["feedback"][0]["comment"] == "User A feedback"


def test_export_ignores_user_id_query_parameter(client):
    """Verify passing user_id in query string does not change export scope."""
    auth_a = _register_and_login(client, "export_tom", "tom@example.com")
    user_a_id = auth_a["user"]["id"]

    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Tom private', 'Normal');", (user_a_id,))

    user_b_id = execute_db("INSERT INTO users (username, email, password_hash) VALUES ('export_jerry', 'jerry@example.com', 'hash');")
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Jerry private', 'Insult');", (user_b_id,))

    res = client.get(f"/api/user/export?user_id={user_b_id}")
    assert res.status_code == 200
    data = res.get_json()["data"]

    assert data["user"]["username"] == "export_tom"
    assert len(data["saved_analyses"]) == 1
    assert data["saved_analyses"][0]["text_content"] == "Tom private"


def test_export_credential_exclusion(client):
    """Verify password_hash, password, csrf_token, and session secrets are completely absent from export payload."""
    auth = _register_and_login(client, "export_sec", "sec@example.com")
    user_id = auth["user"]["id"]

    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Note', 'Normal');", (user_id,))

    res = client.get("/api/user/export")
    assert res.status_code == 200
    raw_text = res.get_data(as_text=True)

    assert "password_hash" not in raw_text.lower()
    assert "password" not in raw_text.lower()
    assert "csrf_token" not in raw_text.lower()
    assert auth["csrf_token"] not in raw_text


def test_export_audit_log_exclusion(client):
    """Verify audit_logs records are completely absent from export payload."""
    auth = _register_and_login(client, "export_audit", "audit@example.com")
    user_id = auth["user"]["id"]

    # Record an audit log for this user
    execute_db(
        "INSERT INTO audit_logs (user_id, action, details) VALUES (?, 'TEST_ACTION', 'Confidential audit entry');",
        (user_id,)
    )

    res = client.get("/api/user/export")
    assert res.status_code == 200
    data = res.get_json()["data"]

    assert "audit_logs" not in data
    assert "audit" not in data
    assert "Confidential audit entry" not in res.get_data(as_text=True)


def test_export_cache_control_header(client):
    """Verify Cache-Control: no-store header is set on responses."""
    _register_and_login(client, "export_cache", "cache@example.com")
    res = client.get("/api/user/export")
    assert res.status_code == 200
    assert res.headers.get("Cache-Control") == "no-store"


def test_export_empty_records(client):
    """Verify a user with no saved analyses and no feedback receives empty lists."""
    _register_and_login(client, "export_empty", "empty@example.com")
    res = client.get("/api/user/export")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["saved_analyses"] == []
    assert data["feedback"] == []
    assert data["user"]["username"] == "export_empty"


def test_export_deactivated_account_rejected(client):
    """Verify deactivated user account (is_active = 0) is rejected with 401 UNAUTHENTICATED."""
    auth = _register_and_login(client, "export_deact", "deact@example.com")
    user_id = auth["user"]["id"]

    # Deactivate account in database
    execute_db("UPDATE users SET is_active = 0 WHERE id = ?;", (user_id,))

    res = client.get("/api/user/export")
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "UNAUTHENTICATED"
    assert res.headers.get("Cache-Control") == "no-store"


def test_export_deterministic_ordering_for_analyses_and_feedback(client):
    """Verify analyses and feedback are deterministically ordered by timestamp DESC, id DESC."""
    auth = _register_and_login(client, "export_order", "order@example.com")
    user_id = auth["user"]["id"]

    fixed_ts = "2026-11-07 10:00:00"

    # Insert 3 analyses with identical timestamp
    a1 = execute_db("INSERT INTO saved_analyses (user_id, text_content, category, saved_at) VALUES (?, 'Analysis 1', 'Normal', ?);", (user_id, fixed_ts))
    a2 = execute_db("INSERT INTO saved_analyses (user_id, text_content, category, saved_at) VALUES (?, 'Analysis 2', 'Normal', ?);", (user_id, fixed_ts))
    a3 = execute_db("INSERT INTO saved_analyses (user_id, text_content, category, saved_at) VALUES (?, 'Analysis 3', 'Normal', ?);", (user_id, fixed_ts))

    # Insert 3 feedback items with identical timestamp
    f1 = execute_db("INSERT INTO feedback (user_id, feedback_type, comment, created_at) VALUES (?, 'general', 'FB 1', ?);", (user_id, fixed_ts))
    f2 = execute_db("INSERT INTO feedback (user_id, feedback_type, comment, created_at) VALUES (?, 'general', 'FB 2', ?);", (user_id, fixed_ts))
    f3 = execute_db("INSERT INTO feedback (user_id, feedback_type, comment, created_at) VALUES (?, 'general', 'FB 3', ?);", (user_id, fixed_ts))

    res = client.get("/api/user/export")
    assert res.status_code == 200
    data = res.get_json()["data"]

    # Analyses order: a3, a2, a1
    analyses_ids = [item["id"] for item in data["saved_analyses"]]
    assert analyses_ids == [a3, a2, a1]

    # Feedback order: f3, f2, f1
    feedback_ids = [item["id"] for item in data["feedback"]]
    assert feedback_ids == [f3, f2, f1]


def test_export_service_reuse(client, monkeypatch):
    """Verify route directly reuses get_user_export_data service."""
    auth = _register_and_login(client, "export_mock", "mock@example.com")
    user_id = auth["user"]["id"]

    called = []
    import backend.app.routes.user as user_module

    orig_func = user_module.get_user_export_data

    def tracked_func(uid):
        called.append(uid)
        return orig_func(uid)

    monkeypatch.setattr(user_module, "get_user_export_data", tracked_func)

    res = client.get("/api/user/export")
    assert res.status_code == 200
    assert called == [user_id]


def test_export_missing_user_returns_404(client, monkeypatch):
    """Verify if user service returns None, route returns 404 USER_NOT_FOUND with Cache-Control: no-store."""
    auth = _register_and_login(client, "export_nf", "nf@example.com")

    import backend.app.routes.user as user_module
    monkeypatch.setattr(user_module, "get_user_export_data", lambda uid: None)

    res = client.get("/api/user/export")
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "USER_NOT_FOUND"
    assert res.headers.get("Cache-Control") == "no-store"

