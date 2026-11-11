# CyAware — Shared API Specification & Frontend Integration Contract

**Version:** 1.0.0  
**Backend Branch:** `CyAware-Backend`  
**Status:** Canonical Reference for Frontend & Backend Integration  

---

## 1. Project Overview & Architectural Conventions

CyAware is an NLP-based cyberbullying and harmful communication detection system. It employs a **TF-IDF + Logistic Regression** baseline model trained on standardized text datasets to analyze and classify text messages across 5 canonical categories.

### Architectural Principles:
- **Backend Stack:** Flask 3.x, SQLite 3 (with `PRAGMA foreign_keys = ON;`), scikit-learn.
- **Language Scope:** **English-first model**. CyAware does not claim unvalidated multilingual support.
- **Decision Philosophy:** The backend provides **informational and advisory analysis** for human review. It does **not** perform automatic blocking, punishment, censorship, or automated reporting to authorities.
- **Regulatory Transparency:** CyAware incorporates user data export and atomic account deletion safeguards, but does **not** claim automated or certified compliance with GDPR or other regional regulations.

---

## 2. Base URL, Protocols & Content Negotiation

- **Base URL Prefix:** All backend API endpoints are mounted under `/api`.
- **Default Port:** `http://127.0.0.1:5000` (development server).
- **Transport Security:** Production deployments require HTTPS. In local development, HTTP is permitted.
- **Content Negotiation:**
  - Standard JSON requests: `Content-Type: application/json`, `Accept: application/json`.
  - File upload requests: `multipart/form-data`.
- **Global Security Headers:** Every API response includes:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Content-Security-Policy: default-src 'self'`

---

## 3. Session Authentication & Cookie Policy

- **Session Mechanism:** CyAware utilizes Flask server-managed sessions stored via a cryptographically signed cookie named `session`.
- **Cookie Attributes:**
  - `HttpOnly = True` (inaccessible to client-side JavaScript `document.cookie`).
  - `SameSite = "Lax"` (mitigates CSRF on cross-site requests).
  - `Secure = False` in development; `Secure = True` in production.
- **Browser Fetch Credential Handling:**
  - **Same-Origin Requests (Standard Deployment):** In modern browsers, `fetch()` requests to the same origin include cookies by default (`credentials: "same-origin"`). When frontend and backend share an origin or are served through a reverse proxy (e.g., Nginx), cookies are sent automatically.
  - **Cross-Origin Requests:** If the frontend and backend run on different origins during development, `fetch()` must specify `{ credentials: "include" }`.
  - **CORS Notice:** The CyAware backend currently has **no CORS middleware or headers configured**. Cross-origin requests will be blocked by the browser’s Same-Origin Policy unless an origin proxy is configured.

---

## 4. Cross-Site Request Forgery (CSRF) Protection

- **Scope:** State-changing HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`) are subject to CSRF validation whenever an active authenticated session exists (`session["user_id"]` is set).
- **Token Acquisition:**
  1. Returned in `data.csrf_token` upon successful login (`POST /api/auth/login`).
  2. Or fetched via `GET /api/auth/csrf-token`.
- **Request Transmission:** Pass the token in the HTTP request headers:
  - Header name: `X-CSRF-Token` (or `X-CSRFToken`).
- **Exemptions:**
  - Safe methods: `GET`, `HEAD`, `OPTIONS`.
  - Unauthenticated requests: `POST /api/auth/register`, `POST /api/auth/login`, and guest analysis (`POST /api/analyze/text` with `save=false`).
- **Error Response (403):** If the CSRF token is missing, expired, or invalid on an authenticated state-changing request:
  ```json
  {
    "success": false,
    "error": {
      "code": "CSRF_ERROR",
      "message": "CSRF token missing or invalid."
    }
  }
  ```

---

## 5. Unified JSON Response Envelopes

Every API endpoint returns a standardized JSON structure.

### Success Envelope (HTTP 2xx)
```json
{
  "success": true,
  "data": { ... },
  "message": "Optional human-readable confirmation string."
}
```
*(Note: Some endpoints return only `data`, some return both `data` and `message`, and some return only `message` on resource deletion).*

### Error Envelope (HTTP 4xx / 5xx)
```json
{
  "success": false,
  "error": {
    "code": "STANDARDIZED_ERROR_CODE",
    "message": "Human-readable description of the error."
  }
}
```

---

## 6. Implemented Endpoints Inventory

The following **15 endpoints** are implemented, tested, and available in the CyAware backend:

