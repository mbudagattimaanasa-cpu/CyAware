import json
import pytest
from backend.app.database import execute_db, query_db, get_db


def _register_and_login(client, username="del_user", email="del@example.com", password="Password123"):
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


def test_delete_account_unauthenticated_rejected(client):
    """Verify DELETE /api/user/account without authentication returns 401 UNAUTHENTICATED with no-store."""
    res = client.delete("/api/user/account")
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHENTICATED"
    assert res.headers.get("Cache-Control") == "no-store"


def test_delete_account_missing_csrf_rejected(client):
    """Verify authenticated DELETE /api/user/account without X-CSRF-Token returns 403 CSRF_ERROR."""
    _register_and_login(client, "csrf_miss", "csrf_miss@example.com")
    res = client.delete("/api/user/account")
    assert res.status_code == 403
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "CSRF_ERROR"
    assert res.headers.get("Cache-Control") == "no-store"


def test_delete_account_invalid_csrf_rejected(client):
    """Verify authenticated DELETE /api/user/account with invalid X-CSRF-Token returns 403 CSRF_ERROR."""
    _register_and_login(client, "csrf_bad", "csrf_bad@example.com")
    res = client.delete("/api/user/account", headers={"X-CSRF-Token": "invalid_token_12345"})
    assert res.status_code == 403
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "CSRF_ERROR"
    assert res.headers.get("Cache-Control") == "no-store"


def test_delete_account_success(client):
    """Verify authenticated user can delete their own account with valid CSRF."""
    auth = _register_and_login(client, "alice_del", "alice_del@example.com")
    user_id = auth["user"]["id"]
    csrf_token = auth["csrf_token"]

    res = client.delete("/api/user/account", headers={"X-CSRF-Token": csrf_token})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "permanently deleted" in data["message"]

    # Verify user is deleted from database
    user = query_db("SELECT * FROM users WHERE id = ?;", (user_id,), one=True)
    assert user is None


def test_delete_account_removes_user_and_feedback(client):
    """Verify user feedback is explicitly pruned from database upon account deletion."""
    auth = _register_and_login(client, "bob_del", "bob_del@example.com")
    user_id = auth["user"]["id"]
    csrf_token = auth["csrf_token"]

    # Create feedback for user
    fb_id = execute_db(
        "INSERT INTO feedback (user_id, feedback_type, comment) VALUES (?, 'general', 'Bob feedback');",
        (user_id,)
    )

    res = client.delete("/api/user/account", headers={"X-CSRF-Token": csrf_token})
    assert res.status_code == 200

    # Verify feedback was deleted
    fb_rows = query_db("SELECT * FROM feedback WHERE user_id = ?;", (user_id,))
    assert len(fb_rows) == 0


def test_delete_account_cascades_saved_analyses(client):
    """Verify saved analyses are deleted via foreign-key cascade upon account deletion."""
    auth = _register_and_login(client, "charlie_del", "charlie_del@example.com")
    user_id = auth["user"]["id"]
    csrf_token = auth["csrf_token"]

    # Insert saved analysis for user
    a_id = execute_db(
        "INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Charlie note', 'Normal');",
        (user_id,)
    )

    res = client.delete("/api/user/account", headers={"X-CSRF-Token": csrf_token})
    assert res.status_code == 200

    # Verify saved analyses cascaded
    a_rows = query_db("SELECT * FROM saved_analyses WHERE user_id = ?;", (user_id,))
    assert len(a_rows) == 0


def test_delete_account_anonymized_audit_log(client):
    """Verify deletion creates an anonymized ACCOUNT_DELETED audit log with user_id=NULL and ip_address=NULL."""
    auth = _register_and_login(client, "dana_del", "dana_del@example.com")
    csrf_token = auth["csrf_token"]

    res = client.delete("/api/user/account", headers={"X-CSRF-Token": csrf_token})
    assert res.status_code == 200

    # Check the newest audit log
    audit = query_db(
        "SELECT * FROM audit_logs WHERE action = 'ACCOUNT_DELETED' ORDER BY id DESC;",
        one=True
    )
    assert audit is not None
    assert audit["user_id"] is None
    assert audit["ip_address"] is None
    assert audit["details"] == "User account closed"


def test_delete_account_session_cleared_on_success(client):
    """Verify subsequent requests using the client's session are rejected with 401 after deletion."""
    auth = _register_and_login(client, "eve_del", "eve_del@example.com")
    csrf_token = auth["csrf_token"]

    # Delete account
    res = client.delete("/api/user/account", headers={"X-CSRF-Token": csrf_token})
    assert res.status_code == 200

    # Subsequent request using the same client cookies must be rejected with 401
    res_sub = client.get("/api/user/export")
    assert res_sub.status_code == 401
    assert res_sub.get_json()["error"]["code"] == "UNAUTHENTICATED"


def test_delete_account_session_preserved_on_failure(client):
    """Verify session is preserved if account deletion fails or is rejected."""
    # Create an admin user and login
    execute_db(
        "INSERT INTO users (username, email, password_hash, role) VALUES ('admin_sess', 'admin_sess@example.com', 'hash', 'admin');"
    )
    # Login as admin via direct test login
    with client.session_transaction() as sess:
        admin_row = query_db("SELECT id FROM users WHERE username = 'admin_sess';", one=True)
        sess["user_id"] = admin_row["id"]
        sess["csrf_token"] = "valid_admin_csrf_token"

    res = client.delete("/api/user/account", headers={"X-CSRF-Token": "valid_admin_csrf_token"})
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "ADMIN_ACCOUNT_DELETION_NOT_ALLOWED"

    # Confirm session is still active
    with client.session_transaction() as sess:
        assert sess.get("user_id") == admin_row["id"]

    res_me = client.get("/api/auth/me")
    assert res_me.status_code == 200
    assert res_me.get_json()["data"]["user"]["username"] == "admin_sess"


