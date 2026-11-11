import json
import pytest
from werkzeug.security import generate_password_hash
from backend.app.database import get_db, execute_db, query_db
from backend.app.services.user_service import delete_user_account, get_user_export_data


def _create_test_user(username="testuser", email="test@example.com", role="user", is_active=1):
    """Helper to insert a user directly for service testing."""
    pw_hash = generate_password_hash("ValidPass123!")
    user_id = execute_db(
        """
        INSERT INTO users (username, email, password_hash, role, is_active)
        VALUES (?, ?, ?, ?, ?);
        """,
        (username, email, pw_hash, role, is_active)
    )
    return user_id


def test_delete_user_account_success(app):
    """Verify successful deletion of standard user account, cascading analyses, pruning feedback, and logging anonymized audit event."""
    with app.app_context():
        user_id = _create_test_user("alice", "alice@example.com", role="user")

        # Create saved analysis
        analysis_id = execute_db(
            """
            INSERT INTO saved_analyses (user_id, text_content, category, confidence, explanation, highlighted_terms_json)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (user_id, "Sample message", "Normal", 0.95, "Safe message", json.dumps(["sample"]))
        )

        # Create feedback
        fb_id = execute_db(
            """
            INSERT INTO feedback (analysis_id, user_id, feedback_type, comment)
            VALUES (?, ?, ?, ?);
            """,
            (analysis_id, user_id, "general", "Great prediction")
        )

        success, err, status = delete_user_account(user_id, is_self_service=True)
        assert success is True
        assert err is None
        assert status == 200

        # Verify user is deleted
        u = query_db("SELECT * FROM users WHERE id = ?;", (user_id,), one=True)
        assert u is None

        # Verify saved_analyses cascaded
        a = query_db("SELECT * FROM saved_analyses WHERE user_id = ?;", (user_id,))
        assert len(a) == 0

        # Verify feedback was pruned
        fb = query_db("SELECT * FROM feedback WHERE user_id = ?;", (user_id,))
        assert len(fb) == 0

        # Verify audit log contains anonymized ACCOUNT_DELETED event
        audit = query_db(
            "SELECT * FROM audit_logs WHERE action = 'ACCOUNT_DELETED' ORDER BY id DESC;",
            one=True
        )
        assert audit is not None
        assert audit["user_id"] is None
        assert audit["ip_address"] is None
        assert "alice" not in audit["details"]
        assert "alice@example.com" not in audit["details"]


def test_delete_user_account_missing_user(app):
    """Verify non-existent user ID returns 404 USER_NOT_FOUND."""
    with app.app_context():
        success, err, status = delete_user_account(99999, is_self_service=True)
        assert success is False
        assert err == "USER_NOT_FOUND"
        assert status == 404


def test_delete_user_account_inactive_user(app):
    """Verify inactive account is rejected with 400 ACCOUNT_INACTIVE."""
    with app.app_context():
        user_id = _create_test_user("inactive_user", "inactive@example.com", is_active=0)
        success, err, status = delete_user_account(user_id, is_self_service=True)
        assert success is False
        assert err == "ACCOUNT_INACTIVE"
        assert status == 400

        # Ensure user was not deleted
        u = query_db("SELECT * FROM users WHERE id = ?;", (user_id,), one=True)
        assert u is not None


def test_delete_user_account_admin_self_service_rejected(app):
    """Verify Admin cannot delete their own account via self-service."""
    with app.app_context():
        admin_id = _create_test_user("admin1", "admin1@example.com", role="admin")
        success, err, status = delete_user_account(admin_id, is_self_service=True)
        assert success is False
        assert err == "ADMIN_ACCOUNT_DELETION_NOT_ALLOWED"
        assert status == 403

        # Ensure admin remains intact
        u = query_db("SELECT * FROM users WHERE id = ?;", (admin_id,), one=True)
        assert u is not None


def test_delete_user_account_last_admin_protected(app):
    """Verify last active Admin cannot be deleted even via non-self-service deletion."""
    with app.app_context():
        admin_id = _create_test_user("sole_admin", "sole_admin@example.com", role="admin")
        # is_self_service=False represents an administrative deletion path
        success, err, status = delete_user_account(admin_id, is_self_service=False)
        assert success is False
        assert err == "LAST_ADMIN_PROTECTED"
        assert status == 403

        # Ensure sole admin remains intact
        u = query_db("SELECT * FROM users WHERE id = ?;", (admin_id,), one=True)
        assert u is not None


def test_delete_user_account_non_last_admin_allowed(app):
    """Verify non-last active Admin can be deleted through non-self-service deletion."""
    with app.app_context():
        admin1_id = _create_test_user("admin_a", "admin_a@example.com", role="admin")
        _create_test_user("admin_b", "admin_b@example.com", role="admin")

        success, err, status = delete_user_account(admin1_id, is_self_service=False)
        assert success is True
        assert err is None
        assert status == 200

        # Verify admin1 is deleted
        u = query_db("SELECT * FROM users WHERE id = ?;", (admin1_id,), one=True)
        assert u is None


def test_delete_user_account_transaction_state_conflict(app):
    """Verify unexpected active transaction aborts safely without committing someone else's work."""
    with app.app_context():
        user_id = _create_test_user("bob", "bob@example.com")
        db = get_db()
        # Start an uncommitted transaction with a draft feedback record
        db.execute("INSERT INTO feedback (user_id, feedback_type, comment) VALUES (?, 'general', 'Uncommitted draft');", (user_id,))
        assert db.in_transaction is True

        # Call delete_user_account while an uncommitted transaction is open
        success, err, status = delete_user_account(user_id, is_self_service=True)
        assert success is False
        assert err == "TRANSACTION_STATE_CONFLICT"
        assert status == 500

        # Assert immediately that the transaction remains open and uncommitted data is preserved
        assert db.in_transaction is True
        row = db.execute("SELECT * FROM feedback WHERE comment = 'Uncommitted draft';").fetchone()
        assert row is not None
        user_row = db.execute("SELECT * FROM users WHERE id = ?;", (user_id,)).fetchone()
        assert user_row is not None

        # Manually rollback to verify the row was indeed uncommitted
        db.rollback()
        assert db.in_transaction is False
        fb = query_db("SELECT * FROM feedback WHERE comment = 'Uncommitted draft';")
        assert len(fb) == 0


def test_delete_user_account_rollback_on_failure(app, monkeypatch):
    """Verify transaction rolls back cleanly if an unexpected error occurs during deletion."""
    with app.app_context():
        user_id = _create_test_user("charlie", "charlie@example.com")

        # Create at least one saved analysis
        analysis_id = execute_db(
            """
            INSERT INTO saved_analyses (user_id, text_content, category, confidence, explanation)
            VALUES (?, ?, ?, ?, ?);
            """,
            (user_id, "Charlie's text", "Normal", 0.90, "Safe text")
        )

        # Create at least one feedback record
        fb_id = execute_db(
            """
            INSERT INTO feedback (analysis_id, user_id, feedback_type, comment)
            VALUES (?, ?, ?, ?);
            """,
            (analysis_id, user_id, "general", "Charlie's feedback")
        )

        # Count existing ACCOUNT_DELETED audit events before the attempt
        initial_audit_count = query_db(
            "SELECT COUNT(*) AS c FROM audit_logs WHERE action = 'ACCOUNT_DELETED';",
            one=True
        )["c"]

        real_db = get_db()

        class FaultyDBWrapper:
            def __init__(self, db):
                self._db = db

            def execute(self, sql, *args):
                # Fails when executing user deletion, after feedback deletion and audit log insert
                if "DELETE FROM users" in sql:
                    raise RuntimeError("Simulated database failure during user delete")
                return self._db.execute(sql, *args)

            def rollback(self):
                return self._db.rollback()

            def commit(self):
                return self._db.commit()

            def __getattr__(self, name):
                return getattr(self._db, name)

        faulty_wrapper = FaultyDBWrapper(real_db)
        monkeypatch.setattr("backend.app.services.user_service.get_db", lambda: faulty_wrapper)

        with pytest.raises(RuntimeError, match="Simulated database failure"):
            delete_user_account(user_id, is_self_service=True)

        # Verify actual database state after failure:
        # 1. User still exists
        u = query_db("SELECT * FROM users WHERE id = ?;", (user_id,), one=True)
        assert u is not None
        assert u["username"] == "charlie"

        # 2. Saved analysis still exists
        analyses = query_db("SELECT * FROM saved_analyses WHERE user_id = ?;", (user_id,))
        assert len(analyses) == 1
        assert analyses[0]["id"] == analysis_id

        # 3. Feedback record still exists (verifying feedback deletion was rolled back)
        fb = query_db("SELECT * FROM feedback WHERE user_id = ?;", (user_id,))
        assert len(fb) == 1
        assert fb[0]["id"] == fb_id

        # 4. No new ACCOUNT_DELETED audit event was committed (verifying audit insert was rolled back)
        final_audit_count = query_db(
            "SELECT COUNT(*) AS c FROM audit_logs WHERE action = 'ACCOUNT_DELETED';",
            one=True
        )["c"]
        assert final_audit_count == initial_audit_count


def test_get_user_export_data_complete_and_sanitized(app):
    """Verify export contains only requested user's profile, analyses, feedback and excludes password_hash."""
    with app.app_context():
        user1_id = _create_test_user("dana", "dana@example.com")
        user2_id = _create_test_user("eve", "eve@example.com")

        # User 1 analysis & feedback
        a1_id = execute_db(
            """
            INSERT INTO saved_analyses (user_id, text_content, category, confidence, explanation, highlighted_terms_json, safer_rewrite)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (user1_id, "User 1 content", "Normal", 0.92, "Safe text", json.dumps(["content"]), "Safer text")
        )
        execute_db(
            "INSERT INTO feedback (analysis_id, user_id, feedback_type, rating, comment) VALUES (?, ?, ?, ?, ?);",
            (a1_id, user1_id, "general", 5, "Helpful analysis")
        )

        # User 2 analysis (isolation test)
        execute_db(
            """
            INSERT INTO saved_analyses (user_id, text_content, category, confidence)
            VALUES (?, ?, ?, ?);
            """,
            (user2_id, "User 2 private content", "Insult", 0.88)
        )

        export = get_user_export_data(user1_id)
        assert export is not None
        assert "user" in export
        assert "saved_analyses" in export
        assert "feedback" in export

        # Exclusions
        user_profile = export["user"]
        assert "password_hash" not in user_profile
        assert "password" not in user_profile
        assert "csrf_token" not in user_profile
        assert user_profile["username"] == "dana"
        assert user_profile["email"] == "dana@example.com"

        # Analyses isolation
        analyses = export["saved_analyses"]
        assert len(analyses) == 1
        assert analyses[0]["text_content"] == "User 1 content"
        assert analyses[0]["highlighted_terms"] == ["content"]

        # Feedback
        feedback = export["feedback"]
        assert len(feedback) == 1
        assert feedback[0]["comment"] == "Helpful analysis"
        assert feedback[0]["rating"] == 5

        # Audit logs should NOT be in export
        assert "audit_logs" not in export


def test_get_user_export_data_non_existent(app):
    """Verify export for non-existent user returns None."""
    with app.app_context():
        export = get_user_export_data(99999)
        assert export is None