| # | Method | URL Path | Auth Required | CSRF Required | Short Purpose |
| :-: | :--- | :--- | :-: | :-: | :--- |
| 1 | `GET` | `/api/health` | No | No | Health check and database ping |
| 2 | `POST` | `/api/auth/register` | No | No | Register new user account |
| 3 | `POST` | `/api/auth/login` | No | No | Authenticate user & issue session cookie |
| 4 | `GET` | `/api/auth/csrf-token` | No | No | Retrieve active session CSRF token |
| 5 | `POST` | `/api/auth/logout` | Yes | Yes | Invalidate session & log out |
| 6 | `GET` | `/api/auth/me` | Yes | No | Fetch authenticated user profile |
| 7 | `POST` | `/api/analyze/text` | Optional* | Conditional* | Analyze single message (*Auth & CSRF required if `save=true`) |
| 8 | `POST` | `/api/analyze/file` | Yes | Yes | Batch CSV/TXT file text analysis |
| 9 | `POST` | `/api/analyze/image` | Yes | Yes | Screenshot OCR text extraction |
| 10 | `POST` | `/api/analyze/conversation` | Yes | Yes | Multi-turn sequence analysis |
| 11 | `GET` | `/api/analyses` | Yes | No | Paginated saved analysis history |
| 12 | `DELETE`| `/api/analyses/<int:analysis_id>`| Yes | Yes | Delete a saved analysis record |
| 13 | `GET` | `/api/dashboard` | Yes | No | Personal dashboard statistics & activity |
| 14 | `GET` | `/api/user/export` | Yes | No | Export personal user data (`no-store`) |
| 15 | `DELETE`| `/api/user/account` | Yes | Yes | Permanently delete user account (`no-store`) |

---

## 7. Endpoint Specifications & Examples

### 7.1 `GET /api/health`
- **Purpose:** System status probe and database connectivity verification.
- **Request:** None.
- **Success Response (200):**
  ```json
  {
    "success": true,
    "data": {
      "status": "healthy",
      "database": "connected",
      "timestamp": "2026-11-11T14:00:00.000000+00:00",
      "version": "1.0.0-stage2"
    },
    "message": "CyAware Backend API is operational."
  }
  ```
  *(Returns `"status": "degraded"` if database execution fails).*

---

### 7.2 `POST /api/auth/register`
- **Purpose:** Create a new standard user account (`role` is forced to `'user'`).
- **Request Headers:** `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "username": "alice_smith",
    "email": "alice@example.com",
    "password": "Password123"
  }
  ```
- **Validation Constraints:**
  - `username`: 3–30 characters, letters, numbers, underscores (`^[a-zA-Z0-9_]{3,30}$`).
  - `email`: valid email syntax, maximum 120 characters, converted to lowercase.
  - `password`: minimum 8 characters, at least 1 letter and 1 digit.
- **Success Response (201):**
  ```json
  {
    "success": true,
    "data": {
      "user": {
        "id": 1,
        "username": "alice_smith",
        "email": "alice@example.com",
        "role": "user",
        "created_at": "2026-11-11 14:00:00"
      }
    },
    "message": "Account created successfully."
  }
  ```
- **Error Responses:**
  - `400 VALIDATION_ERROR`: Field validation failure.
  - `409 USER_EXISTS`: Username or email already registered.

---

### 7.3 `POST /api/auth/login`
- **Purpose:** Authenticate user, issue session cookie, and return CSRF token.
- **Request Headers:** `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "username_or_email": "alice_smith",
    "password": "Password123"
  }
  ```
- **Throttling:** Max 5 failed attempts per 300 seconds (5 min) per IP + identifier.
- **Success Response (200):** Sets `Set-Cookie: session=...; HttpOnly; SameSite=Lax`.
  ```json
  {
    "success": true,
    "data": {
      "user": {
        "id": 1,
        "username": "alice_smith",
        "email": "alice@example.com",
        "role": "user"
      },
      "csrf_token": "9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e"
    },
    "message": "Logged in successfully."
  }
  ```
- **Error Responses:**
  - `400 VALIDATION_ERROR`: Missing username/email or password.
  - `401 INVALID_CREDENTIALS`: Password mismatch or user not found.
  - `401 ACCOUNT_DISABLED`: User account deactivated (`is_active = 0`).
  - `429 RATE_LIMITED`: Throttled due to repeated failed logins.

---

### 7.4 `GET /api/auth/csrf-token`
- **Purpose:** Retrieve or establish a CSRF token for the active session.
- **Request:** None.
- **Success Response (200):**
  ```json
  {
    "success": true,
    "data": {
      "csrf_token": "9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e"
    }
  }
  ```

---

