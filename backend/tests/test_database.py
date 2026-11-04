import sqlite3
import pytest
from backend.app import database


def test_tables_created(app):
    """Verify all required tables exist in the schema."""
    with app.app_context():
        rows = database.query_db(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        table_names = [row["name"] for row in rows]
        required_tables = [
            "users",
            "saved_analyses",
            "feedback",
            "model_metadata",
            "audit_logs",
        ]
        for tbl in required_tables:
            assert tbl in table_names, f"Table '{tbl}' is missing from schema."


def test_user_insertion_and_unique_constraints(app):
    """Verify user creation and uniqueness constraints on username and email."""
    with app.app_context():
        # Insert a user
        user_id = database.execute_db(
            """INSERT INTO users (username, email, password_hash, role)
               VALUES (?, ?, ?, ?);""",
            ("testuser", "test@example.com", "dummy_hash", "user")
        )
        assert user_id > 0

        # Query back
        user = database.query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
        assert user["username"] == "testuser"
        assert user["email"] == "test@example.com"
        assert user["role"] == "user"
        assert user["is_active"] == 1

        # Duplicate username should raise IntegrityError
        with pytest.raises(sqlite3.IntegrityError):
            database.execute_db(
                """INSERT INTO users (username, email, password_hash, role)
                   VALUES (?, ?, ?, ?);""",
                ("testuser", "different@example.com", "dummy_hash2", "user")
            )

        # Duplicate email should raise IntegrityError
        with pytest.raises(sqlite3.IntegrityError):
            database.execute_db(
                """INSERT INTO users (username, email, password_hash, role)
                   VALUES (?, ?, ?, ?);""",
                ("differentuser", "test@example.com", "dummy_hash3", "user")
            )


def test_user_role_check_constraint(app):
    """Verify invalid roles are rejected by the CHECK constraint."""
    with app.app_context():
        with pytest.raises(sqlite3.IntegrityError):
            database.execute_db(
                """INSERT INTO users (username, email, password_hash, role)
                   VALUES (?, ?, ?, ?);""",
                ("hacker", "hacker@example.com", "dummy_hash", "superadmin")
            )


def test_foreign_key_and_cascade_delete(app):
    """Verify foreign key enforcement and cascade deletion on saved_analyses."""
    with app.app_context():
        # Inserting analysis for nonexistent user must fail FK constraint
        with pytest.raises(sqlite3.IntegrityError):
            database.execute_db(
                """INSERT INTO saved_analyses (user_id, text_content, category)
                   VALUES (?, ?, ?);""",
                (9999, "Some offensive message", "Insult")
            )

        # Create valid user
        user_id = database.execute_db(
            """INSERT INTO users (username, email, password_hash, role)
               VALUES (?, ?, ?, ?);""",
            ("john_doe", "john@example.com", "dummy_hash", "user")
        )

        # Insert saved analysis for this user
        analysis_id = database.execute_db(
            """INSERT INTO saved_analyses (user_id, text_content, category, confidence)
               VALUES (?, ?, ?, ?);""",
            (user_id, "Some test message", "Insult", 0.88)
        )
        assert analysis_id > 0

        # Verify it exists
        saved = database.query_db(
            "SELECT * FROM saved_analyses WHERE id = ?", (analysis_id,), one=True
        )
        assert saved["text_content"] == "Some test message"

        # Delete the user; cascade must remove their saved analyses
        database.execute_db("DELETE FROM users WHERE id = ?", (user_id,))
        remaining = database.query_db(
            "SELECT * FROM saved_analyses WHERE id = ?", (analysis_id,), one=True
        )
        assert remaining is None


def test_feedback_check_constraints(app):
    """Verify constraints on feedback table (type and rating)."""
    with app.app_context():
        user_id = database.execute_db(
            """INSERT INTO users (username, email, password_hash, role)
               VALUES (?, ?, ?, ?);""",
            ("fb_user", "fb@example.com", "dummy_hash", "user")
        )

        # Valid feedback
        fb_id = database.execute_db(
            """INSERT INTO feedback (user_id, feedback_type, rating, comment)
               VALUES (?, ?, ?, ?);""",
            (user_id, "general", 4, "Great platform")
        )
        assert fb_id > 0

        # Invalid feedback_type should fail
        with pytest.raises(sqlite3.IntegrityError):
            database.execute_db(
                """INSERT INTO feedback (user_id, feedback_type, rating)
                   VALUES (?, ?, ?);""",
                (user_id, "invalid_type", 5)
            )

        # Rating outside 1-5 should fail
        with pytest.raises(sqlite3.IntegrityError):
            database.execute_db(
                """INSERT INTO feedback (user_id, feedback_type, rating)
                   VALUES (?, ?, ?);""",
                (user_id, "general", 6)
            )


def test_audit_log_insertion(app):
    """Verify audit log records actions without sensitive message content."""
    with app.app_context():
        log_id = database.execute_db(
            """INSERT INTO audit_logs (action, ip_address, details)
               VALUES (?, ?, ?);""",
            ("SYSTEM_BOOT", "127.0.0.1", "Schema verified successfully")
        )
        assert log_id > 0

        log = database.query_db("SELECT * FROM audit_logs WHERE id = ?", (log_id,), one=True)
        assert log["action"] == "SYSTEM_BOOT"
        assert log["details"] == "Schema verified successfully"

