import json
from flask import Blueprint, jsonify, session
from backend.app.database import query_db
from backend.app.middleware import login_required

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")

CONFIDENCE_DISCLAIMER = (
    "Confidence scores represent uncalibrated decision probabilities "
    "output by the model and should not be interpreted as absolute guarantees."
)

CANONICAL_CATEGORIES = [
    "Normal",
    "Insult",
    "Threat",
    "Hate Speech",
    "Toxic/Abusive Language",
]


@dashboard_bp.route("", methods=["GET"], strict_slashes=False)
@login_required
def get_dashboard():
    """
    Retrieve personal dashboard metrics for the authenticated user:
      - total_saved_count (user-scoped COUNT(*))
      - zero-filled category_breakdown (rolling up 'Toxic/Abusive' into 'Toxic/Abusive Language')
      - recent_activity (up to 5 most recent analyses, ordered by saved_at DESC, id DESC)
      - uncalibrated model confidence disclaimer
    """
    user_id = session.get("user_id")

    # 1. Total saved analyses count query
    count_row = query_db(
        "SELECT COUNT(*) AS total FROM saved_analyses WHERE user_id = ?;",
        (user_id,),
        one=True
    )
    total_saved_count = count_row["total"] if count_row else 0

    # 2. Category breakdown query with zero-filling and rollup
    category_counts = query_db(
        """
        SELECT category, COUNT(*) AS count
        FROM saved_analyses
        WHERE user_id = ?
        GROUP BY category;
        """,
        (user_id,)
    )

    breakdown = {cat: 0 for cat in CANONICAL_CATEGORIES}
    for row in category_counts:
        cat = row["category"]
        count = row["count"]
        # Roll up shorthand variant into canonical category
        if cat in ("Toxic/Abusive", "Toxic/Abusive Language"):
            breakdown["Toxic/Abusive Language"] += count
        elif cat in breakdown:
            breakdown[cat] += count

    # 3. Recent activity preview query (capped at 5, deterministic tie-breaking)
    recent_rows = query_db(
        """
        SELECT id, text_content, category, confidence, severity, explanation,
               highlighted_terms_json, safer_rewrite, saved_at
        FROM saved_analyses
        WHERE user_id = ?
        ORDER BY saved_at DESC, id DESC
        LIMIT 5;
        """,
        (user_id,)
    )

    recent_activity = []
    for row in recent_rows:
        highlighted_terms = []
        if row["highlighted_terms_json"]:
            try:
                parsed = json.loads(row["highlighted_terms_json"])
                if isinstance(parsed, list):
                    highlighted_terms = parsed
                else:
                    highlighted_terms = []
            except (ValueError, TypeError):
                highlighted_terms = []

        recent_activity.append({
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
            "total_saved_count": total_saved_count,
            "category_breakdown": breakdown,
            "recent_activity": recent_activity,
            "confidence_disclaimer": CONFIDENCE_DISCLAIMER
        }
    }), 200