### 7.5 `POST /api/auth/logout`
- **Purpose:** Invalidate the active user session and clear session cookies.
- **Headers:** `X-CSRF-Token: <token>`
- **Request:** Empty body.
- **Success Response (200):**
  ```json
  {
    "success": true,
    "message": "Logged out successfully."
  }
  ```
- **Error Responses:** `401 UNAUTHENTICATED`, `403 CSRF_ERROR`.

---

### 7.6 `GET /api/auth/me`
- **Purpose:** Fetch profile information for the authenticated session.
- **Request:** None.
- **Success Response (200):**
  ```json
  {
    "success": true,
    "data": {
      "user": {
        "id": 1,
        "username": "alice_smith",
        "email": "alice@example.com",
        "role": "user"
      }
    }
  }
  ```
- **Error Responses:** `401 UNAUTHENTICATED`.

---

### 7.7 `POST /api/analyze/text`
- **Purpose:** Analyze a single text message for cyberbullying indicators.
- **Auth & CSRF Rules:**
  - Guest mode: `save=false` (or omitted). Requires no authentication or CSRF token.
  - Persistence mode: `save=true`. Requires an active session (`@login_required`) and a valid `X-CSRF-Token`.
- **Request Body:**
  ```json
  {
    "text": "You are a complete loser, get off the team",
    "save": true
  }
  ```
- **Constraints:** `text` must be 1 to 2,000 characters after stripping whitespace.
- **Success Response (200):**
  ```json
  {
    "success": true,
    "data": {
      "category": "Insult",
      "confidence": 0.9142,
      "severity": null,
      "highlighted_terms": ["loser"],
      "explanation": "Prediction based on high-weight terms: loser",
      "safety_recommendation": "Take a moment before responding. Avoid escalating with counter-insults and consider setting conversation boundaries.",
      "safer_rewrite": "I have strong disagreements with this behavior, but I would like to resolve it constructively.",
      "saved_id": 42
    },
    "message": "Analysis completed successfully."
  }
  ```
  *(Note: `saved_id` is an `integer` if saved; `null` if unsaved. `safer_rewrite` is `null` for `"Normal"` category. `severity` is always `null`).*
- **Error Responses:**
  - `400 VALIDATION_ERROR`: Invalid JSON or non-string `text`.
  - `400 EMPTY_TEXT`: Text contains only whitespace.
  - `401 UNAUTHENTICATED`: `save=true` specified without active session.
  - `403 CSRF_ERROR`: Authenticated session missing valid CSRF token.
  - `413 TEXT_TOO_LONG`: `text` exceeds 2,000 characters.
  - `500 INFERENCE_ERROR`: Model inference runtime failure.

---

### 7.8 `POST /api/analyze/file`
- **Purpose:** Analyze batch text messages from an uploaded `.csv` or `.txt` file.
- **Auth:** `@login_required` (HTTP 401).
- **CSRF:** Required (`X-CSRF-Token` header; HTTP 403).
- **Request Format:** `multipart/form-data` with form field `'file'`.
- **Constraints:**
  - Maximum size: 2 MB (`2,097,152` bytes).
  - Maximum records: 500 lines/rows.
  - Allowed extensions: `.csv`, `.txt`.
  - Encoding: Strict UTF-8.
  - CSV recognized columns: `text`, `message`, `content`, `comment`, `tweet`, `body`.
- **Success Response (200):**
  ```json
  {
    "success": true,
    "data": {
      "filename": "chat_export.csv",
      "total_processed": 3,
      "category_summary": {
        "Normal": 2,
        "Insult": 1,
        "Threat": 0,
        "Hate Speech": 0,
        "Toxic/Abusive Language": 0
      },
      "results": [
        {"index": 1, "text": "Good work today team", "category": "Normal", "confidence": 0.96},
        {"index": 2, "text": "You are pathetic", "category": "Insult", "confidence": 0.89},
        {"index": 3, "text": "See you tomorrow", "category": "Normal", "confidence": 0.99}
      ]
    },
    "message": "File processed successfully."
  }
  ```
- **Error Responses:**
  - `400 MISSING_FILE`: Field `'file'` absent or filename empty.
  - `400 INVALID_CSV_STRUCTURE`: Empty CSV or unrecognized column header.
  - `400 AMBIGUOUS_CSV_COLUMNS`: Multiple candidate text columns found.
  - `413 FILE_TOO_LARGE`: Exceeds 2 MB.
  - `413 ROW_LIMIT_EXCEEDED`: Exceeds 500 rows.
  - `415 INVALID_FILE_TYPE`: Extension not `.csv` or `.txt`.
  - `415 INVALID_FILE_CONTENT`: Executable signatures (MZ, ELF, PK, etc.) or embedded HTML/script.
  - `422 ENCODING_ERROR`: Non-UTF-8 bytes encountered.
  - `500 FILE_PROCESSING_ERROR`: General file parsing exception.

