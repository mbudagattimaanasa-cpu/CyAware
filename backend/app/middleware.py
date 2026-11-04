import time
import secrets
import hmac
from functools import wraps
from flask import session, jsonify, g, request, current_app
from backend.app.database import query_db

# In-memory store for rate limiting / login throttling: {key: [timestamp, ...]}
_failed_login_attempts = {}


def check_login_rate_limit(key: str, max_attempts: int = 5, window_seconds: int = 300) -> bool:
    """Check if the given key (e.g. IP or username) has exceeded the max allowed failed attempts.
    Returns True if allowed, False if throttled.
    """
    now = time.time()
    attempts = _failed_login_attempts.get(key, [])
    # Prune attempts outside the window
    attempts = [t for t in attempts if now - t < window_seconds]
    _failed_login_attempts[key] = attempts
    return len(attempts) < max_attempts


def record_failed_login(key: str):
    """Record a failed login attempt for the key."""
    now = time.time()
    if key not in _failed_login_attempts:
        _failed_login_attempts[key] = []
    _failed_login_attempts[key].append(now)


def clear_failed_logins(key: str):
    """Clear failed login attempts upon successful login."""
    _failed_login_attempts.pop(key, None)


def reset_all_rate_limits():
    """Clear all rate-limiting state (useful for test isolation)."""
    _failed_login_attempts.clear()


def generate_csrf_token() -> str:
    """Generate or retrieve a cryptographically secure CSRF token stored in the session."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(32)
        session["csrf_token"] = token
    return token


def validate_csrf():
    """Validate CSRF token for cookie-authenticated state-changing requests."""
    # Check if CSRF enforcement is globally disabled in config
    if not current_app.config.get("CSRF_ENABLED", True):
        return None

    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        # Apply CSRF protection strictly to authenticated sessions
        if session.get("user_id"):
            header_token = (
                request.headers.get("X-CSRF-Token")
                or request.headers.get("X-CSRFToken")
            )
            body_token = None
            if request.is_json:
                data = request.get_json(silent=True)
                if isinstance(data, dict):
                    body_token = data.get("csrf_token")

            token = header_token or body_token
            expected_token = session.get("csrf_token")

            if not expected_token or not token or not hmac.compare_digest(str(expected_token), str(token)):
                return jsonify({
                    "success": False,
                    "error": {
                        "code": "CSRF_ERROR",
                        "message": "CSRF token missing or invalid."
                    }
                }), 403

    return None


def login_required(f):
    """Decorator to require an active authenticated user session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({
                "success": False,
                "error": {
                    "code": "UNAUTHENTICATED",
                    "message": "Authentication required. Please log in."
                }
            }), 401

        # Verify user exists and is active in database
        user = query_db(
            "SELECT id, username, email, role, is_active FROM users WHERE id = ?",
            (user_id,),
            one=True
        )
        if not user or user["is_active"] != 1:
            session.clear()
            return jsonify({
                "success": False,
                "error": {
                    "code": "UNAUTHENTICATED",
                    "message": "User account is invalid or deactivated."
                }
            }), 401

        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require an authenticated admin session."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if g.current_user["role"] != "admin":
            return jsonify({
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Administrator privileges required."
                }
            }), 403
        return f(*args, **kwargs)
    return decorated_function
