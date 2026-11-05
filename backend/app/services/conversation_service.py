from datetime import datetime
from typing import List, Dict, Any
from backend.app.services.nlp_service import nlp_service
from backend.app.services.file_service import FileValidationError

MIN_CONVERSATION_MESSAGES = 2
MAX_CONVERSATION_MESSAGES = 50
MAX_MESSAGE_LENGTH = 1000


def validate_iso8601_timestamp(ts: str) -> bool:
    """Validate that timestamp string conforms to ISO-8601 standard."""
    if not isinstance(ts, str):
        return False
    # Support standard trailing Z for UTC
    normalized = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
    try:
        datetime.fromisoformat(normalized)
        return True
    except (ValueError, TypeError):
        return False


def process_conversation_sequence(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze a sequential multi-turn dialogue while strictly preserving input order.
    
    Speaker labels and timestamps are treated as unverified user-supplied metadata.
    Under no circumstances are participants classified or labeled as 'bully' or 'victim'.
    Confidence scores are uncalibrated model decision probabilities.
    """
    if not isinstance(messages, list) or len(messages) < MIN_CONVERSATION_MESSAGES or len(messages) > MAX_CONVERSATION_MESSAGES:
        raise FileValidationError(
            "INVALID_CONVERSATION",
            f"Conversation requires between {MIN_CONVERSATION_MESSAGES} and {MAX_CONVERSATION_MESSAGES} messages.",
            status_code=400
        )

    total_messages = len(messages)
    evaluations = []
    flagged_indices = []
    flagged_categories = set()

    # Process turns preserving exact input order
    for idx, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise FileValidationError(
                "INVALID_CONVERSATION",
                f"Message at index {idx} must be a valid JSON object.",
                status_code=400
            )

        raw_text = msg.get("text")
        if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
            raise FileValidationError(
                "EMPTY_TEXT",
                f"Message at index {idx} has missing or empty text.",
                status_code=400
            )

        trimmed_text = raw_text.strip()
        if len(trimmed_text) > MAX_MESSAGE_LENGTH:
            raise FileValidationError(
                "TEXT_TOO_LONG",
                f"Message at index {idx} exceeds maximum limit of {MAX_MESSAGE_LENGTH} characters.",
                status_code=413
            )

        # Unverified user-supplied speaker label
        speaker = str(msg.get("speaker", "Unknown")).strip() or "Unknown"
        if len(speaker) > 100:
            speaker = speaker[:100]

        # Validate timestamp if provided
        timestamp = msg.get("timestamp")
        if timestamp is not None:
            if not validate_iso8601_timestamp(str(timestamp)):
                raise FileValidationError(
                    "INVALID_TIMESTAMP",
                    f"Message at index {idx} contains an invalid ISO-8601 timestamp '{timestamp}'.",
                    status_code=400
                )

        # Perform NLP classification
        prediction = nlp_service.predict(trimmed_text)
        cat = prediction["category"]
        conf = prediction["confidence"]

        if cat != "Normal":
            flagged_indices.append(idx)
            flagged_categories.add(cat)

        eval_item = {
            "index": idx,
            "speaker": speaker,
            "category": cat,
            "confidence": conf,
            "highlighted_terms": prediction["highlighted_terms"]
        }
        if timestamp:
            eval_item["timestamp"] = timestamp

        evaluations.append(eval_item)

    flagged_count = len(flagged_indices)

    # Algorithmic calculation of repeated_harm_indicator:
    # Requires at least 2 flagged messages.
    # Set to True if (at least 2 are consecutive) OR (flagged_count / total_messages >= 0.30).
    repeated_harm_indicator = False
    if flagged_count >= 2:
        has_consecutive = any(flagged_indices[i + 1] == flagged_indices[i] + 1 for i in range(len(flagged_indices) - 1))
        has_high_ratio = (flagged_count / total_messages) >= 0.30
        repeated_harm_indicator = bool(has_consecutive or has_high_ratio)

    # Construct objective, cautious pattern summary
    if flagged_count == 0:
        pattern_summary = (
            "No hostile or abusive language was detected across the conversation turns. "
            "Communication appears civil and constructive."
        )
    elif flagged_count == 1:
        pattern_summary = (
            f"1 of {total_messages} messages was flagged with hostile tone. "
            "This isolated remark warrants human review but does not constitute repeated harm or definitive proof of harmful behavior."
        )
    else:
        cats_str = ", ".join(sorted(flagged_categories))
        pattern_summary = (
            f"{flagged_count} of {total_messages} messages were flagged with harmful tone ({cats_str}). "
            f"Observed pattern indicates {'potentially persistent' if repeated_harm_indicator else 'intermittent'} "
            "hostile communication. This serves as an indicator to aid human review and does not constitute definitive proof of harmful behavior."
        )

    return {
        "conversation_indicators": {
            "total_messages": total_messages,
            "flagged_message_count": flagged_count,
            "repeated_harm_indicator": repeated_harm_indicator,
            "pattern_summary": pattern_summary
        },
        "message_evaluations": evaluations
    }