---

### 7.9 `POST /api/analyze/image`
- **Purpose:** Extract text from an uploaded screenshot via Tesseract OCR for human verification.
- **Auth:** `@login_required` (HTTP 401).
- **CSRF:** Required (`X-CSRF-Token` header; HTTP 403).
- **Request Format:** `multipart/form-data` with form field `'image'`.
- **Constraints:**
  - Maximum size: 5 MB (`5,242,880` bytes).
  - Allowed extensions: `.png`, `.jpg`, `.jpeg`.
  - Image dimensions: Minimum 10x10 px; maximum 8000x8000 px.
- **Success Response (200):**
  ```json
  {
    "success": true,
    "data": {
      "extracted_text": "Hey loser leave now",
      "ocr_confidence": 91.5,
      "notice": "Please review and edit the extracted text above before submitting for cyberbullying analysis."
    },
    "message": "Text extracted successfully."
  }
  ```
- **Error Responses:**
  - `400 MISSING_IMAGE`: Field `'image'` missing or empty filename.
  - `413 IMAGE_TOO_LARGE`: File size exceeds 5 MB or dimensions exceed 8,000 px.
  - `415 INVALID_IMAGE_TYPE`: Extension or PIL format not PNG/JPEG.
  - `422 CORRUPTED_IMAGE`: File damaged or unreadable by image parser.
  - `422 INVALID_IMAGE_DIMENSIONS`: Dimensions smaller than 10x10 px.
  - `422 NO_TEXT_EXTRACTED`: Zero legible alphanumeric characters found.
  - `500 OCR_EXECUTION_ERROR`: Tesseract engine runtime crash.
  - `500 OCR_PROCESSING_ERROR`: Unhandled exception in image route.
  - `503 OCR_ENGINE_NOT_AVAILABLE`: Tesseract binary missing or not configured on server.

---

### 7.10 `POST /api/analyze/conversation`
- **Purpose:** Analyze a multi-turn sequential conversation while strictly preserving message order.
- **Auth:** `@login_required` (HTTP 401).
- **CSRF:** Required (`X-CSRF-Token` header; HTTP 403).
- **Request Body (JSON):**
  ```json
  {
    "messages": [
      {"speaker": "Alex", "text": "Are you joining the group call tonight?", "timestamp": "2026-11-11T18:00:00Z"},
      {"speaker": "Jordan", "text": "No, you idiots never do anything productive.", "timestamp": "2026-11-11T18:01:00Z"},
      {"speaker": "Jordan", "text": "Shut up and stop asking me.", "timestamp": "2026-11-11T18:02:00Z"}
    ]
  }
  ```
- **Constraints:**
  - `messages`: Array of 2 to 50 turns.
  - Each message `text`: 1 to 1,000 characters.
  - `speaker`: Optional string (default `"Unknown"`, truncated to 100 chars).
  - `timestamp`: Optional ISO-8601 string.
  - `save`: Persistence is **not supported**; `save=true` returns HTTP 400.
- **Success Response (200):**
  ```json
  {
    "success": true,
    "data": {
      "conversation_indicators": {
        "total_messages": 3,
        "flagged_message_count": 2,
        "repeated_harm_indicator": true,
        "pattern_summary": "2 of 3 messages were flagged with harmful tone (Insult). Observed pattern indicates potentially persistent hostile communication. This serves as an indicator to aid human review and does not constitute definitive proof of harmful behavior."
      },
      "message_evaluations": [
        {
          "index": 0,
          "speaker": "Alex",
          "category": "Normal",
          "confidence": 0.95,
          "highlighted_terms": [],
          "timestamp": "2026-11-11T18:00:00Z"
        },
        {
          "index": 1,
          "speaker": "Jordan",
          "category": "Insult",
          "confidence": 0.89,
          "highlighted_terms": ["idiots"],
          "timestamp": "2026-11-11T18:01:00Z"
        },
        {
          "index": 2,
          "speaker": "Jordan",
          "category": "Insult",
          "confidence": 0.84,
          "highlighted_terms": ["shut up"],
          "timestamp": "2026-11-11T18:02:00Z"
        }
      ]
    },
    "message": "Conversation analyzed successfully."
  }
  ```