def test_delete_account_admin_self_service_rejected(client):
    """Verify Admin cannot self-delete account through DELETE /api/user/account."""
    execute_db(
        "INSERT INTO users (username, email, password_hash, role) VALUES ('admin_self', 'admin_self@example.com', 'hash', 'admin');"
    )
    admin_row = query_db("SELECT id FROM users WHERE username = 'admin_self';", one=True)

    with client.session_transaction() as sess:
        sess["user_id"] = admin_row["id"]
        sess["csrf_token"] = "admin_csrf"

    res = client.delete("/api/user/account", headers={"X-CSRF-Token": "admin_csrf"})
    assert res.status_code == 403
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "ADMIN_ACCOUNT_DELETION_NOT_ALLOWED"

    # Verify admin record remains in database
    u = query_db("SELECT * FROM users WHERE id = ?;", (admin_row["id"],), one=True)
    assert u is not None
    assert u["role"] == "admin"


def test_delete_account_ownership_isolation_and_tampering(client):
    """Verify User A calling DELETE /api/user/account?user_id=<User B ID> deletes exclusively User A."""
    auth_a = _register_and_login(client, "user_del_a", "del_a@example.com")
    user_a_id = auth_a["user"]["id"]
    csrf_a = auth_a["csrf_token"]

    # User B inserted directly in DB with saved analysis
    user_b_id = execute_db("INSERT INTO users (username, email, password_hash) VALUES ('user_del_b', 'del_b@example.com', 'hash');")
    b_analysis_id = execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'User B note', 'Normal');", (user_b_id,))

    # User A calls DELETE with ?user_id=<User B ID>
    res = client.delete(f"/api/user/account?user_id={user_b_id}", headers={"X-CSRF-Token": csrf_a})
    assert res.status_code == 200

    # User A is deleted
    assert query_db("SELECT * FROM users WHERE id = ?;", (user_a_id,), one=True) is None

    # User B and User B's records are completely untouched
    user_b = query_db("SELECT * FROM users WHERE id = ?;", (user_b_id,), one=True)
    assert user_b is not None
    assert user_b["username"] == "user_del_b"

    b_analyses = query_db("SELECT * FROM saved_analyses WHERE user_id = ?;", (user_b_id,))
    assert len(b_analyses) == 1
    assert b_analyses[0]["id"] == b_analysis_id


def test_delete_account_inactive_rejected(client):
    """Verify deactivated user account (is_active = 0) is rejected."""
    auth = _register_and_login(client, "inact_user", "inact@example.com")
    user_id = auth["user"]["id"]
    csrf_token = auth["csrf_token"]

    # Deactivate user in database
    execute_db("UPDATE users SET is_active = 0 WHERE id = ?;", (user_id,))

    res = client.delete("/api/user/account", headers={"X-CSRF-Token": csrf_token})
    # Handled by @login_required (401 UNAUTHENTICATED) or service (400 ACCOUNT_INACTIVE)
    assert res.status_code in (400, 401)
    assert res.get_json()["success"] is False

    # Confirm user row still exists in database
    u = query_db("SELECT * FROM users WHERE id = ?;", (user_id,), one=True)
    assert u is not None


def test_delete_account_cache_control_header(client):
    """Verify Cache-Control: no-store header is set on account deletion responses."""
    auth = _register_and_login(client, "cache_del_user", "cache_del@example.com")
    csrf_token = auth["csrf_token"]

    res = client.delete("/api/user/account", headers={"X-CSRF-Token": csrf_token})
    assert res.status_code == 200
    assert res.headers.get("Cache-Control") == "no-store"


def test_delete_account_rollback_on_injected_failure(client, monkeypatch):
    """Verify database changes roll back cleanly and session is preserved if an exception occurs during deletion."""
    auth = _register_and_login(client, "fail_user", "fail@example.com")
    user_id = auth["user"]["id"]
    csrf_token = auth["csrf_token"]

    # Insert saved analysis and feedback
    a_id = execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Fail note', 'Normal');", (user_id,))
    f_id = execute_db("INSERT INTO feedback (user_id, feedback_type, comment) VALUES (?, 'general', 'Fail fb');", (user_id,))

    real_db = get_db()

    class FaultyDBWrapper:
        def __init__(self, db):
            self._db = db

        def execute(self, sql, *args):
            if "DELETE FROM users" in sql:
                raise RuntimeError("Simulated failure during user deletion")
            return self._db.execute(sql, *args)

        def rollback(self):
            return self._db.rollback()

        def commit(self):
            return self._db.commit()

        def __getattr__(self, name):
            return getattr(self._db, name)

    faulty_wrapper = FaultyDBWrapper(real_db)
    monkeypatch.setattr("backend.app.services.user_service.get_db", lambda: faulty_wrapper)

    # Calling delete should encounter the error (caught and handled as 500)
    res = client.delete("/api/user/account", headers={"X-CSRF-Token": csrf_token})
    assert res.status_code == 500

    # Verify actual database state: user, feedback, and analyses remain intact!
    u = query_db("SELECT * FROM users WHERE id = ?;", (user_id,), one=True)
    assert u is not None
    assert u["username"] == "fail_user"

    analyses = query_db("SELECT * FROM saved_analyses WHERE user_id = ?;", (user_id,))
    assert len(analyses) == 1

    feedback = query_db("SELECT * FROM feedback WHERE user_id = ?;", (user_id,))
    assert len(feedback) == 1

    # Verify session is preserved
    with client.session_transaction() as sess:
        assert sess.get("user_id") == user_id

