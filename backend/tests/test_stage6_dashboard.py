import json
import pytest
from backend.app.database import execute_db, query_db


def _register_and_login(client, username="dash_user", email="dash@example.com", password="Password123"):
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


def test_dashboard_unauthenticated_rejected(client):
    """Verify GET /api/dashboard without authentication returns 401 UNAUTHENTICATED."""
    res = client.get("/api/dashboard")
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHENTICATED"


def test_dashboard_empty_user(client):
    """Verify an authenticated user with no saved analyses receives zero counts and empty activity."""
    _register_and_login(client, "empty_dash", "empty_dash@example.com")
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    dash = data["data"]
    assert dash["total_saved_count"] == 0
    assert dash["recent_activity"] == []
    assert dash["category_breakdown"] == {
        "Normal": 0,
        "Insult": 0,
        "Threat": 0,
        "Hate Speech": 0,
        "Toxic/Abusive Language": 0
    }
    assert "confidence_disclaimer" in dash


def test_dashboard_populated_metrics(client):
    """Verify accurate total_saved_count, category counts, and consistency."""
    auth = _register_and_login(client, "metrics_user", "metrics@example.com")
    user_id = auth["user"]["id"]

    # Insert 2 Normal, 1 Insult, 1 Threat
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category, confidence) VALUES (?, 'Msg 1', 'Normal', 0.95);", (user_id,))
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category, confidence) VALUES (?, 'Msg 2', 'Normal', 0.92);", (user_id,))
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category, confidence) VALUES (?, 'Msg 3', 'Insult', 0.88);", (user_id,))
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category, confidence) VALUES (?, 'Msg 4', 'Threat', 0.99);", (user_id,))

    res = client.get("/api/dashboard")
    assert res.status_code == 200
    dash = res.get_json()["data"]

    assert dash["total_saved_count"] == 4
    breakdown = dash["category_breakdown"]
    assert breakdown["Normal"] == 2
    assert breakdown["Insult"] == 1
    assert breakdown["Threat"] == 1
    assert breakdown["Hate Speech"] == 0
    assert breakdown["Toxic/Abusive Language"] == 0
    assert sum(breakdown.values()) == dash["total_saved_count"]


def test_dashboard_category_breakdown_zero_filled(client):
    """Verify categories with 0 saved items are explicitly present with value 0."""
    auth = _register_and_login(client, "zero_fill_user", "zero_fill@example.com")
    user_id = auth["user"]["id"]

    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Single normal', 'Normal');", (user_id,))

    res = client.get("/api/dashboard")
    assert res.status_code == 200
    breakdown = res.get_json()["data"]["category_breakdown"]
    expected_categories = ["Normal", "Insult", "Threat", "Hate Speech", "Toxic/Abusive Language"]
    for cat in expected_categories:
        assert cat in breakdown
        if cat == "Normal":
            assert breakdown[cat] == 1
        else:
            assert breakdown[cat] == 0


def test_dashboard_recent_activity_cap_five_and_ordering(client):
    """Verify recent activity is capped at 5 and deterministically ordered by saved_at DESC, id DESC."""
    auth = _register_and_login(client, "cap_user", "cap@example.com")
    user_id = auth["user"]["id"]

    # Insert 8 records with identical timestamp to verify id DESC tie-breaker and 5-item cap
    fixed_ts = "2026-11-07 14:00:00"
    inserted_ids = []
    for i in range(1, 9):
        rec_id = execute_db(
            """
            INSERT INTO saved_analyses (user_id, text_content, category, confidence, saved_at)
            VALUES (?, ?, 'Normal', 0.90, ?);
            """,
            (user_id, f"Message {i}", fixed_ts)
        )
        inserted_ids.append(rec_id)

    res = client.get("/api/dashboard")
    assert res.status_code == 200
    dash = res.get_json()["data"]
    assert dash["total_saved_count"] == 8

    recent = dash["recent_activity"]
    assert len(recent) == 5

    # Order must be the last 5 inserted IDs in descending order
    expected_ids = list(reversed(inserted_ids[-5:]))
    actual_ids = [item["id"] for item in recent]
    assert actual_ids == expected_ids


def test_dashboard_ownership_isolation(client):
    """Verify User A's dashboard does not include User B's saved records in totals, breakdown, or activity."""
    auth_a = _register_and_login(client, "dash_alice", "alice@example.com")
    user_a_id = auth_a["user"]["id"]

    # User A has 1 normal message
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Alice message', 'Normal');", (user_a_id,))

    # User B inserted directly in DB with 5 threats
    user_b_id = execute_db("INSERT INTO users (username, email, password_hash) VALUES ('dash_bob', 'bob@example.com', 'hash');")
    for i in range(5):
        execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Bob threat', 'Threat');", (user_b_id,))

    res = client.get("/api/dashboard")
    assert res.status_code == 200
    dash = res.get_json()["data"]

    assert dash["total_saved_count"] == 1
    assert dash["category_breakdown"]["Normal"] == 1
    assert dash["category_breakdown"]["Threat"] == 0
    assert len(dash["recent_activity"]) == 1
    assert dash["recent_activity"][0]["text_content"] == "Alice message"