- **Error Responses:**
  - `400 VALIDATION_ERROR`: Invalid JSON payload.
  - `400 INVALID_CONVERSATION`: `< 2` or `> 50` messages, or items not objects.
  - `400 EMPTY_TEXT`: Blank text in any turn.
  - `400 INVALID_TIMESTAMP`: Malformed ISO-8601 timestamp string.
  - `400 PERSISTENCE_NOT_SUPPORTED`: Client passed `save=true`.
  - `413 TEXT_TOO_LONG`: Any turn exceeds 1,000 characters.
  - `500 CONVERSATION_PROCESSING_ERROR`: Turn processing failure.

---

### 7.11 `GET /api/analyses`
- **Purpose:** Retrieve paginated saved analyses for the authenticated user.
- **Auth:** `@login_required` (HTTP 401).
- **CSRF:** None (GET request).
- **Query Parameters:**
  - `page` (`integer`, optional, default `1`): Must be >= 1.
  - `limit` (`integer`, optional, default `10`): Integer between 1 and 50.
  - `category` (`string`, optional): Whitelisted values: `Normal`, `Insult`, `Threat`, `Hate Speech`, `Toxic/Abusive`, `Toxic/Abusive Language`.
- **Success Response (200):** Ordered by `saved_at DESC, id DESC`.
  ```json
  {
    "success": true,
    "data": {
      "items": [
        {
          "id": 42,
          "text_content": "You are a complete loser, get off the team",
          "category": "Insult",
          "confidence": 0.9142,
          "severity": null,
          "explanation": "Prediction based on high-weight terms: loser",
          "highlighted_terms": ["loser"],
          "safer_rewrite": "I have strong disagreements with this behavior, but I would like to resolve it constructively.",
          "saved_at": "2026-11-11 14:15:00"
        }
      ],
      "pagination": {
        "page": 1,
        "limit": 10,
        "total": 1,
        "total_pages": 1
      }
    }
  }
  ```
- **Error Responses:**
  - `400 INVALID_PAGINATION_PARAMETERS`: `page < 1`, `limit < 1`, or `limit > 50`.
  - `400 INVALID_CATEGORY_FILTER`: Unknown category value.
  - `401 UNAUTHENTICATED`.

---

### 7.12 `DELETE /api/analyses/<int:analysis_id>`
- **Purpose:** Delete a single saved analysis record owned by the authenticated user.
- **Auth:** `@login_required` (HTTP 401).
- **CSRF:** Required (`X-CSRF-Token` header; HTTP 403).
- **URL Parameter:** `analysis_id` (`integer`, required).
- **Success Response (200):**
  ```json
  {
    "success": true,
    "message": "Saved analysis deleted successfully."
  }
  ```
- **Error Responses:**
  - `401 UNAUTHENTICATED`, `403 CSRF_ERROR`.
  - `404 ANALYSIS_NOT_FOUND`: Record does not exist or belongs to another user.

---

### 7.13 `GET /api/dashboard`
- **Purpose:** Retrieve personal dashboard summary metrics and recent activity.
- **Auth:** `@login_required` (HTTP 401).
- **CSRF:** None (GET request).
- **Success Response (200):**
  ```json
  {
    "success": true,
    "data": {
      "total_saved_count": 5,
      "category_breakdown": {
        "Normal": 2,
        "Insult": 2,
        "Threat": 0,
        "Hate Speech": 0,
        "Toxic/Abusive Language": 1
      },
      "recent_activity": [
        {
          "id": 42,
          "text_content": "You are a complete loser, get off the team",
          "category": "Insult",
          "confidence": 0.9142,
          "severity": null,
          "explanation": "Prediction based on terms: loser",
          "highlighted_terms": ["loser"],
          "safer_rewrite": "I have strong disagreements with this behavior, but I would like to resolve it constructively.",
          "saved_at": "2026-11-11 14:15:00"
        }
      ],
      "confidence_disclaimer": "Confidence scores represent uncalibrated decision probabilities output by the model and should not be interpreted as absolute guarantees."
    }
  }
  ```
- **Error Responses:** `401 UNAUTHENTICATED`.

---

### 7.14 `GET /api/user/export`
- **Purpose:** Export all personal profile data, saved analyses, and submitted feedback.
- **Auth:** `@login_required` (HTTP 401).
- **CSRF:** None (GET request).
- **Headers Returned:** `Cache-Control: no-store`.
- **Success Response (200):**
  ```json
  {
    "success": true,
    "data": {
      "profile": {
        "id": 1,
        "username": "alice_smith",
        "email": "alice@example.com",
        "role": "user",
        "created_at": "2026-11-11 14:00:00",
        "updated_at": "2026-11-11 14:00:00"
      },
      "saved_analyses": [
        {
          "id": 42,
          "text_content": "You are a complete loser, get off the team",
          "category": "Insult",
          "confidence": 0.9142,
          "severity": null,
          "explanation": "Prediction based on terms: loser",
          "highlighted_terms": ["loser"],
          "safer_rewrite": "I have strong disagreements with this behavior, but I would like to resolve it constructively.",
          "saved_at": "2026-11-11 14:15:00"
        }
      ],
      "feedback": [
        {
          "id": 1,
          "analysis_id": 42,
          "feedback_type": "general",
          "suggested_category": null,
          "rating": 5,
          "comment": "Very helpful analysis",
          "status": "pending",
          "created_at": "2026-11-11 14:20:00"
        }
      ]
    }
  }
  ```
