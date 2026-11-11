import json
import sqlite3
from typing import Optional, Tuple, Dict, Any
from backend.app.database import get_db, query_db


def delete_user_account(user_id: int, is_self_service: bool = True) -> Tuple[bool, Optional[str], int]:
    """
    Safely and permanently delete a user account and associated personal records inside an atomic SQLite transaction.

    Safeguards:
      - Validates that no unexpected transaction is open on the connection (TRANSACTION_STATE_CONFLICT).
      - Acquires an exclusive write lock using SQLite BEGIN IMMEDIATE.
      - Fetches target user role and is_active status inside the transaction.
      - Rejects non-existent users (USER_NOT_FOUND, 404).
      - Rejects inactive accounts (ACCOUNT_INACTIVE, 400).
      - Prohibits Admin self-service deletion (ADMIN_ACCOUNT_DELETION_NOT_ALLOWED, 403).
      - Protects against deleting the last active Administrator in any deletion path (LAST_ADMIN_PROTECTED, 403).
      - Explicitly prunes user feedback records.
      - Cascades user deletion to saved_analyses via SQLite foreign keys.
      - Records an anonymized ACCOUNT_DELETED audit log (user_id=NULL, ip_address=NULL, zero PII).
      - Rolls back only transactions owned by this function upon failure or rejection.

    Returns:
      (success: bool, error_code: Optional[str], status_code: int)
    """
    db = get_db()

    # Pre-condition: fail safely if an unexpected transaction is already open
    if getattr(db, "in_transaction", False):
        return False, "TRANSACTION_STATE_CONFLICT", 500

    tx_acquired = False
    try:
        db.execute("BEGIN IMMEDIATE;")
        tx_acquired = True
    except sqlite3.Error:
        return False, "DATABASE_LOCKED", 500

    try:
        # In-transaction user lookup to guarantee fresh role and status
        user = db.execute(
            "SELECT id, username, email, role, is_active FROM users WHERE id = ?;",
            (user_id,)
        ).fetchone()

        if not user:
            db.rollback()
            return False, "USER_NOT_FOUND", 404

        # Reject already-deactivated accounts
        if user["is_active"] != 1:
            db.rollback()
            return False, "ACCOUNT_INACTIVE", 400

        # Disallow Admin self-service deletion
        if is_self_service and user["role"] == "admin":
            db.rollback()
            return False, "ADMIN_ACCOUNT_DELETION_NOT_ALLOWED", 403

        # Preserve the last active Admin safeguard for all deletion paths
        if user["role"] == "admin":
            admin_count_row = db.execute(
                "SELECT COUNT(*) AS active_admins FROM users WHERE role = 'admin' AND is_active = 1;"
            ).fetchone()
            active_admins = admin_count_row["active_admins"] if admin_count_row else 0
            if active_admins <= 1:
                db.rollback()
                return False, "LAST_ADMIN_PROTECTED", 403

        # Explicitly delete user feedback records
        db.execute("DELETE FROM feedback WHERE user_id = ?;", (user_id,))

        # Record anonymized audit log (zero user retention, zero IP retention)
        db.execute(
            """
            INSERT INTO audit_logs (user_id, action, ip_address, details)
            VALUES (NULL, 'ACCOUNT_DELETED', NULL, 'User account closed');
            """
        )

        # Permanently delete user record (foreign key ON DELETE CASCADE prunes saved_analyses)
        db.execute("DELETE FROM users WHERE id = ?;", (user_id,))

        # Commit atomic transaction
        db.commit()
        return True, None, 200

    except Exception:
        if tx_acquired:
            try:
                db.rollback()
            except Exception:
                pass
        raise


def get_user_export_data(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Export all personal data belonging strictly to the requested user.

    Excludes:
      - Password hashes
      - Session tokens and CSRF tokens
      - Audit logs and system administration records

    Returns:
      Dictionary containing user profile, saved analyses, and submitted feedback,
      or None if user is not found.
    """
    user = query_db(
        "SELECT id, username, email, role, created_at, updated_at FROM users WHERE id = ?;",
        (user_id,),
        one=True
    )
    if not user:
        return None

    profile = {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "created_at": user["created_at"],
        "updated_at": user["updated_at"]
    }

    # Fetch all saved analyses for this user with deterministic tie-breaking
    analyses_rows = query_db(
        """
        SELECT id, text_content, category, confidence, severity, explanation,
               highlighted_terms_json, safer_rewrite, saved_at
        FROM saved_analyses
        WHERE user_id = ?
        ORDER BY saved_at DESC, id DESC;
        """,
        (user_id,)
    )

    saved_analyses = []
    for row in analyses_rows:
        highlighted_terms = []
        if row["highlighted_terms_json"]:
            try:
                highlighted_terms = json.loads(row["highlighted_terms_json"])
            except (ValueError, TypeError):
                highlighted_terms = []

        saved_analyses.append({
            "id": row["id"],
            "text_content": row["text_content"],
            "category": row["category"],
            "confidence": row["confidence"],
            "severity": row["severity"],
            "explanation": row["explanation"],
            "highlighted_terms": highlighted_terms,
            "safer_rewrite": row["safer_rewrite"],
            "saved_at": row["saved_at"]
        })

    # Fetch all feedback submitted by this user with deterministic tie-breaking
    feedback_rows = query_db(
        """
        SELECT id, analysis_id, feedback_type, suggested_category, rating, comment, status, created_at
        FROM feedback
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC;
        """,
        (user_id,)
    )

    feedback_list = [
        {
            "id": fb["id"],
            "analysis_id": fb["analysis_id"],
            "feedback_type": fb["feedback_type"],
            "suggested_category": fb["suggested_category"],
            "rating": fb["rating"],
            "comment": fb["comment"],
            "status": fb["status"],
            "created_at": fb["created_at"]
        }
        for fb in feedback_rows
    ]

    return {
        "user": profile,
        "saved_analyses": saved_analyses,
        "feedback": feedback_list
    }

