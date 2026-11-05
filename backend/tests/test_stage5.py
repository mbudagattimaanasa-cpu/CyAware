import io
import re
from unittest.mock import patch
import pytest
from PIL import Image
from backend.app.services.file_service import safe_delete_file


@pytest.fixture
def auth_user(client):
    """Fixture to register and login a user, returning user data and CSRF token."""
    client.post("/api/auth/register", json={
        "username": "stage5_user",
        "email": "stage5@example.com",
        "password": "Password123"
    })
    login_res = client.post("/api/auth/login", json={
        "username_or_email": "stage5_user",
        "password": "Password123"
    })
    data = login_res.get_json()["data"]
    return {
        "user": data["user"],
        "csrf_token": data["csrf_token"]
    }


def make_test_image_bytes(format="PNG", size=(100, 100), color="white"):
    """Generate in-memory image bytes using PIL."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


# =========================================================================
# 1. Batch File Upload Tests (/api/analyze/file)
# =========================================================================

def test_file_upload_valid_csv(client, auth_user):
    """Verify valid CSV with recognized 'text' header processes rows and returns category summary."""
    csv_content = "id,text,author\n1,Hello world,Alice\n2,You are an absolute idiot,Bob\n"
    data = {
        "file": (io.BytesIO(csv_content.encode("utf-8")), "chat.csv")
    }
    res = client.post(
        "/api/analyze/file",
        data=data,
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 200
    res_data = res.get_json()["data"]
    assert res_data["total_processed"] == 2
    assert res_data["filename"] == "chat.csv"
    assert res_data["category_summary"]["Normal"] == 1
    assert res_data["category_summary"]["Insult"] == 1
    assert len(res_data["results"]) == 2
    assert res_data["results"][0]["category"] == "Normal"
    assert res_data["results"][1]["category"] == "Insult"


def test_file_upload_valid_txt(client, auth_user):
    """Verify valid plain TXT file parses non-empty lines."""
    txt_content = "Good morning team.\nYou are completely useless.\nHave a great day!\n"
    data = {
        "file": (io.BytesIO(txt_content.encode("utf-8")), "messages.txt")
    }
    res = client.post(
        "/api/analyze/file",
        data=data,
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 200
    res_data = res.get_json()["data"]
    assert res_data["total_processed"] == 3
    assert res_data["filename"] == "messages.txt"


def test_file_upload_content_mismatch_binary_rejected(client, auth_user):
    """Verify binary/executable content disguised as .csv is rejected with 415 INVALID_FILE_CONTENT."""
    fake_exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00some fake executable payload"
    data = {
        "file": (io.BytesIO(fake_exe_bytes), "malicious.csv")
    }
    res = client.post(
        "/api/analyze/file",
        data=data,
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 415
    assert res.get_json()["error"]["code"] == "INVALID_FILE_CONTENT"


def test_file_upload_html_disguised_rejected(client, auth_user):
    """Verify HTML document disguised as .txt is rejected with 415 INVALID_FILE_CONTENT."""
    html_bytes = b"<!DOCTYPE html><html><body><h1>Phishing</h1></body></html>"
    data = {
        "file": (io.BytesIO(html_bytes), "page.txt")
    }
    res = client.post(
        "/api/analyze/file",
        data=data,
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 415
    assert res.get_json()["error"]["code"] == "INVALID_FILE_CONTENT"


def test_file_upload_ambiguous_csv_columns_rejected(client, auth_user):
    """Verify CSV lacking any recognized text column is rejected with 400 AMBIGUOUS_CSV_COLUMNS."""
    ambiguous_csv = "id,username,city,age\n1,john,Seattle,30\n2,mary,Boston,25\n"
    data = {
        "file": (io.BytesIO(ambiguous_csv.encode("utf-8")), "users.csv")
    }
    res = client.post(
        "/api/analyze/file",
        data=data,
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "AMBIGUOUS_CSV_COLUMNS"


def test_file_upload_exceeds_row_limit(client, auth_user):
    """Verify CSV with > 500 rows is rejected with 413 ROW_LIMIT_EXCEEDED."""
    lines = ["id,text"] + [f"{i},sample message {i}" for i in range(501)]
    large_csv = "\n".join(lines)
    data = {
        "file": (io.BytesIO(large_csv.encode("utf-8")), "large.csv")
    }
    res = client.post(
        "/api/analyze/file",
        data=data,
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 413
    assert res.get_json()["error"]["code"] == "ROW_LIMIT_EXCEEDED"


def test_file_upload_non_utf8_rejected(client, auth_user):
    """Verify non-UTF-8 encoded files return 422 ENCODING_ERROR."""
    invalid_utf8 = b"text\n" + b"\xff\xfe\x00\x12invalid bytes\x80\x81"
    data = {
        "file": (io.BytesIO(invalid_utf8), "bad_encoding.csv")
    }
    res = client.post(
        "/api/analyze/file",
        data=data,
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 422
    assert res.get_json()["error"]["code"] == "ENCODING_ERROR"


def test_file_upload_auth_and_csrf_required(client):
    """Verify /api/analyze/file requires authentication."""
    csv_bytes = b"text\nHello"
    res_unauth = client.post(
        "/api/analyze/file",
        data={"file": (io.BytesIO(csv_bytes), "test.csv")},
        content_type="multipart/form-data"
    )
    assert res_unauth.status_code == 401


# =========================================================================
# 2. Screenshot / Image OCR Tests (/api/analyze/image)
# =========================================================================

def test_ocr_corrupted_image_rejected(client, auth_user):
    """Verify corrupted image bytes return 422 CORRUPTED_IMAGE."""
    corrupted_bytes = b"\x89PNG\r\n\x1a\ncorrupted header and body"
    res = client.post(
        "/api/analyze/image",
        data={"image": (io.BytesIO(corrupted_bytes), "broken.png")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 422
    assert res.get_json()["error"]["code"] == "CORRUPTED_IMAGE"


def test_ocr_unsupported_image_extension_rejected(client, auth_user):
    """Verify unsupported extension (e.g. .gif) returns 415 INVALID_IMAGE_TYPE."""
    gif_bytes = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    res = client.post(
        "/api/analyze/image",
        data={"image": (io.BytesIO(gif_bytes), "anim.gif")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 415
    assert res.get_json()["error"]["code"] == "INVALID_IMAGE_TYPE"


def test_ocr_tiny_dimensions_rejected(client, auth_user):
    """Verify image with dimensions < 10x10 returns 422 INVALID_IMAGE_DIMENSIONS."""
    tiny_img = make_test_image_bytes(format="PNG", size=(5, 5))
    res = client.post(
        "/api/analyze/image",
        data={"image": (io.BytesIO(tiny_img), "tiny.png")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 422
    assert res.get_json()["error"]["code"] == "INVALID_IMAGE_DIMENSIONS"


def test_ocr_engine_missing_graceful_degradation(client, auth_user):
    """Verify missing Tesseract executable returns 503 OCR_ENGINE_NOT_AVAILABLE."""
    img_bytes = make_test_image_bytes(format="PNG", size=(100, 100))
    with patch("backend.app.services.ocr_service.find_tesseract_cmd", return_value=None):
        res = client.post(
            "/api/analyze/image",
            data={"image": (io.BytesIO(img_bytes), "test.png")},
            content_type="multipart/form-data",
            headers={"X-CSRF-Token": auth_user["csrf_token"]}
        )
        assert res.status_code == 503
        assert res.get_json()["error"]["code"] == "OCR_ENGINE_NOT_AVAILABLE"


def test_ocr_success_with_mocked_tesseract(client, auth_user):
    """Verify successful OCR extraction returns uncalibrated confidence score and handoff notice."""
    img_bytes = make_test_image_bytes(format="PNG", size=(200, 100))
    mock_data = {
        "text": ["", "Hey", "loser", "leave", "now"],
        "conf": [-1, 95.0, 92.0, 88.0, 91.0]
    }
    with patch("backend.app.services.ocr_service.find_tesseract_cmd", return_value="dummy_path"):
        with patch("backend.app.services.ocr_service._run_tesseract", return_value=mock_data):
            res = client.post(
                "/api/analyze/image",
                data={"image": (io.BytesIO(img_bytes), "screenshot.png")},
                content_type="multipart/form-data",
                headers={"X-CSRF-Token": auth_user["csrf_token"]}
            )
            assert res.status_code == 200
            data = res.get_json()["data"]
            assert data["extracted_text"] == "Hey loser leave now"
            assert data["ocr_confidence"] == 91.5
            assert "review and edit" in data["notice"].lower()


def test_ocr_blank_image_returns_no_text_extracted(client, auth_user):
    """Verify image producing zero alphanumeric characters returns 422 NO_TEXT_EXTRACTED."""
    img_bytes = make_test_image_bytes(format="PNG", size=(200, 100))
    mock_data = {
        "text": ["", "   ", "---"],
        "conf": [-1, 0, 0]
    }
    with patch("backend.app.services.ocr_service.find_tesseract_cmd", return_value="dummy_path"):
        with patch("backend.app.services.ocr_service._run_tesseract", return_value=mock_data):
            res = client.post(
                "/api/analyze/image",
                data={"image": (io.BytesIO(img_bytes), "blank.png")},
                content_type="multipart/form-data",
                headers={"X-CSRF-Token": auth_user["csrf_token"]}
            )
            assert res.status_code == 422
            assert res.get_json()["error"]["code"] == "NO_TEXT_EXTRACTED"


# =========================================================================
# 3. Conversation Processing Tests (/api/analyze/conversation)
# =========================================================================

def test_conversation_order_preservation(client, auth_user):
    """Verify conversation evaluates and returns messages in exact input order."""
    messages = [
        {"speaker": "UserA", "text": "Good morning team, let us review the project syllabus.", "timestamp": "2026-11-05T01:00:00Z"},
        {"speaker": "UserB", "text": "The conference will start at nine oclock.", "timestamp": "2026-11-05T01:01:00Z"},
        {"speaker": "UserA", "text": "Here are the meeting notes from yesterdays discussion.", "timestamp": "2026-11-05T01:02:00Z"}
    ]
    res = client.post(
        "/api/analyze/conversation",
        json={"messages": messages},
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    evals = data["message_evaluations"]
    assert len(evals) == 3
    assert evals[0]["index"] == 0 and evals[0]["speaker"] == "UserA"
    assert evals[1]["index"] == 1 and evals[1]["speaker"] == "UserB"
    assert evals[2]["index"] == 2 and evals[2]["speaker"] == "UserA"


def test_repeated_harm_single_flagged_is_false(client, auth_user):
    """Verify that exactly 1 flagged message NEVER triggers repeated_harm_indicator."""
    messages = [
        {"speaker": "UserA", "text": "Good morning team, let us review the project syllabus."},
        {"speaker": "UserB", "text": "You are completely stupid idiot."},  # 1 flagged
        {"speaker": "UserA", "text": "The conference will start at nine oclock."},
        {"speaker": "UserB", "text": "The weather forecast looks clear for today."},
        {"speaker": "UserA", "text": "Here are the meeting notes from yesterdays discussion."}
    ]
    res = client.post(
        "/api/analyze/conversation",
        json={"messages": messages},
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 200
    indicators = res.get_json()["data"]["conversation_indicators"]
    assert indicators["flagged_message_count"] == 1
    assert indicators["repeated_harm_indicator"] is False
    assert "isolated remark" in indicators["pattern_summary"].lower()


def test_repeated_harm_consecutive_flagged_is_true(client, auth_user):
    """Verify that 2 consecutive flagged messages trigger repeated_harm_indicator=True."""
    messages = [
        {"speaker": "UserA", "text": "Good morning team, let us review the project syllabus."},
        {"speaker": "UserB", "text": "You are completely stupid."},       # Flagged 1
        {"speaker": "UserB", "text": "Shut up you absolute idiot."},      # Flagged 2 (consecutive!)
        {"speaker": "UserA", "text": "The conference will start at nine oclock."},
        {"speaker": "UserA", "text": "The weather forecast looks clear for today."}
    ]
    res = client.post(
        "/api/analyze/conversation",
        json={"messages": messages},
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 200
    indicators = res.get_json()["data"]["conversation_indicators"]
    assert indicators["flagged_message_count"] == 2
    assert indicators["repeated_harm_indicator"] is True
    assert "potentially persistent" in indicators["pattern_summary"].lower()


def test_repeated_harm_thirty_percent_ratio_is_true(client, auth_user):
    """Verify that >= 30% flagged messages (even if non-consecutive) triggers repeated_harm_indicator=True."""
    # 2 flagged out of 6 total = 33.3% >= 30%
    messages = [
        {"speaker": "UserA", "text": "You are completely stupid idiot."},  # Flagged 1
        {"speaker": "UserB", "text": "Good morning team, let us review the project syllabus."},
        {"speaker": "UserB", "text": "The conference will start at nine oclock."},
        {"speaker": "UserA", "text": "You are a complete loser."},        # Flagged 2 (non-consecutive)
        {"speaker": "UserB", "text": "The weather forecast looks clear for today."},
        {"speaker": "UserB", "text": "Here are the meeting notes from yesterdays discussion."}
    ]
    res = client.post(
        "/api/analyze/conversation",
        json={"messages": messages},
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 200
    indicators = res.get_json()["data"]["conversation_indicators"]
    assert indicators["flagged_message_count"] == 2
    assert indicators["repeated_harm_indicator"] is True


def test_conversation_never_labels_bully_or_victim(client, auth_user):
    """Ethical boundary test: response payload must never contain 'bully' or 'victim' as roles."""
    messages = [
        {"speaker": "BullyTargeter", "text": "You are an idiot and a loser."},
        {"speaker": "HarassedUser", "text": "Good morning team, let us review the project syllabus."},
        {"speaker": "BullyTargeter", "text": "I will find you and kill you."}
    ]
    res = client.post(
        "/api/analyze/conversation",
        json={"messages": messages},
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 200
    raw_response_text = res.get_data(as_text=True)
    # Assert neither 'bully' nor 'victim' appears as a distinct word in the response
    assert not re.search(r"\b(bully|victim)\b", raw_response_text, re.IGNORECASE)


def test_conversation_persistence_rejected(client, auth_user):
    """Verify that passing save=true is rejected with 400 PERSISTENCE_NOT_SUPPORTED."""
    messages = [
        {"speaker": "UserA", "text": "Good morning team, let us review the project syllabus."},
        {"speaker": "UserB", "text": "The conference will start at nine oclock."}
    ]
    res = client.post(
        "/api/analyze/conversation",
        json={"messages": messages, "save": True},
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "PERSISTENCE_NOT_SUPPORTED"


def test_conversation_invalid_timestamp_rejected(client, auth_user):
    """Verify that invalid ISO-8601 timestamp string is rejected with 400 INVALID_TIMESTAMP."""
    messages = [
        {"speaker": "UserA", "text": "Good morning team", "timestamp": "yesterday at 5pm"},
        {"speaker": "UserB", "text": "The conference will start at nine oclock", "timestamp": "2026-11-05T01:00:00Z"}
    ]
    res = client.post(
        "/api/analyze/conversation",
        json={"messages": messages},
        headers={"X-CSRF-Token": auth_user["csrf_token"]}
    )
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "INVALID_TIMESTAMP"


def test_safe_delete_handles_exceptions_safely(tmp_path):
    """Verify safe_delete_file logs a warning and does not raise an unhandled exception."""
    non_existent = str(tmp_path / "non_existent_file.tmp")
    # Calling on non-existent file should complete without raising
    safe_delete_file(non_existent)
