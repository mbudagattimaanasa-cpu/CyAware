import os
import shutil
import io
import re
import logging
from typing import Dict, Any
from PIL import Image, UnidentifiedImageError
from backend.app.services.file_service import FileValidationError, safe_delete_file

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_FORMATS = {"PNG", "JPEG"}
MIN_DIM = 10
MAX_DIM = 8000

# Try importing pytesseract
try:
    import pytesseract
    from pytesseract import Output
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False


def find_tesseract_cmd() -> str:
    """Locate the Tesseract executable path on the system or return None if missing."""
    # 1. Environment variable override
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd and os.path.exists(env_cmd):
        return env_cmd

    # 2. System PATH
    which_path = shutil.which("tesseract")
    if which_path:
        return which_path

    # 3. Standard Windows installation locations
    standard_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for p in standard_paths:
        if os.path.exists(p):
            return p

    return None


def _run_tesseract(gray_img):
    """Internal helper to execute Tesseract OCR and extract word data dictionary."""
    import pytesseract
    from pytesseract import Output
    return pytesseract.image_to_data(gray_img, output_type=Output.DICT)


def extract_text_from_image(image_bytes: bytes) -> Dict[str, Any]:
    """Validate image bytes and extract text using Tesseract OCR.
    
    The returned ocr_confidence is an uncalibrated character recognition engine score (0-100),
    not a statistical guarantee of transcription accuracy.
    """
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise FileValidationError(
            "IMAGE_TOO_LARGE",
            f"Image exceeds maximum allowed size of {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
            status_code=413
        )

    # Validate image format and dimensions using PIL
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()  # Verify integrity
        # Reopen for processing because verify() mutates file pointer
        image = Image.open(io.BytesIO(image_bytes))
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise FileValidationError(
            "CORRUPTED_IMAGE",
            f"Image file is corrupted, unreadable, or invalid: {str(e)}",
            status_code=422
        )

    fmt = (image.format or "").upper()
    if fmt not in ALLOWED_FORMATS:
        raise FileValidationError(
            "INVALID_IMAGE_TYPE",
            f"Image format '{fmt}' is not supported. Only PNG and JPEG/JPG are allowed.",
            status_code=415
        )

    w, h = image.size
    if w < MIN_DIM or h < MIN_DIM:
        raise FileValidationError(
            "INVALID_IMAGE_DIMENSIONS",
            f"Image dimensions ({w}x{h}) are too small. Minimum is {MIN_DIM}x{MIN_DIM}.",
            status_code=422
        )

    if w > MAX_DIM or h > MAX_DIM:
        raise FileValidationError(
            "IMAGE_TOO_LARGE",
            f"Image dimensions ({w}x{h}) exceed maximum allowed dimensions of {MAX_DIM}x{MAX_DIM}.",
            status_code=413
        )

    # Check Tesseract engine availability
    tesseract_cmd = find_tesseract_cmd()
    if not PYTESSERACT_AVAILABLE or not tesseract_cmd:
        raise FileValidationError(
            "OCR_ENGINE_NOT_AVAILABLE",
            "Tesseract OCR engine is not configured or installed on the host server.",
            status_code=503
        )

    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    # Pre-process image to grayscale for cleaner extraction
    gray_img = image.convert("L")

    try:
        # Extract word data with engine confidence metrics
        data = _run_tesseract(gray_img)
    except Exception as e:
        logger.error("Tesseract OCR execution failed: %s", e)
        raise FileValidationError(
            "OCR_EXECUTION_ERROR",
            f"OCR processing failed: {str(e)}",
            status_code=500
        )

    confidences = []
    text_words = []

    for word, conf in zip(data.get("text", []), data.get("conf", [])):
        cleaned_word = word.strip()
        if cleaned_word:
            text_words.append(cleaned_word)
            try:
                c_val = float(conf)
                if c_val >= 0:
                    confidences.append(c_val)
            except (ValueError, TypeError):
                pass

    extracted_text = " ".join(text_words).strip()

    # Reject if no legible alphanumeric characters found
    if not extracted_text or not re.search(r"[a-zA-Z0-9]", extracted_text):
        raise FileValidationError(
            "NO_TEXT_EXTRACTED",
            "No legible text could be extracted from the uploaded image.",
            status_code=422
        )

    avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

    return {
        "extracted_text": extracted_text,
        "ocr_confidence": avg_confidence,
        "notice": "Please review and edit the extracted text above before submitting for cyberbullying analysis."
    }