def test_dashboard_ignores_user_id_query_parameter(client):
    """Verify unexpected user_id in query parameter cannot change ownership scope."""
    auth_a = _register_and_login(client, "dash_tom", "tom@example.com")
    user_a_id = auth_a["user"]["id"]

    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Tom private', 'Normal');", (user_a_id,))

    user_b_id = execute_db("INSERT INTO users (username, email, password_hash) VALUES ('dash_jerry', 'jerry@example.com', 'hash');")
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Jerry private', 'Threat');", (user_b_id,))

    res = client.get(f"/api/dashboard?user_id={user_b_id}")
    assert res.status_code == 200
    dash = res.get_json()["data"]

    # Must reflect Tom's data exclusively
    assert dash["total_saved_count"] == 1
    assert dash["category_breakdown"]["Normal"] == 1
    assert dash["category_breakdown"]["Threat"] == 0
    assert dash["recent_activity"][0]["text_content"] == "Tom private"


def test_dashboard_toxic_abusive_variant_rollup(client):
    """Verify records saved as 'Toxic/Abusive' or 'Toxic/Abusive Language' roll up into 'Toxic/Abusive Language'."""
    auth = _register_and_login(client, "rollup_user", "rollup@example.com")
    user_id = auth["user"]["id"]

    # Insert 1 shorthand variant and 1 full canonical variant
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Shorthand toxic', 'Toxic/Abusive');", (user_id,))
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Canonical toxic', 'Toxic/Abusive Language');", (user_id,))

    res = client.get("/api/dashboard")
    assert res.status_code == 200
    dash = res.get_json()["data"]

    assert dash["total_saved_count"] == 2
    assert dash["category_breakdown"]["Toxic/Abusive Language"] == 2


def test_dashboard_confidence_disclaimer_present(client):
    """Verify presence and wording of the uncalibrated model score disclaimer."""
    _register_and_login(client, "disclaimer_user", "disclaimer@example.com")
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    dash = res.get_json()["data"]
    assert "confidence_disclaimer" in dash
    assert "uncalibrated decision probabilities" in dash["confidence_disclaimer"]


def test_dashboard_malformed_highlighted_terms_json(client):
    """Verify malformed JSON in highlighted_terms_json falls back to [] without crashing."""
    auth = _register_and_login(client, "corrupt_user", "corrupt@example.com")
    user_id = auth["user"]["id"]

    # Insert analysis with invalid non-JSON string in highlighted_terms_json
    execute_db(
        """
        INSERT INTO saved_analyses (user_id, text_content, category, highlighted_terms_json)
        VALUES (?, 'Text with corrupted json', 'Normal', 'INVALID_NOT_JSON{[');
        """,
        (user_id,)
    )

    res = client.get("/api/dashboard")
    assert res.status_code == 200
    recent = res.get_json()["data"]["recent_activity"]
    assert len(recent) == 1
    assert recent[0]["highlighted_terms"] == []


def test_dashboard_unexpected_query_parameters_cannot_escalate(client):
    """Verify unexpected query parameters like ?role=admin&all=true do not leak data."""
    auth = _register_and_login(client, "tamper_user", "tamper@example.com")
    user_id = auth["user"]["id"]

    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Tamper user note', 'Normal');", (user_id,))

    # Insert other user records
    other_id = execute_db("INSERT INTO users (username, email, password_hash, role) VALUES ('admin_other', 'admin_other@example.com', 'hash', 'admin');")
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Admin secret note', 'Threat');", (other_id,))

    res = client.get("/api/dashboard?role=admin&all=true&scope=global")
    assert res.status_code == 200
    dash = res.get_json()["data"]
    assert dash["total_saved_count"] == 1
    assert dash["recent_activity"][0]["text_content"] == "Tamper user note"


def test_dashboard_no_credential_or_session_data_in_response(client):
    """Verify no passwords, hashes, session tokens, or CSRF tokens exist in response."""
    auth = _register_and_login(client, "sec_user", "sec@example.com")
    user_id = auth["user"]["id"]

    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Note', 'Normal');", (user_id,))

    res = client.get("/api/dashboard")
    assert res.status_code == 200
    raw_text = res.get_data(as_text=True)

    assert "password" not in raw_text.lower()
    assert "csrf_token" not in raw_text.lower()
    assert "password_hash" not in raw_text.lower()
    assert auth["csrf_token"] not in raw_text

