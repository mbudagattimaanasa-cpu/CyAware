import json
from math import ceil
from flask import Blueprint, request, jsonify, session
from backend.app.database import get_db, query_db
from backend.app.middleware import login_required

analyses_bp = Blueprint("analyses", __name__, url_prefix="/api/analyses")

VALID_CATEGORIES = {
    "Normal",
    "Insult",
    "Threat",
    "Hate Speech",
    "Toxic/Abusive",
    "Toxic/Abusive Language"
}


@analyses_bp.route("", methods=["GET"], strict_slashes=False)
@login_required
def get_analyses():
    """
    Retrieve paginated saved analyses for the authenticated user with optional category filtering.
    Enforces deterministic sorting (saved_at DESC, id DESC) and strict ownership isolation.
    """
    user_id = session.get("user_id")

    # Validate page parameter
    raw_page = request.args.get("page", 1)
    try:
        page = int(raw_page)
        if page < 1:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": {
                "code": "INVALID_PAGINATION_PARAMETERS",
                "message": "Page must be a positive integer."
            }
        }), 400

    # Validate limit parameter (1 to 50)
    raw_limit = request.args.get("limit", 10)
    try:
        limit = int(raw_limit)
        if limit < 1 or limit > 50:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": {
                "code": "INVALID_PAGINATION_PARAMETERS",
                "message": "Limit must be an integer between 1 and 50."
            }
        }), 400

    # Validate category filter
    category_filter = request.args.get("category")
    if category_filter:
        category_filter = category_filter.strip()
        if category_filter not in VALID_CATEGORIES:
            return jsonify({
                "success": False,
                "error": {
                    "code": "INVALID_CATEGORY_FILTER",
                    "message": "Invalid category filter."
                }
            }), 400

    # Parameterized query filtering
    if category_filter in ("Toxic/Abusive", "Toxic/Abusive Language"):
        where_clause = "user_id = ? AND category IN ('Toxic/Abusive', 'Toxic/Abusive Language')"
        filter_args = [user_id]
    elif category_filter:
        where_clause = "user_id = ? AND category = ?"
        filter_args = [user_id, category_filter]
    else:
        where_clause = "user_id = ?"
        filter_args = [user_id]

    # Calculate total matching count
    count_sql = f"SELECT COUNT(*) AS total FROM saved_analyses WHERE {where_clause};"
    count_res = query_db(count_sql, tuple(filter_args), one=True)
    total = count_res["total"] if count_res else 0
    total_pages = ceil(total / limit) if total > 0 else 0

    # Fetch paginated items with deterministic ordering
    offset = (page - 1) * limit
    data_sql = f"""
        SELECT id, text_content, category, confidence, severity, explanation,
               highlighted_terms_json, safer_rewrite, saved_at
        FROM saved_analyses
        WHERE {where_clause}
        ORDER BY saved_at DESC, id DESC
        LIMIT ? OFFSET ?;
    """
    rows = query_db(data_sql, tuple(filter_args + [limit, offset]))

    items = []
    for row in rows:
        highlighted_terms = []
        if row["highlighted_terms_json"]:
            try:
                highlighted_terms = json.loads(row["highlighted_terms_json"])
            except (ValueError, TypeError):
                highlighted_terms = []

        items.append({
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

    return jsonify({
        "success": True,
        "data": {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages
            }
        }
    }), 200


@analyses_bp.route("/<int:analysis_id>", methods=["DELETE"], strict_slashes=False)
@login_required
def delete_analysis(analysis_id: int):
    """
    Delete an individual saved analysis record owned by the authenticated user.
    Enforces CSRF and returns HTTP 404 for missing or foreign records.
    """
    user_id = session.get("user_id")
    db = get_db()
    cur = db.execute(
        "DELETE FROM saved_analyses WHERE id = ? AND user_id = ?;",
        (analysis_id, user_id)
    )
    rowcount = cur.rowcount
    db.commit()

    if rowcount == 0:
        return jsonify({
            "success": False,
            "error": {
                "code": "ANALYSIS_NOT_FOUND",
                "message": "Analysis record not found."
            }
        }), 404

    return jsonify({
        "success": True,
        "message": "Saved analysis deleted successfully."
    }), 200

