from flask import Blueprint, jsonify, session
from backend.app.middleware import login_required
from backend.app.services.user_service import get_user_export_data, delete_user_account

user_bp = Blueprint("user", __name__, url_prefix="/api/user")

DELETION_ERROR_MESSAGES = {
    "ADMIN_ACCOUNT_DELETION_NOT_ALLOWED": "Administrator accounts cannot be deleted through self-service.",
    "ACCOUNT_INACTIVE": "User account is deactivated.",
    "USER_NOT_FOUND": "User account not found.",
    "TRANSACTION_STATE_CONFLICT": "A conflicting database transaction is already in progress.",
    "DATABASE_LOCKED": "Database is currently busy. Please try again."
}


@user_bp.after_request
def add_user_cache_headers(response):
    """Ensure all responses from the user blueprint prohibit intermediate and client-side caching."""
    response.headers["Cache-Control"] = "no-store"
    return response


@user_bp.route("/export", methods=["GET"], strict_slashes=False)
@login_required
def export_user_data():
    """
    Export all personal data belonging strictly to the authenticated user:
      - User profile (excluding password_hash)
      - Saved analyses (deterministically ordered by saved_at DESC, id DESC)
      - Submitted feedback (deterministically ordered by created_at DESC, id DESC)
    """
    user_id = session.get("user_id")
    export_data = get_user_export_data(user_id)
    if not export_data:
        return jsonify({
            "success": False,
            "error": {
                "code": "USER_NOT_FOUND",
                "message": "User account not found."
            }
        }), 404

    return jsonify({
        "success": True,
        "data": export_data
    }), 200


@user_bp.route("/account", methods=["DELETE"], strict_slashes=False)
@login_required
def delete_account():
    """
    Permanently delete the authenticated user's account and personal data.
    Enforces CSRF, delegates to the atomic transaction service, and clears
    the server-side session strictly upon successful commit.
    """
    user_id = session.get("user_id")

    try:
        success, err_code, status_code = delete_user_account(user_id, is_self_service=True)
    except Exception:
        return jsonify({
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An error occurred while deleting the account."
            }
        }), 500

    if not success:
        # Session is intentionally PRESERVED if deletion fails or is rejected
        return jsonify({
            "success": False,
            "error": {
                "code": err_code,
                "message": DELETION_ERROR_MESSAGES.get(err_code, "Failed to delete account.")
            }
        }), status_code

    # Invalidate session state strictly after database commit succeeds
    session.clear()

    return jsonify({
        "success": True,
        "message": "User account and associated data permanently deleted."
    }), 200

