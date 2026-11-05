import json
import pytest
from backend.app.database import query_db


@pytest.fixture
def auth_user(client):
    """Helper fixture to create and login a user, returning user data and CSRF token."""
    client.post("/api/auth/register", json={
        "username": "tester_one",
        "email": "tester1@example.com",
        "password": "Password123"
    })
    login_res = client.post("/api/auth/login", json={
        "username_or_email": "tester_one",
        "password": "Password123"
    })
    user_data = login_res.get_json()["data"]
    return {
        "user": user_data["user"],
        "csrf_token": user_data["csrf_token"]
    }


def test_guest_analyze_text_success(client):
    """Verify an unauthenticated guest can analyze text without saving."""
    res = client.post("/api/analyze/text", json={
        "text": "Thank you for the quick assistance and friendly advice."
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["category"] == "Normal"
    assert data["data"]["saved_id"] is None
    assert data["data"]["severity"] is None
    assert 0.0 <= data["data"]["confidence"] <= 1.0


def test_guest_cannot_save_analysis(client):
    """Verify guest passing save=true is rejected with 401 Unauthorized."""
    res = client.post("/api/analyze/text", json={
        "text": "You are completely useless and stupid.",
        "save": True
    })
    assert res.status_code == 401
    err = res.get_json()["error"]
    assert err["code"] == "UNAUTHENTICATED"


def test_guest_analysis_creates_no_database_record(client, app):
    """Verify guest analysis leaves saved_analyses and audit_logs tables untouched for messages."""
    with app.app_context():
        count_before = query_db("SELECT COUNT(*) as cnt FROM saved_analyses", one=True)["cnt"]
        assert count_before == 0

    client.post("/api/analyze/text", json={
        "text": "Some temporary message analyzed by a guest."
    })

    with app.app_context():
        count_after = query_db("SELECT COUNT(*) as cnt FROM saved_analyses", one=True)["cnt"]
        assert count_after == 0


def test_authenticated_analyze_without_saving(client, auth_user, app):
    """Verify an authenticated user with save=false does not persist any record."""
    csrf_token = auth_user["csrf_token"]
    res = client.post(
        "/api/analyze/text",
        json={
            "text": "I am angry with this system, damn it.",
            "save": False
        },
        headers={"X-CSRF-Token": csrf_token}
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["saved_id"] is None

    with app.app_context():
        count = query_db("SELECT COUNT(*) as cnt FROM saved_analyses", one=True)["cnt"]
        assert count == 0


def test_authenticated_analyze_and_save_success(client, auth_user, app):
    """Verify authenticated user can opt-in to save an analysis with CSRF token."""
    user_id = auth_user["user"]["id"]
    csrf_token = auth_user["csrf_token"]

    res = client.post(
        "/api/analyze/text",
        json={
            "text": "You are completely stupid, an absolute idiot.",
            "save": True
        },
        headers={"X-CSRF-Token": csrf_token}
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["category"] == "Insult"
    assert data["saved_id"] is not None
    assert data["severity"] is None
    assert data["safer_rewrite"] is not None
    assert len(data["highlighted_terms"]) > 0

    saved_id = data["saved_id"]

    # Verify database persistence
    with app.app_context():
        row = query_db("SELECT * FROM saved_analyses WHERE id = ?", (saved_id,), one=True)
        assert row is not None
        assert row["user_id"] == user_id
        assert row["category"] == "Insult"
        assert row["text_content"] == "You are completely stupid, an absolute idiot."
        assert row["severity"] is None

        # Verify audit log recorded without the raw text
        audit = query_db(
            "SELECT * FROM audit_logs WHERE action = 'ANALYSIS_SAVED' AND user_id = ?",
            (user_id,),
            one=True
        )
        assert audit is not None
        assert "stupid" not in audit["details"]


def test_authenticated_save_requires_csrf(client, auth_user):
    """Verify that an authenticated state-changing request with save=true enforces CSRF."""
    # Attempt save without X-CSRF-Token header
    res = client.post(
        "/api/analyze/text",
        json={
            "text": "You are completely stupid, an absolute idiot.",
            "save": True
        }
    )
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "CSRF_ERROR"


def test_saved_analysis_ownership_isolation(client, app):
    """Verify strict user ownership isolation between multiple users in saved_analyses."""
    # 1. Register and login User A
    client.post("/api/auth/register", json={
        "username": "user_a",
        "email": "usera@example.com",
        "password": "Password123"
    })
    res_a = client.post("/api/auth/login", json={
        "username_or_email": "user_a",
        "password": "Password123"
    })
    token_a = res_a.get_json()["data"]["csrf_token"]
    user_a_id = res_a.get_json()["data"]["user"]["id"]

    # User A saves an analysis
    save_a = client.post(
        "/api/analyze/text",
        json={"text": "Message for User A", "save": True},
        headers={"X-CSRF-Token": token_a}
    )
    id_a = save_a.get_json()["data"]["saved_id"]

    # Logout User A
    client.post("/api/auth/logout", headers={"X-CSRF-Token": token_a})

    # 2. Register and login User B
    client.post("/api/auth/register", json={
        "username": "user_b",
        "email": "userb@example.com",
        "password": "Password123"
    })
    res_b = client.post("/api/auth/login", json={
        "username_or_email": "user_b",
        "password": "Password123"
    })
    token_b = res_b.get_json()["data"]["csrf_token"]
    user_b_id = res_b.get_json()["data"]["user"]["id"]

    # User B saves an analysis
    save_b = client.post(
        "/api/analyze/text",
        json={"text": "Message for User B", "save": True},
        headers={"X-CSRF-Token": token_b}
    )
    id_b = save_b.get_json()["data"]["saved_id"]

    # 3. Assert database records have distinct user_ids
    with app.app_context():
        record_a = query_db("SELECT * FROM saved_analyses WHERE id = ?", (id_a,), one=True)
        record_b = query_db("SELECT * FROM saved_analyses WHERE id = ?", (id_b,), one=True)

        assert record_a["user_id"] == user_a_id
        assert record_b["user_id"] == user_b_id
        assert record_a["user_id"] != record_b["user_id"]
        assert record_a["text_content"] == "Message for User A"
        assert record_b["text_content"] == "Message for User B"


def test_analyze_text_validation_errors(client):
    """Test validation errors on text input."""
    # Non-JSON
    res1 = client.post("/api/analyze/text", data="plain text not json")
    assert res1.status_code == 400
    assert res1.get_json()["error"]["code"] == "VALIDATION_ERROR"

    # Missing text field
    res2 = client.post("/api/analyze/text", json={"wrong_field": "hello"})
    assert res2.status_code == 400
    assert res2.get_json()["error"]["code"] == "VALIDATION_ERROR"

    # Non-string text
    res3 = client.post("/api/analyze/text", json={"text": 12345})
    assert res3.status_code == 400
    assert res3.get_json()["error"]["code"] == "VALIDATION_ERROR"

    # Empty text
    res4 = client.post("/api/analyze/text", json={"text": ""})
    assert res4.status_code == 400
    assert res4.get_json()["error"]["code"] == "EMPTY_TEXT"

    # Whitespace only
    res5 = client.post("/api/analyze/text", json={"text": "   \n\t  "})
    assert res5.status_code == 400
    assert res5.get_json()["error"]["code"] == "EMPTY_TEXT"

    # Too long (> 2000 chars)
    long_text = "a" * 2001
    res6 = client.post("/api/analyze/text", json={"text": long_text})
    assert res6.status_code == 413
    assert res6.get_json()["error"]["code"] == "TEXT_TOO_LONG"