- **Error Responses:** `401 UNAUTHENTICATED`, `404 USER_NOT_FOUND`.

---

### 7.15 `DELETE /api/user/account`
- **Purpose:** Permanently and atomically delete the authenticated user's account and personal records.
- **Auth:** `@login_required` (HTTP 401).
- **CSRF:** Required (`X-CSRF-Token` header; HTTP 403).
- **Headers Returned:** `Cache-Control: no-store`.
- **Success Response (200):**
  ```json
  {
    "success": true,
    "message": "User account and associated data permanently deleted."
  }
  ```
- **Error Responses:**
  - `400 ACCOUNT_INACTIVE`: Account is deactivated.
  - `401 UNAUTHENTICATED`: Session absent or expired.
  - `403 ADMIN_ACCOUNT_DELETION_NOT_ALLOWED`: Self-deletion prohibited for Administrator role.
  - `403 CSRF_ERROR`: Missing or invalid CSRF token.
  - `404 USER_NOT_FOUND`: Target user record does not exist.
  - `500 TRANSACTION_STATE_CONFLICT`: Conflicting transaction open.
  - `500 DATABASE_LOCKED`: SQLite write lock busy.
  - `500 INTERNAL_ERROR`: Exception during deletion.

---

## 8. Validation Rules, Constraints & Size Limits

| Entity / Route | Constraint | Minimum | Maximum | Failure Code | Status |
| :--- | :--- | :---: | :---: | :--- | :---: |
| Username (`/register`) | Length & Characters | 3 chars | 30 chars | `VALIDATION_ERROR` | 400 |
| Email (`/register`) | Length & Syntax | Valid regex | 120 chars | `VALIDATION_ERROR` | 400 |
| Password (`/register`) | Length & Complexity | 8 chars | No max | `VALIDATION_ERROR` | 400 |
| Text (`/analyze/text`) | Character Count | 1 char | 2,000 chars | `TEXT_TOO_LONG` | 413 |
| File (`/analyze/file`) | File Size | 1 byte | 2 MB | `FILE_TOO_LARGE` | 413 |
| File (`/analyze/file`) | Row Count | 1 row | 500 rows | `ROW_LIMIT_EXCEEDED` | 413 |
| Image (`/analyze/image`) | File Size | 1 byte | 5 MB | `IMAGE_TOO_LARGE` | 413 |
| Image (`/analyze/image`) | Dimensions | 10x10 px | 8000x8000 px | `INVALID_IMAGE_DIMENSIONS` | 422 / 413 |
| Conversation (`/conversation`)| Turn Count | 2 turns | 50 turns | `INVALID_CONVERSATION` | 400 |
| Turn Text (`/conversation`) | Character Count | 1 char | 1,000 chars | `TEXT_TOO_LONG` | 413 |
| Pagination Limit (`/analyses`) | Page Limit | 1 | 50 | `INVALID_PAGINATION_PARAMETERS` | 400 |

---

## 9. File Upload, MIME Verification & OCR Safety

1. **Magic Signature Inspection:** Files uploaded to `/api/analyze/file` undergo binary inspection. Files beginning with executable or archive magic bytes (`MZ`, `ELF`, `PK\x03\x04`, `\x1f\x8b`, `%PDF`, or null byte padding) or containing HTML/script tags are rejected immediately with `415 INVALID_FILE_CONTENT`.
2. **Encoding Enforcement:** Batch files must be valid UTF-8. Non-UTF-8 bytes trigger `422 ENCODING_ERROR`.
3. **Screenshot Lifecycle & Cleanup:**
   - Uploaded screenshots are stored in a temporary file created via `tempfile.NamedTemporaryFile`.
   - After OCR extraction, the `finally` block calls `safe_delete_file(temp_path)`.
   - **Cleanup Failure Behavior:** If `os.unlink()` encounters an `OSError`, the failure is logged as a warning (`logger.warning`) and **suppressed** so the API response is not blocked. Cleanup is best-effort.
   - **Permanent Retention:** Raw image bytes are **never** stored in the database or filesystem.
   - **Audit Trail:** An audit log records `action = 'IMAGE_OCR_EXTRACTED'` with `details = "Image '<filename>' OCR completed with score <ocr_confidence>"`. The image binary and extracted text are excluded from the audit log.

