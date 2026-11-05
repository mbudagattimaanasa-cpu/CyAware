import json
from flask import Blueprint, request, jsonify, session
from backend.app.services.nlp_service import nlp_service
from backend.app.database import execute_db

analyze_bp = Blueprint("analyze", __name__, url_prefix="/api/analyze")

MAX_TEXT_LENGTH = 2000


@analyze_bp.route("/text", methods=["POST"])
def analyze_text():
    """Analyze a single text message for cyberbullying indicators.
    
    - Supports guest analysis without persistence.
    - Saves analysis ONLY when an authenticated user explicitly specifies save=True.
    - Returns honest model decision confidence (uncalibrated score) and severity=null.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request payload must be valid JSON."
            }
        }), 400

    raw_text = data.get("text")
    if raw_text is None or not isinstance(raw_text, str):
        return jsonify({
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Field 'text' is required and must be a string."
            }
        }), 400

    trimmed_text = raw_text.strip()
    if not trimmed_text:
        return jsonify({
            "success": False,
            "error": {
                "code": "EMPTY_TEXT",
                "message": "Text cannot be empty."
            }
        }), 400

    if len(raw_text) > MAX_TEXT_LENGTH:
        return jsonify({
            "success": False,
            "error": {
                "code": "TEXT_TOO_LONG",
                "message": f"Text exceeds maximum limit of {MAX_TEXT_LENGTH} characters."
            }
        }), 413

    # Opt-in persistence flag
    save_opt_in = bool(data.get("save", False))
    user_id = session.get("user_id")

    # If the user requests to save, they MUST be authenticated
    if save_opt_in and not user_id:
        return jsonify({
            "success": False,
            "error": {
                "code": "UNAUTHENTICATED",
                "message": "Authentication required to save analysis history."
            }
        }), 401

    # Perform prediction using NLP service
    try:
        prediction = nlp_service.predict(trimmed_text)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": {
                "code": "INFERENCE_ERROR",
                "message": f"Failed to analyze text: {str(e)}"
            }
        }), 500

    category = prediction["category"]
    confidence = prediction["confidence"]
    severity = None  # Explicitly null per product agreement
    highlighted_terms = prediction["highlighted_terms"]
    explanation = prediction["explanation"]
    safety_recommendation = prediction["safety_recommendation"]
    safer_rewrite = prediction["safer_rewrite"]

    saved_id = None

    # Opt-in persistence: only save if explicitly requested by authenticated user
    if save_opt_in and user_id:
        highlighted_json = json.dumps(highlighted_terms)
        saved_id = execute_db(
            """INSERT INTO saved_analyses (
                   user_id, text_content, category, confidence, severity,
                   explanation, highlighted_terms_json, safer_rewrite
               ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?);""",
            (
                user_id,
                trimmed_text,
                category,
                confidence,
                explanation,
                highlighted_json,
                safer_rewrite,
            )
        )

        # Audit log entry without recording the private message text
        client_ip = request.remote_addr or "127.0.0.1"
        execute_db(
            """INSERT INTO audit_logs (user_id, action, ip_address, details)
               VALUES (?, 'ANALYSIS_SAVED', ?, ?);""",
            (user_id, client_ip, f"Analysis ID {saved_id} saved for category '{category}'")
        )

    return jsonify({
        "success": True,
        "data": {
            "category": category,
            "confidence": confidence,
            "severity": severity,
            "highlighted_terms": highlighted_terms,
            "explanation": explanation,
            "safety_recommendation": safety_recommendation,
            "safer_rewrite": safer_rewrite,
            "saved_id": saved_id
        },
        "message": "Analysis completed successfully."
    }), 200

