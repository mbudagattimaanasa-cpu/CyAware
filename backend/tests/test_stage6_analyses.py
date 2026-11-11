import json
import pytest
from backend.app.database import execute_db, query_db


def _register_and_login(client, username="user_one", email="user1@example.com", password="Password123"):
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


def test_get_analyses_unauthenticated_rejected(client):
    """Verify unauthenticated requests to GET /api/analyses return 401 UNAUTHENTICATED."""
    res = client.get("/api/analyses")
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHENTICATED"


def test_get_analyses_empty_history(client):
    """Verify authenticated user with no saved analyses receives empty items list and 0 totals."""
    _register_and_login(client, "empty_user", "empty@example.com")
    res = client.get("/api/analyses")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["items"] == []
    assert data["data"]["pagination"] == {
        "page": 1,
        "limit": 10,
        "total": 0,
        "total_pages": 0
    }


def test_get_analyses_success_and_stable_ordering(client):
    """Verify saved analyses are returned with full details and deterministically ordered by saved_at DESC, id DESC."""
    auth = _register_and_login(client, "order_user", "order@example.com")
    user_id = auth["user"]["id"]

    # Insert 3 records with identical saved_at timestamp to test deterministic tie-breaking by id DESC
    fixed_ts = "2026-11-07 10:00:00"
    id1 = execute_db(
        """
        INSERT INTO saved_analyses (user_id, text_content, category, confidence, explanation, highlighted_terms_json, saved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (user_id, "First record", "Normal", 0.91, "Explanation 1", json.dumps(["first"]), fixed_ts)
    )
    id2 = execute_db(
        """
        INSERT INTO saved_analyses (user_id, text_content, category, confidence, explanation, highlighted_terms_json, saved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (user_id, "Second record", "Insult", 0.85, "Explanation 2", json.dumps(["second"]), fixed_ts)
    )
    id3 = execute_db(
        """
        INSERT INTO saved_analyses (user_id, text_content, category, confidence, explanation, highlighted_terms_json, saved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (user_id, "Third record", "Threat", 0.88, "Explanation 3", json.dumps(["third"]), fixed_ts)
    )

    res = client.get("/api/analyses")
    assert res.status_code == 200
    items = res.get_json()["data"]["items"]
    assert len(items) == 3
    # Order must be id3, id2, id1 (id DESC tie-breaker)
    assert items[0]["id"] == id3
    assert items[0]["text_content"] == "Third record"
    assert items[0]["highlighted_terms"] == ["third"]
    assert items[0]["severity"] is None

    assert items[1]["id"] == id2
    assert items[2]["id"] == id1


def test_get_analyses_pagination(client):
    """Verify pagination limits, offsets, and total_pages calculations."""
    auth = _register_and_login(client, "page_user", "page@example.com")
    user_id = auth["user"]["id"]

    for i in range(1, 6):
        execute_db(
            """
            INSERT INTO saved_analyses (user_id, text_content, category, confidence)
            VALUES (?, ?, ?, ?);
            """,
            (user_id, f"Message {i}", "Normal", 0.90)
        )

    # Page 1 with limit 2
    res1 = client.get("/api/analyses?page=1&limit=2")
    assert res1.status_code == 200
    d1 = res1.get_json()["data"]
    assert len(d1["items"]) == 2
    assert d1["pagination"]["page"] == 1
    assert d1["pagination"]["limit"] == 2
    assert d1["pagination"]["total"] == 5
    assert d1["pagination"]["total_pages"] == 3

    # Page 2 with limit 2
    res2 = client.get("/api/analyses?page=2&limit=2")
    assert res2.status_code == 200
    d2 = res2.get_json()["data"]
    assert len(d2["items"]) == 2
    assert d2["pagination"]["page"] == 2

    # Page 3 with limit 2 (last remaining item)
    res3 = client.get("/api/analyses?page=3&limit=2")
    assert res3.status_code == 200
    d3 = res3.get_json()["data"]
    assert len(d3["items"]) == 1
    assert d3["pagination"]["page"] == 3

    # Ensure items across pages are distinct
    all_ids = [d1["items"][0]["id"], d1["items"][1]["id"], d2["items"][0]["id"], d2["items"][1]["id"], d3["items"][0]["id"]]
    assert len(set(all_ids)) == 5


def test_get_analyses_category_filter_and_variants(client):
    """Verify category filtering works and supports both Toxic/Abusive variants."""
    auth = _register_and_login(client, "cat_user", "cat@example.com")
    user_id = auth["user"]["id"]

    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Normal text', 'Normal');", (user_id,))
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Insulting text', 'Insult');", (user_id,))
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Toxic text', 'Toxic/Abusive Language');", (user_id,))

    # Filter by Normal
    res_norm = client.get("/api/analyses?category=Normal")
    assert res_norm.status_code == 200
    d_norm = res_norm.get_json()["data"]
    assert len(d_norm["items"]) == 1
    assert d_norm["items"][0]["category"] == "Normal"
    assert d_norm["pagination"]["total"] == 1

    # Filter by Toxic/Abusive (shorthand variant)
    res_toxic1 = client.get("/api/analyses?category=Toxic/Abusive")
    assert res_toxic1.status_code == 200
    d_toxic1 = res_toxic1.get_json()["data"]
    assert len(d_toxic1["items"]) == 1
    assert d_toxic1["items"][0]["text_content"] == "Toxic text"
    assert d_toxic1["pagination"]["total"] == 1

    # Filter by Toxic/Abusive Language (full canonical variant)
    res_toxic2 = client.get("/api/analyses?category=Toxic/Abusive Language")
    assert res_toxic2.status_code == 200
    d_toxic2 = res_toxic2.get_json()["data"]
    assert len(d_toxic2["items"]) == 1
    assert d_toxic2["items"][0]["text_content"] == "Toxic text"
    assert d_toxic2["pagination"]["total"] == 1


def test_get_analyses_invalid_pagination_parameters(client):
    """Verify invalid page or limit parameters return 400 INVALID_PAGINATION_PARAMETERS."""
    _register_and_login(client, "invalid_page_user", "invalid_page@example.com")

    for bad_page in ["0", "-1", "abc"]:
        res = client.get(f"/api/analyses?page={bad_page}")
        assert res.status_code == 400
        assert res.get_json()["error"]["code"] == "INVALID_PAGINATION_PARAMETERS"

    for bad_limit in ["0", "51", "xyz"]:
        res = client.get(f"/api/analyses?limit={bad_limit}")
        assert res.status_code == 400
        assert res.get_json()["error"]["code"] == "INVALID_PAGINATION_PARAMETERS"


def test_get_analyses_invalid_category_filter(client):
    """Verify unknown category filter returns 400 INVALID_CATEGORY_FILTER."""
    _register_and_login(client, "invalid_cat_user", "invalid_cat@example.com")
    res = client.get("/api/analyses?category=NonExistentCategory")
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_CATEGORY_FILTER"


def test_get_analyses_ownership_isolation(client):
    """Verify User A cannot see User B's saved analyses."""
    auth_a = _register_and_login(client, "user_alpha", "alpha@example.com")
    user_a_id = auth_a["user"]["id"]

    # Insert record for User A
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Alpha private note', 'Normal');", (user_a_id,))

    # Insert User B and a record for User B directly in database
    user_b_id = execute_db("INSERT INTO users (username, email, password_hash) VALUES ('user_beta', 'beta@example.com', 'hash');")
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Beta private note', 'Normal');", (user_b_id,))

    # User A queries analyses: must see only Alpha's note
    res = client.get("/api/analyses")
    assert res.status_code == 200
    items = res.get_json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["text_content"] == "Alpha private note"


def test_get_analyses_ignores_user_id_query_parameter(client):
    """Verify User A calling GET /api/analyses?user_id=<User B ID> still receives exclusively User A's analyses."""
    auth_a = _register_and_login(client, "user_tom", "tom@example.com")
    user_a_id = auth_a["user"]["id"]

    # Insert User A record
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Tom private', 'Normal');", (user_a_id,))

    # Insert User B and record
    user_b_id = execute_db("INSERT INTO users (username, email, password_hash) VALUES ('user_jerry', 'jerry@example.com', 'hash');")
    execute_db("INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Jerry private', 'Normal');", (user_b_id,))

    # User A tries to pass user_id=<User B ID>
    res = client.get(f"/api/analyses?user_id={user_b_id}")
    assert res.status_code == 200
    items = res.get_json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["text_content"] == "Tom private"


def test_delete_analysis_unauthenticated_rejected(client):
    """Verify DELETE /api/analyses/<id> without authentication returns 401 UNAUTHENTICATED."""
    res = client.delete("/api/analyses/1")
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "UNAUTHENTICATED"


def test_delete_analysis_csrf_missing_rejected(client):
    """Verify authenticated DELETE /api/analyses/<id> without X-CSRF-Token returns 403 CSRF_ERROR."""
    _register_and_login(client, "csrf_user", "csrf@example.com")
    res = client.delete("/api/analyses/1")
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "CSRF_ERROR"


def test_delete_analysis_csrf_invalid_rejected(client):
    """Verify authenticated DELETE /api/analyses/<id> with invalid X-CSRF-Token returns 403 CSRF_ERROR."""
    _register_and_login(client, "csrf_bad_user", "csrf_bad@example.com")
    res = client.delete("/api/analyses/1", headers={"X-CSRF-Token": "invalid_csrf_token_value"})
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "CSRF_ERROR"


def test_delete_analysis_success(client):
    """Verify authenticated user can delete their own saved analysis using a valid CSRF token."""
    auth = _register_and_login(client, "del_user", "del@example.com")
    user_id = auth["user"]["id"]
    csrf_token = auth["csrf_token"]

    analysis_id = execute_db(
        "INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'To be deleted', 'Normal');",
        (user_id,)
    )

    res = client.delete(f"/api/analyses/{analysis_id}", headers={"X-CSRF-Token": csrf_token})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "deleted successfully" in data["message"]

    # Verify deleted from DB
    row = query_db("SELECT * FROM saved_analyses WHERE id = ?;", (analysis_id,), one=True)
    assert row is None


def test_delete_analysis_not_found(client):
    """Verify deleting a non-existent analysis ID returns 404 ANALYSIS_NOT_FOUND."""
    auth = _register_and_login(client, "not_found_user", "nf@example.com")
    csrf_token = auth["csrf_token"]

    res = client.delete("/api/analyses/99999", headers={"X-CSRF-Token": csrf_token})
    assert res.status_code == 404
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "ANALYSIS_NOT_FOUND"


def test_delete_analysis_ownership_isolation(client):
    """Verify User A attempting to delete User B's saved analysis returns 404 and leaves record intact."""
    auth_a = _register_and_login(client, "attacker_a", "attacker@example.com")
    csrf_a = auth_a["csrf_token"]

    # User B has an analysis
    user_b_id = execute_db("INSERT INTO users (username, email, password_hash) VALUES ('victim_b', 'victim@example.com', 'hash');")
    analysis_b_id = execute_db(
        "INSERT INTO saved_analyses (user_id, text_content, category) VALUES (?, 'Victim sensitive analysis', 'Normal');",
        (user_b_id,)
    )

    # User A tries to delete User B's analysis
    res = client.delete(f"/api/analyses/{analysis_b_id}", headers={"X-CSRF-Token": csrf_a})
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "ANALYSIS_NOT_FOUND"

    # Verify User B's record is completely untouched in the database
    row = query_db("SELECT * FROM saved_analyses WHERE id = ?;", (analysis_b_id,), one=True)
    assert row is not None
    assert row["text_content"] == "Victim sensitive analysis"