---

## 10. Multi-Turn Conversation Analysis Behavior & Indicator Semantics

1. **Sequential Analysis:** Turns in `POST /api/analyze/conversation` are evaluated sequentially, preserving their original order.
2. **Repeated Harm Indicator:** Algorithmic indicator evaluated as:
   - Requires at least 2 flagged messages (`flagged_count >= 2`).
   - Returns `true` if **(at least two flagged messages are consecutive)** OR **(flagged messages comprise >= 30% of total turns)**.
3. **Objective Pattern Summary:** Cautious, non-judgmental prose generated from flagged category counts.
4. **Non-Punitive Design:** Participants are **never** labeled as `"bully"` or `"victim"`. Speaker labels are treated as unverified metadata.
5. **Zero Persistence:** Conversation sequences are strictly ephemeral and cannot be saved (`save=true` returns `400 PERSISTENCE_NOT_SUPPORTED`).

---

## 11. Analysis History Ownership Isolation & Deletion Cascades

1. **Strict Ownership Scoping:** All database queries in `GET /api/analyses`, `DELETE /api/analyses/<id>`, and `GET /api/dashboard` use `WHERE user_id = ?` bound exclusively to `session["user_id"]`.
2. **Anti-Enumeration 404:** Requesting deletion of an analysis that does not exist or belongs to another user returns `404 ANALYSIS_NOT_FOUND`.
3. **Cascade Rules:** Deleting an analysis cascades to set `analysis_id = NULL` on referencing feedback records via `ON DELETE SET NULL`.

---

## 12. Dashboard Response Semantics & Metric Zero-Filling

1. **Zero-Filled Categories:** `category_breakdown` always returns all 5 canonical keys initialized to `0` if no records exist:
   - `"Normal"`, `"Insult"`, `"Threat"`, `"Hate Speech"`, `"Toxic/Abusive Language"`.
2. **Recent Activity Limit:** Capped at the 5 most recent records, ordered by `saved_at DESC, id DESC`.
3. **Disclaimer Field:** Always includes the canonical `confidence_disclaimer` string.

---

## 13. User Data Export Privacy & Sanitization

1. **Deterministic Ordering:** Exported analyses are ordered by `saved_at DESC, id DESC`. Exported feedback is ordered by `created_at DESC, id DESC`.
2. **Strict Sensitive Data Exclusion:** The export payload excludes `password_hash`, plain-text passwords, session tokens, CSRF tokens, and internal audit logs.
3. **Cache Invalidation:** Returns `Cache-Control: no-store` on all responses.

---

## 14. Account Deletion Atomicity, Session Termination & Anonymized Auditing

1. **Atomic SQLite Transaction:** `DELETE /api/user/account` executes under `BEGIN IMMEDIATE;`.
2. **Order of Operations:**
   - Prunes user feedback (`DELETE FROM feedback WHERE user_id = ?;`).
   - Deletes user row (`DELETE FROM users WHERE id = ?;`), which cascades deletion of saved analyses via `ON DELETE CASCADE`.
   - Records an anonymized audit log entry: `user_id = NULL`, `ip_address = NULL`, `details = "User account closed"`.
   - Commits transaction (`db.commit()`).
3. **Session Cleared Exclusively on Commit:** `session.clear()` is called **only after** database commit succeeds. If deletion fails or is rejected, the user's session is preserved.
4. **Admin Protection:** Self-service Administrator account deletion is rejected with `403 ADMIN_ACCOUNT_DELETION_NOT_ALLOWED`.

---

## 15. Persistence, Ephemeral Workflows & Privacy Boundaries

| Workflow / Endpoint | Stored in Database? | Logged to Audit Log? | Details Logged |
| :--- | :---: | :---: | :--- |
| `POST /api/analyze/text` (`save=false`) | No | No | None |
| `POST /api/analyze/text` (`save=true`) | Yes (`saved_analyses`) | Yes | Category and `saved_id` (message text omitted) |
| `POST /api/analyze/file` | No | Yes | Filename and processed row count |
| `POST /api/analyze/image` | No | Yes | Filename and OCR confidence score |
| `POST /api/analyze/conversation` | No | Yes | Total turns and flagged turn count |
| `GET /api/user/export` | No | No | None |
| `DELETE /api/user/account` | Permanent Deletion | Yes (Anonymized) | `user_id=NULL`, `ip_address=NULL`, generic text |

---

## 16. Category Naming Standards & Backward Compatibility

