import os
import csv
import io
import logging
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# Maximum file constraints
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_ALLOWED_ROWS = 500

# Canonical recognized column headers for text in CSV
RECOGNIZED_TEXT_COLUMNS = {"text", "message", "content", "comment", "tweet", "body"}

# Forbidden binary magic signatures
FORBIDDEN_SIGNATURES = [
    b"MZ",              # DOS / Windows PE Executable
    b"\x7fELF",         # Linux ELF Executable
    b"PK\x03\x04",      # ZIP / Archive format
    b"\x1f\x8b",        # GZIP
    b"%PDF",            # PDF document
    b"\x00\x00\x00",    # Binary null padding
]


class FileValidationError(Exception):
    """Custom exception for file validation failures."""
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def safe_delete_file(file_path: str):
    """Safely unlink a temporary file and log any deletion failures rather than silently swallowing."""
    if file_path and os.path.exists(file_path):
        try:
            os.unlink(file_path)
        except OSError as e:
            logger.warning("Failed to delete temporary file '%s': %s", file_path, e)


def inspect_file_content(file_bytes: bytes, filename: str):
    """Inspect raw bytes to ensure file is legitimate text and not a renamed binary or executable."""
    if len(file_bytes) > MAX_FILE_BYTES:
        raise FileValidationError(
            "FILE_TOO_LARGE",
            f"File exceeds maximum allowed size of {MAX_FILE_BYTES // (1024 * 1024)} MB.",
            status_code=413
        )

    # Inspect magic bytes
    sample = file_bytes[:16]
    for sig in FORBIDDEN_SIGNATURES:
        if sample.startswith(sig):
            raise FileValidationError(
                "INVALID_FILE_CONTENT",
                "File contains binary or executable content that is not allowed.",
                status_code=415
            )

    # Check for HTML / XML / Script signatures in CSV/TXT
    sample_text = file_bytes[:512].lower()
    if b"<!doctype html" in sample_text or b"<html" in sample_text or b"<script" in sample_text:
        raise FileValidationError(
            "INVALID_FILE_CONTENT",
            "HTML or script documents cannot be processed as text data files.",
            status_code=415
        )

    # Strict UTF-8 validation
    try:
        decoded_text = file_bytes.decode("utf-8")
        return decoded_text
    except UnicodeDecodeError as e:
        raise FileValidationError(
            "ENCODING_ERROR",
            "File must be valid UTF-8 encoded text.",
            status_code=422
        )


def parse_csv_file(text_content: str) -> List[Tuple[int, str]]:
    """Parse CSV text, enforce row limits, validate column structure without ambiguous guessing,
    and return list of (original_row_number, text).
    """
    lines = text_content.splitlines()
    total_raw_rows = len(lines)

    if total_raw_rows == 0:
        raise FileValidationError("INVALID_CSV_STRUCTURE", "CSV file is empty.", status_code=400)

    if total_raw_rows > MAX_ALLOWED_ROWS:
        raise FileValidationError(
            "ROW_LIMIT_EXCEEDED",
            f"File contains {total_raw_rows} rows, exceeding the limit of {MAX_ALLOWED_ROWS} rows.",
            status_code=413
        )

    try:
        reader = csv.reader(io.StringIO(text_content))
        header = next(reader, None)
    except Exception as e:
        raise FileValidationError("INVALID_CSV_FORMAT", f"Malformed CSV structure: {str(e)}", status_code=400)

    if not header:
        raise FileValidationError("INVALID_CSV_STRUCTURE", "CSV file has no header row.", status_code=400)

    # Case-insensitive header matching
    header_lower = [col.strip().lower() for col in header]
    matched_col_idx = None

    for idx, col_name in enumerate(header_lower):
        if col_name in RECOGNIZED_TEXT_COLUMNS:
            matched_col_idx = idx
            break

    if matched_col_idx is None:
        accepted_list = ", ".join(sorted(RECOGNIZED_TEXT_COLUMNS))
        raise FileValidationError(
            "AMBIGUOUS_CSV_COLUMNS",
            f"CSV must contain a recognized text column header ({accepted_list}). No ambiguous column selection is permitted.",
            status_code=400
        )

    parsed_items = []
    for row_num, row in enumerate(reader, start=2):
        if not row:
            continue  # Skip blank row
        if matched_col_idx < len(row):
            val = row[matched_col_idx].strip()
            if val:
                parsed_items.append((row_num, val))

    if not parsed_items:
        raise FileValidationError(
            "INVALID_CSV_STRUCTURE",
            "CSV file does not contain any non-empty text entries in the recognized column.",
            status_code=400
        )

    return parsed_items


def parse_txt_file(text_content: str) -> List[Tuple[int, str]]:
    """Parse plain text file into (line_number, line_text) pairs up to MAX_ALLOWED_ROWS."""
    lines = text_content.splitlines()
    total_lines = len(lines)

    if total_lines == 0:
        raise FileValidationError("INVALID_FILE_CONTENT", "TXT file is empty.", status_code=400)

    if total_lines > MAX_ALLOWED_ROWS:
        raise FileValidationError(
            "ROW_LIMIT_EXCEEDED",
            f"File contains {total_lines} lines, exceeding the limit of {MAX_ALLOWED_ROWS} lines.",
            status_code=413
        )

    parsed_items = []
    for line_num, line in enumerate(lines, start=1):
        cleaned = line.strip()
        if cleaned:
            parsed_items.append((line_num, cleaned))

    if not parsed_items:
        raise FileValidationError("INVALID_FILE_CONTENT", "TXT file contains only blank lines.", status_code=400)

    return parsed_items

