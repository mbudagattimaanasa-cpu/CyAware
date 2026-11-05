from pathlib import Path
import pytest
from backend.app.services.nlp_service import NLPModelService, CATEGORIES
from backend.app.database import query_db

MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "models"


@pytest.fixture(scope="module")
def loaded_nlp_service():
    """Module-level fixture to load the trained model once for tests."""
    service = NLPModelService(model_dir=MODEL_DIR)
    loaded = service.load_model()
    assert loaded is True, "Failed to load trained model artifacts."
    return service


def test_model_artifacts_exist():
    """Verify serialized model artifacts and metadata exist on disk."""
    vec_path = MODEL_DIR / "tfidf_vectorizer.joblib"
    clf_path = MODEL_DIR / "classifier_model.joblib"
    meta_path = MODEL_DIR / "model_metadata.json"

    assert vec_path.exists(), "TF-IDF vectorizer artifact missing."
    assert clf_path.exists(), "Classifier model artifact missing."
    assert meta_path.exists(), "Model metadata JSON missing."


def test_model_metadata_integrity(loaded_nlp_service):
    """Verify evaluation metadata contains all 5 classes and genuine metrics."""
    meta = loaded_nlp_service.metadata
    assert meta is not None
    assert meta["model_id"] == "model_v1_tfidf_lr"
    assert meta["version"] == "1.0.0"

    classes = meta["classes"]
    for cat in CATEGORIES:
        assert cat in classes, f"Category '{cat}' missing from model classes."

    metrics = meta["evaluation_metrics"]
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert 0.0 <= metrics["macro_f1"] <= 1.0
    assert len(metrics["confusion_matrix"]) == 5
    assert len(metrics["class_wise_metrics"]) == 5


def test_predict_normal_message(loaded_nlp_service):
    """Verify clean, polite text is predicted as Normal."""
    text = "Thank you so much for the helpful explanation and collaboration today."
    res = loaded_nlp_service.predict(text)
    assert res["category"] == "Normal"
    assert 0.0 <= res["confidence"] <= 1.0
    assert res["safer_rewrite"] is None
    assert "civil" in res["safety_recommendation"].lower() or "constructive" in res["safety_recommendation"].lower()


def test_predict_insult(loaded_nlp_service):
    """Verify targeted demeaning text is flagged as Insult with highlighted terms."""
    text = "You are completely stupid, a total loser and an idiot."
    res = loaded_nlp_service.predict(text)
    assert res["category"] == "Insult"
    assert 0.0 <= res["confidence"] <= 1.0
    assert len(res["highlighted_terms"]) > 0
    assert res["safer_rewrite"] is not None


def test_predict_threat(loaded_nlp_service):
    """Verify direct violent intimidation is flagged as Threat."""
    text = "I will find you and kill you tonight."
    res = loaded_nlp_service.predict(text)
    assert res["category"] == "Threat"
    assert 0.0 <= res["confidence"] <= 1.0
    assert "safety" in res["safety_recommendation"].lower() or "authorities" in res["safety_recommendation"].lower()


def test_predict_hate_speech(loaded_nlp_service):
    """Verify group-targeted discriminatory attacks are flagged as Hate Speech."""
    text = "I hate all muslims and jews, get out of our country"
    res = loaded_nlp_service.predict(text)
    assert res["category"] == "Hate Speech"
    assert 0.0 <= res["confidence"] <= 1.0
    assert "discriminatory" in res["explanation"].lower() or "identity" in res["explanation"].lower()
    assert res["safer_rewrite"] is not None


def test_predict_toxic_abusive_language(loaded_nlp_service):
    """Verify general obscenity and vulgar hostility are flagged as Toxic/Abusive Language."""
    text = "damn this fucking garbage article sucks"
    res = loaded_nlp_service.predict(text)
    assert res["category"] == "Toxic/Abusive Language"
    assert 0.0 <= res["confidence"] <= 1.0
    assert "abusive" in res["explanation"].lower() or "toxic" in res["explanation"].lower()
    assert res["safer_rewrite"] is not None


def test_probabilities_sum_to_one(loaded_nlp_service):
    """Verify that output probability distribution across all 5 classes sums to ~1.0."""
    text = "Why did you delete my post?"
    res = loaded_nlp_service.predict(text)
    probas = res["probabilities"]
    assert len(probas) == 5
    total = sum(probas.values())
    assert abs(total - 1.0) < 0.01


def test_predict_empty_or_whitespace(loaded_nlp_service):
    """Verify empty or whitespace-only inputs are rejected with ValueError."""
    with pytest.raises(ValueError):
        loaded_nlp_service.predict("")

    with pytest.raises(ValueError):
        loaded_nlp_service.predict("   \n\t  ")


def test_predict_invalid_types(loaded_nlp_service):
    """Verify non-string inputs raise ValueError."""
    with pytest.raises(ValueError):
        loaded_nlp_service.predict(12345)

    with pytest.raises(ValueError):
        loaded_nlp_service.predict(None)


def test_model_registration_in_database(app):
    """Verify active model record is registered in SQLite model_metadata table."""
    with app.app_context():
        # First ensure train_model was registered or re-register in test DB
        meta_file = MODEL_DIR / "model_metadata.json"
        if meta_file.exists():
            import json
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            query_db(
                """INSERT OR REPLACE INTO model_metadata (model_id, version, algorithm, metrics_json, is_active)
                   VALUES (?, ?, ?, ?, 1)""",
                (data["model_id"], data["version"], data["algorithm"], json.dumps(data["evaluation_metrics"]))
            )

        active = query_db(
            "SELECT * FROM model_metadata WHERE is_active = 1",
            one=True
        )
        assert active is not None
        assert active["model_id"] == "model_v1_tfidf_lr"

