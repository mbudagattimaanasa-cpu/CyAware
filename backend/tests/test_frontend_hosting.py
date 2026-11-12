import pytest
from backend.app import create_app


@pytest.fixture
def client():
    app = create_app("testing")
    with app.test_client() as client:
        yield client


def test_serve_index_html(client):
    """Verify GET / serves frontend/index.html with 200 OK and HTML MIME type."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.content_type
    assert b"CyAware" in response.data
    assert b"<!DOCTYPE html>" in response.data


def test_serve_html_pages(client):
    """Verify existing HTML pages load via exact file name and extensionless route."""
    # Exact file names
    for page in ["login.html", "register.html", "analyze-text.html", "dashboard.html", "history.html"]:
        res = client.get(f"/{page}")
        assert res.status_code == 200
        assert "text/html" in res.content_type

    # Extensionless routes
    res_login = client.get("/login")
    assert res_login.status_code == 200
    assert "text/html" in res_login.content_type

    res_reg = client.get("/register")
    assert res_reg.status_code == 200
    assert "text/html" in res_reg.content_type


def test_serve_css_and_js_and_svg_assets(client):
    """Verify static CSS, JS, and SVG assets load with appropriate MIME types."""
    # CSS
    res_css = client.get("/css/main.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.content_type

    # JS
    res_config = client.get("/js/config.js")
    assert res_config.status_code == 200
    assert ("javascript" in res_config.content_type or "text/plain" in res_config.content_type)
    assert b"CyAwareConfig" in res_config.data

    res_api = client.get("/js/api.js")
    assert res_api.status_code == 200
    assert ("javascript" in res_api.content_type or "text/plain" in res_api.content_type)
    assert b"CyAwareAPI" in res_api.data

    # SVG
    res_svg = client.get("/assets/icons/cyaware-logo.svg")
    assert res_svg.status_code == 200
    assert "image/svg+xml" in res_svg.content_type


def test_unknown_api_route_does_not_return_frontend_html(client):
    """Verify unknown /api/... routes return JSON 404, NOT frontend HTML."""
    response = client.get("/api/unknown_nonexistent_endpoint")
    assert response.status_code == 404
    assert response.is_json
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"


def test_path_traversal_rejected(client):
    """Verify path traversal attempts are safely rejected with 404 and do not leak server files."""
    traversal_paths = [
        "/../requirements.txt",
        "/../../backend/app/config.py",
        "/....//....//etc/passwd",
        "/..%2F..%2Fbackend"
    ]
    for path in traversal_paths:
        res = client.get(path)
        assert res.status_code == 404
        assert b"SECRET_KEY" not in res.data


def test_security_headers_preserved_on_frontend_routes(client):
    """Verify global security headers and CSP are attached to frontend responses."""
    response = client.get("/")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Content-Security-Policy") == "default-src 'self'"


def test_api_routes_still_operational(client):
    """Verify existing API routes still function normally alongside frontend hosting."""
    # Health check
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.is_json
    assert res_health.get_json()["data"]["status"] == "healthy"

    # CSRF Token
    res_csrf = client.get("/api/auth/csrf-token")
    assert res_csrf.status_code == 200
    assert res_csrf.is_json
    assert "csrf_token" in res_csrf.get_json()["data"]

    # Public Text Analysis
    res_analyze = client.post("/api/analyze/text", json={"text": "Hello world this is a test", "save": False})
    assert res_analyze.status_code == 200
    assert res_analyze.is_json
    assert res_analyze.get_json()["data"]["category"] == "Normal"

