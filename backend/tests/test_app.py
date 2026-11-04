def test_health_check(client):
    """Verify health endpoint returns 200, healthy status, and connected DB."""
    response = client.get("/api/health")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert json_data["data"]["status"] == "healthy"
    assert json_data["data"]["database"] == "connected"


def test_security_headers(client):
    """Verify standard security headers are attached to responses."""
    response = client.get("/api/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"


def test_404_json_envelope(client):
    """Verify 404 responses conform to standard JSON error envelope."""
    response = client.get("/api/non-existent-route")
    assert response.status_code == 404
    json_data = response.get_json()
    assert json_data["success"] is False
    assert json_data["error"]["code"] == "NOT_FOUND"


def test_405_json_envelope(client):
    """Verify 405 Method Not Allowed conforms to standard JSON error envelope."""
    response = client.post("/api/health")
    assert response.status_code == 405
    json_data = response.get_json()
    assert json_data["success"] is False
    assert json_data["error"]["code"] == "METHOD_NOT_ALLOWED"

