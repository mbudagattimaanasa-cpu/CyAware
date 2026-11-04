import re
from flask import Blueprint, request, jsonify, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from backend.app.database import query_db, execute_db
from backend.app.middleware import (
    login_required,
    check_login_rate_limit,
    record_failed_login,
    clear_failed_logins,
    generate_csrf_token,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,30}$")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_registration_input(username, email, password):
    """Validate registration fields against security rules."""
    if not username or not isinstance(username, str) or not USERNAME_REGEX.match(username.strip()):
        return "Username must be 3-30 characters long and contain only letters, numbers, and underscores."

    if not email or not isinstance(email, str) or len(email.strip()) > 120 or not EMAIL_REGEX.match(email.strip()):
        return "A valid email address is required (maximum 120 characters)."

    if not password or not isinstance(password, str) or len(password) < 8:
        return "Password must be at least 8 characters long."

    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        return "Password must contain at least one letter and one number."

    return None


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new standard user account. Role is strictly 'user'."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request payload must be valid JSON."
            }
        }), 400

    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    validation_error = validate_registration_input(username, email, password)
    if validation_error:
        return jsonify({
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": validation_error
            }
        }), 400

    # Check if username or email already exists
    existing = query_db(
        "SELECT id, username, email FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
        (username, email),
        one=True
    )
    if existing:
        return jsonify({
            "success": False,
            "error": {
                "code": "USER_EXISTS",
                "message": "Username or email is already registered."
            }
        }), 409

    # Hash password securely
    password_hash = generate_password_hash(password)

    # Insert user (role is ALWAYS 'user', never allow self-assignment of 'admin')
    user_id = execute_db(
        """INSERT INTO users (username, email, password_hash, role, is_active)
           VALUES (?, ?, ?, 'user', 1);""",
        (username, email, password_hash)
    )

    # Record security audit log (NO passwords)
    execute_db(
        """INSERT INTO audit_logs (user_id, action, ip_address, details)
           VALUES (?, 'USER_REGISTERED', ?, ?);""",
        (user_id, request.remote_addr or "127.0.0.1", f"Username: {username}")
    )

    created_user = query_db(
        "SELECT id, username, email, role, created_at FROM users WHERE id = ?",
        (user_id,),
        one=True
    )

    return jsonify({
        "success": True,
        "data": {
            "user": {
                "id": created_user["id"],
                "username": created_user["username"],
                "email": created_user["email"],
                "role": created_user["role"],
                "created_at": created_user["created_at"]
            }
        },
        "message": "Account created successfully."
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate user and establish a server-managed session with throttling."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request payload must be valid JSON."
            }
        }), 400

    identifier = str(data.get("username_or_email", "")).strip()
    password = str(data.get("password", ""))
    client_ip = request.remote_addr or "127.0.0.1"

    if not identifier or not password:
        return jsonify({
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Username/email and password are required."
            }
        }), 400

    # Rate limiting / brute-force protection
    rate_limit_key = f"{client_ip}:{identifier.lower()}"
    if not check_login_rate_limit(rate_limit_key, max_attempts=5, window_seconds=300):
        execute_db(
            """INSERT INTO audit_logs (user_id, action, ip_address, details)
               VALUES (NULL, 'LOGIN_THROTTLED', ?, ?);""",
            (client_ip, f"Throttled identifier: {identifier}")
        )
        return jsonify({
            "success": False,
            "error": {
                "code": "RATE_LIMITED",
                "message": "Too many failed attempts. Try again in 5 minutes."
            }
        }), 429

    # Look up user by username or email
    user = query_db(
        """SELECT id, username, email, password_hash, role, is_active
           FROM users
           WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)""",
        (identifier, identifier),
        one=True
    )

    if not user or not check_password_hash(user["password_hash"], password):
        record_failed_login(rate_limit_key)
        execute_db(
            """INSERT INTO audit_logs (user_id, action, ip_address, details)
               VALUES (?, 'LOGIN_FAILED', ?, ?);""",
            (user["id"] if user else None, client_ip, f"Failed attempt for {identifier}")
        )
        return jsonify({
            "success": False,
            "error": {
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid username or password."
            }
        }), 401

    if user["is_active"] != 1:
        return jsonify({
            "success": False,
            "error": {
                "code": "ACCOUNT_DISABLED",
                "message": "Account has been deactivated. Please contact an administrator."
            }
        }), 401

    # Reset rate limit tracker upon success
    clear_failed_logins(rate_limit_key)

    # Establish session
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    csrf_token = generate_csrf_token()
    session.permanent = True

    # Audit log
    execute_db(
        """INSERT INTO audit_logs (user_id, action, ip_address, details)
           VALUES (?, 'LOGIN_SUCCESS', ?, ?);""",
        (user["id"], client_ip, f"User {user['username']} logged in")
    )

    return jsonify({
        "success": True,
        "data": {
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"]
            },
            "csrf_token": csrf_token
        },
        "message": "Logged in successfully."
    }), 200


@auth_bp.route("/csrf-token", methods=["GET"])
def get_csrf_token():
    """Return the CSRF token for the current session."""
    token = generate_csrf_token()
    return jsonify({
        "success": True,
        "data": {
            "csrf_token": token
        }
    }), 200


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """Securely terminate the active user session."""
    user_id = session.get("user_id")
    client_ip = request.remote_addr or "127.0.0.1"

    execute_db(
        """INSERT INTO audit_logs (user_id, action, ip_address, details)
           VALUES (?, 'LOGOUT', ?, 'User logged out');""",
        (user_id, client_ip)
    )

    session.clear()
    return jsonify({
        "success": True,
        "message": "Logged out successfully."
    }), 200


@auth_bp.route("/me", methods=["GET"])
@login_required
def get_current_user():
    """Return the profile details of the authenticated user."""
    user = g.current_user
    return jsonify({
        "success": True,
        "data": {
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"]
            }
        }
    }), 200

