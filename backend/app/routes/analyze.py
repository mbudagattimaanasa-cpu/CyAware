import os
import json
import tempfile
from flask import Blueprint, request, jsonify, session
from backend.app.services.nlp_service import nlp_service, CATEGORIES
from backend.app.services.file_service import (
    inspect_file_content,
    parse_csv_file,
    parse_txt_file,
    safe_delete_file,
    FileValidationError,
    MAX_FILE_BYTES,
)
from backend.app.services.ocr_service import extract_text_from_image, MAX_IMAGE_BYTES
from backend.app.services.conversation_service import process_conversation_sequence
from backend.app.middleware import login_required
from backend.app.database import execute_db

analyze_bp = Blueprint("analyze", __name__, url_prefix="/api/analyze")

MAX_TEXT_LENGTH = 2000


@analyze_bp.route("/text", methods=["POST"])
def analyze_text():
    """Analyze a single text message for cyberbullying indicators.
    
    - Supports guest analysis without persistence.
    - Saves analysis ONLY when an authenticated user explicitly specifies save=True.
    - Returns honest uncalibrated model decision confidence and severity=null.
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


@analyze_bp.route("/file", methods=["POST"])
@login_required
def analyze_file():
    """Analyze a batch message file (.csv or .txt) with strict format, encoding, and size validation."""
    if "file" not in request.files:
        return jsonify({
            "success": False,
            "error": {
                "code": "MISSING_FILE",
                "message": "No file uploaded in form field 'file'."
            }
        }), 400

    uploaded_file = request.files["file"]
    filename = uploaded_file.filename or ""

    if not filename:
        return jsonify({
            "success": False,
            "error": {
                "code": "MISSING_FILE",
                "message": "Empty filename provided."
            }
        }), 400

    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".csv", ".txt"):
        return jsonify({
            "success": False,
            "error": {
                "code": "INVALID_FILE_TYPE",
                "message": f"Unsupported file extension '{ext}'. Only .csv and .txt files are allowed."
            }
        }), 415

    temp_path = None
    try:
        # Create an isolated temporary file on disk
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tf:
            temp_path = tf.name
            uploaded_file.save(tf)

        with open(temp_path, "rb") as f:
            raw_bytes = f.read()

        # Inspect bytes for magic signatures and validate UTF-8 encoding
        decoded_content = inspect_file_content(raw_bytes, filename)

        # Parse rows based on extension
        if ext == ".csv":
            parsed_rows = parse_csv_file(decoded_content)
        else:
            parsed_rows = parse_txt_file(decoded_content)

        # Classify each row using NLP model
        summary = {c: 0 for c in CATEGORIES}
        results = []

        for row_idx, text_val in parsed_rows:
            pred = nlp_service.predict(text_val)
            cat = pred["category"]
            conf = pred["confidence"]
            summary[cat] = summary.get(cat, 0) + 1
            results.append({
                "index": row_idx,
                "text": text_val,
                "category": cat,
                "confidence": conf
            })

        user_id = session.get("user_id")
        client_ip = request.remote_addr or "127.0.0.1"
        execute_db(
            """INSERT INTO audit_logs (user_id, action, ip_address, details)
               VALUES (?, 'FILE_ANALYZED', ?, ?);""",
            (user_id, client_ip, f"File '{filename}' processed: {len(results)} rows evaluated")
        )

        return jsonify({
            "success": True,
            "data": {
                "filename": filename,
                "total_processed": len(results),
                "category_summary": summary,
                "results": results
            },
            "message": "File processed successfully."
        }), 200

    except FileValidationError as e:
        return jsonify({
            "success": False,
            "error": {
                "code": e.code,
                "message": e.message
            }
        }), e.status_code
    except Exception as e:
        return jsonify({
            "success": False,
            "error": {
                "code": "FILE_PROCESSING_ERROR",
                "message": f"An error occurred while processing the file: {str(e)}"
            }
        }), 500
    finally:
        # Guaranteed cleanup with safe failure logging
        if temp_path:
            safe_delete_file(temp_path)


@analyze_bp.route("/image", methods=["POST"])
@login_required
def analyze_image():
    """Extract text from an uploaded screenshot using Tesseract OCR for human verification and handoff."""
    if "image" not in request.files:
        return jsonify({
            "success": False,
            "error": {
                "code": "MISSING_IMAGE",
                "message": "No image uploaded in form field 'image'."
            }
        }), 400

    uploaded_img = request.files["image"]
    filename = uploaded_img.filename or ""

    if not filename:
        return jsonify({
            "success": False,
            "error": {
                "code": "MISSING_IMAGE",
                "message": "Empty filename provided."
            }
        }), 400

    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        return jsonify({
            "success": False,
            "error": {
                "code": "INVALID_IMAGE_TYPE",
                "message": f"Unsupported image extension '{ext}'. Only .png, .jpg, and .jpeg are allowed."
            }
        }), 415

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tf:
            temp_path = tf.name
            uploaded_img.save(tf)

        with open(temp_path, "rb") as f:
            raw_bytes = f.read()

        ocr_result = extract_text_from_image(raw_bytes)

        user_id = session.get("user_id")
        client_ip = request.remote_addr or "127.0.0.1"
        execute_db(
            """INSERT INTO audit_logs (user_id, action, ip_address, details)
               VALUES (?, 'IMAGE_OCR_EXTRACTED', ?, ?);""",
            (user_id, client_ip, f"Image '{filename}' OCR completed with score {ocr_result['ocr_confidence']}")
        )

        return jsonify({
            "success": True,
            "data": ocr_result,
            "message": "Text extracted successfully."
        }), 200

    except FileValidationError as e:
        return jsonify({
            "success": False,
            "error": {
                "code": e.code,
                "message": e.message
            }
        }), e.status_code
    except Exception as e:
        return jsonify({
            "success": False,
            "error": {
                "code": "OCR_PROCESSING_ERROR",
                "message": f"Failed to extract text from image: {str(e)}"
            }
        }), 500
    finally:
        if temp_path:
            safe_delete_file(temp_path)


@analyze_bp.route("/conversation", methods=["POST"])
@login_required
def analyze_conversation():
    """Analyze a sequential multi-turn conversation while preserving input order.
    
    Conversation analysis is strictly ephemeral and not persisted to user history.
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

    # Explicit rejection of persistence for conversation analysis
    if data.get("save") is True:
        return jsonify({
            "success": False,
            "error": {
                "code": "PERSISTENCE_NOT_SUPPORTED",
                "message": "Conversation analysis is ephemeral and not stored in user history in this version."
            }
        }), 400

    messages = data.get("messages")
    if not isinstance(messages, list):
        return jsonify({
            "success": False,
            "error": {
                "code": "INVALID_CONVERSATION",
                "message": "Field 'messages' is required and must be an array of message objects."
            }
        }), 400

    try:
        result = process_conversation_sequence(messages)

        user_id = session.get("user_id")
        client_ip = request.remote_addr or "127.0.0.1"
        flagged_count = result["conversation_indicators"]["flagged_message_count"]
        total_turns = result["conversation_indicators"]["total_messages"]

        execute_db(
            """INSERT INTO audit_logs (user_id, action, ip_address, details)
               VALUES (?, 'CONVERSATION_ANALYZED', ?, ?);""",
            (user_id, client_ip, f"Conversation analyzed: {total_turns} turns, {flagged_count} flagged")
        )

        return jsonify({
            "success": True,
            "data": result,
            "message": "Conversation analyzed successfully."
        }), 200

    except FileValidationError as e:
        return jsonify({
            "success": False,
            "error": {
                "code": e.code,
                "message": e.message
            }
        }), e.status_code
    except Exception as e:
        return jsonify({
            "success": False,
            "error": {
                "code": "CONVERSATION_PROCESSING_ERROR",
                "message": f"Failed to analyze conversation: {str(e)}"
            }
        }), 500