- **5 Canonical Categories:**
  1. `Normal`
  2. `Insult`
  3. `Threat`
  4. `Hate Speech`
  5. `Toxic/Abusive Language`
- **Backward Compatibility Rollup:**
  - `GET /api/analyses?category=Toxic/Abusive` and `?category=Toxic/Abusive Language` both query both variants.
  - `GET /api/dashboard` rolls up counts from `"Toxic/Abusive"` into `"Toxic/Abusive Language"`.

---

## 17. Confidence Score Interpretations & Limitations Disclaimer

- **Decision Confidence:** Values are **uncalibrated model decision probabilities** output by scikit-learn's `predict_proba()`.
- **No Absolute Guarantees:** Scores must not be presented to end users as absolute statistical certainties.
- **Severity Nullability:** The `severity` field is permanently returned as `null` across all analysis endpoints and history records. It must not be assigned a value until an objective validation rubric is established.

---

## 18. Frontend Integration Guidelines (Vanilla JavaScript / Browser Fetch)

### Standard Fetch Helper Example (Same-Origin)
```javascript
// Generic API request helper for same-origin CyAware deployment
async function apiRequest(endpoint, { method = "GET", data = null, csrfToken = null, isFormData = false } = {}) {
  const headers = {};

  if (!isFormData && data) {
    headers["Content-Type"] = "application/json";
  }

  // Pass CSRF token on state-changing requests if authenticated
  if (csrfToken && ["POST", "PUT", "PATCH", "DELETE"].includes(method.toUpperCase())) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const options = {
    method,
    headers,
    // Same-origin default automatically sends 'session' cookie
    credentials: "same-origin"
  };

  if (data) {
    options.body = isFormData ? data : JSON.stringify(data);
  }

  const response = await fetch(endpoint, options);
  const result = await response.json();

  if (!response.ok || !result.success) {
    // Standard error envelope: { success: false, error: { code, message } }
    const error = new Error(result.error?.message || "An unexpected error occurred");
    error.code = result.error?.code || "HTTP_" + response.status;
    error.status = response.status;
    throw error;
  }

  return result;
}
```

### Usage Examples:
```javascript
// 1. Text Analysis (Authenticated with opt-in save)
try {
  const res = await apiRequest("/api/analyze/text", {
    method: "POST",
    data: { text: "You are an idiot", save: true },
    csrfToken: activeCsrfToken
  });
  console.log("Analysis category:", res.data.category);
  console.log("Saved ID:", res.data.saved_id);
} catch (err) {
  if (err.status === 401) {
    // Redirect to login
  } else {
    console.error(`Analysis failed [${err.code}]:`, err.message);
  }
}

// 2. Image OCR Upload
try {
  const formData = new FormData();
  formData.append("image", fileInput.files[0]);

  const ocrRes = await apiRequest("/api/analyze/image", {
    method: "POST",
    data: formData,
    csrfToken: activeCsrfToken,
    isFormData: true
  });
  // Display text in UI for user to review and edit before analysis
  textArea.value = ocrRes.data.extracted_text;
} catch (err) {
  if (err.code === "OCR_ENGINE_NOT_AVAILABLE") {
    alert("OCR service is currently unavailable on the server.");
  }
}
```

---

## 19. Unimplemented / Out-of-Scope Endpoints

The following features appear in early architectural notes or database tables, but are **NOT IMPLEMENTED** in HTTP routes. The frontend must not attempt to call these:

| Proposed Feature / Route | Related Database Table | Status | Notes |
| :--- | :--- | :---: | :--- |
| `POST /api/feedback` | `feedback` | **NOT IMPLEMENTED** | Table exists, but no user feedback submission route exists. |
| `GET /api/feedback` | `feedback` | **NOT IMPLEMENTED** | No route to list or inspect feedback records. |
| `GET /api/analyses/<int:id>` | `saved_analyses` | **NOT IMPLEMENTED** | Single analysis retrieval is not exposed (use paginated list). |
| `PUT /api/analyses/<int:id>` | `saved_analyses` | **NOT IMPLEMENTED** | Saved analyses are immutable. |
| `PUT /api/auth/password` | `users` | **NOT IMPLEMENTED** | Password reset/update route is not implemented. |
| `GET /api/admin/metrics` | Admin Dashboard | **NOT IMPLEMENTED** | No administrative analytics or user management HTTP routes. |
| `GET /api/model/info` | `model_metadata` | **NOT IMPLEMENTED** | Metadata table exists in DB, but has no public HTTP route. |
| `GET /api/analyses/export/pdf`| PDF Reports | **NOT IMPLEMENTED** | `fpdf2` is in requirements, but no PDF generation route exists. |

