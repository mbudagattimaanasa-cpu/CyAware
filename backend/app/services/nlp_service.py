import os
import json
import re
from pathlib import Path
from datetime import datetime, timezone
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, precision_recall_fscore_support

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL_DIR = BASE_DIR / "data" / "models"
DEFAULT_RAW_DATA = BASE_DIR / "data" / "raw" / "jigsaw_train.csv"

# The 5 canonical categories agreed for CyAware
CATEGORIES = [
    "Normal",
    "Insult",
    "Threat",
    "Hate Speech",
    "Toxic/Abusive Language",
]

# Safety recommendations per category
SAFETY_RECOMMENDATIONS = {
    "Normal": "No action needed. The conversation appears civil and constructive.",
    "Insult": "Take a moment before responding. Avoid escalating with counter-insults and consider setting conversation boundaries.",
    "Threat": "Safety priority: Do not engage. Document the interaction and consider reporting to appropriate safety or platform authorities.",
    "Hate Speech": "Do not amplify or internalize discriminatory language. Report the message to platform moderators or institutional channels.",
    "Toxic/Abusive Language": "Disengage from hostile exchanges. Stepping away or pausing the conversation helps prevent toxic escalation.",
}

# Template-based respectful rewrites for abusive/toxic/insulting inputs
REWRITE_TEMPLATES = {
    "Insult": "I have strong disagreements with this behavior, but I would like to resolve it constructively.",
    "Toxic/Abusive Language": "I feel frustrated with this situation. Let us address the specific issue directly.",
    "Threat": "I am deeply upset and need this issue resolved immediately through proper channels.",
    "Hate Speech": "I disagree with this perspective and ask that we keep our conversation respectful of everyone.",
}


def clean_text(text: str) -> str:
    """Preprocess text by lowercasing and normalizing whitespace while preserving words and punctuation."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def map_jigsaw_categories(df: pd.DataFrame) -> pd.Series:
    """Apply verified priority hierarchy mapping to Jigsaw multi-label columns."""
    def assign_row(row):
        if row["threat"] == 1:
            return "Threat"
        if row["identity_hate"] == 1:
            return "Hate Speech"
        if row["insult"] == 1:
            return "Insult"
        if row["toxic"] == 1 or row["severe_toxic"] == 1 or row["obscene"] == 1:
            return "Toxic/Abusive Language"
        return "Normal"

    return df.apply(assign_row, axis=1)


class NLPModelService:
    """Service for managing model training, inference, confidence, and keyword explanations."""

    def __init__(self, model_dir: Path = None):
        self.model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
        self.vectorizer = None
        self.classifier = None
        self.metadata = None
        self.is_loaded = False

    def load_model(self) -> bool:
        """Load the serialized TF-IDF vectorizer and classifier from disk."""
        vec_path = self.model_dir / "tfidf_vectorizer.joblib"
        clf_path = self.model_dir / "classifier_model.joblib"
        meta_path = self.model_dir / "model_metadata.json"

        if not vec_path.exists() or not clf_path.exists():
            self.is_loaded = False
            return False

        self.vectorizer = joblib.load(vec_path)
        self.classifier = joblib.load(clf_path)

        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)

        self.is_loaded = True
        return True

    def train_and_evaluate(
        self,
        dataset_path: Path = None,
        output_dir: Path = None,
        test_size: float = 0.20,
        random_state: int = 42,
    ) -> dict:
        """Train TF-IDF + Logistic Regression baseline on the full dataset with balanced weights and 80/20 stratified split."""
        data_path = Path(dataset_path) if dataset_path else DEFAULT_RAW_DATA
        out_dir = Path(output_dir) if output_dir else self.model_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        if not data_path.exists():
            raise FileNotFoundError(f"Dataset not found at {data_path}")

        print(f"Loading raw dataset from {data_path}...")
        df = pd.read_csv(data_path)

        print("Applying 5-category priority mapping...")
        y = map_jigsaw_categories(df)
        X = df["comment_text"].fillna("").apply(clean_text)

        # 1. Stratified 80/20 train/test split to prevent data leakage
        print(f"Splitting data (test_size={test_size}, stratify=y, random_state={random_state})...")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )

        # 2. Fit TF-IDF STRICTLY on training split
        print("Fitting TF-IDF Vectorizer on X_train...")
        vectorizer = TfidfVectorizer(
            max_features=25000,
            ngram_range=(1, 2),
            sublinear_tf=True,
            stop_words="english",
        )
        X_train_vec = vectorizer.fit_transform(X_train)
        X_test_vec = vectorizer.transform(X_test)

        # 3. Fit Logistic Regression with balanced class weighting
        print("Training Logistic Regression (class_weight='balanced', max_iter=1000)...")
        classifier = LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=random_state,
            solver="lbfgs",
        )
        classifier.fit(X_train_vec, y_train)

        # 4. Evaluate honestly on unseen X_test
        print("Evaluating on test split...")
        y_pred = classifier.predict(X_test_vec)
        y_proba = classifier.predict_proba(X_test_vec)

        accuracy = float(accuracy_score(y_test, y_pred))
        macro_prec, macro_rec, macro_f1, _ = precision_recall_fscore_support(
            y_test, y_pred, average="macro", zero_division=0
        )
        weighted_prec, weighted_rec, weighted_f1, _ = precision_recall_fscore_support(
            y_test, y_pred, average="weighted", zero_division=0
        )

        class_labels = list(classifier.classes_)
        prec_per_class, rec_per_class, f1_per_class, supp_per_class = precision_recall_fscore_support(
            y_test, y_pred, labels=class_labels, zero_division=0
        )

        class_metrics = {}
        for idx, lbl in enumerate(class_labels):
            class_metrics[lbl] = {
                "precision": round(float(prec_per_class[idx]), 4),
                "recall": round(float(rec_per_class[idx]), 4),
                "f1_score": round(float(f1_per_class[idx]), 4),
                "test_support": int(supp_per_class[idx]),
            }

        cm = confusion_matrix(y_test, y_pred, labels=class_labels).tolist()

        metadata = {
            "model_id": "model_v1_tfidf_lr",
            "version": "1.0.0",
            "algorithm": "TF-IDF + Logistic Regression (Balanced)",
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_samples": int(len(X_train)),
            "test_samples": int(len(X_test)),
            "classes": class_labels,
            "evaluation_metrics": {
                "accuracy": round(accuracy, 4),
                "macro_precision": round(float(macro_prec), 4),
                "macro_recall": round(float(macro_rec), 4),
                "macro_f1": round(float(macro_f1), 4),
                "weighted_f1": round(float(weighted_f1), 4),
                "class_wise_metrics": class_metrics,
                "confusion_matrix": cm,
            },
        }

        # 5. Save serialized artifacts
        print(f"Saving model artifacts to {out_dir}...")
        joblib.dump(vectorizer, out_dir / "tfidf_vectorizer.joblib")
        joblib.dump(classifier, out_dir / "classifier_model.joblib")
        with open(out_dir / "model_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        self.vectorizer = vectorizer
        self.classifier = classifier
        self.metadata = metadata
        self.is_loaded = True

        print("Model training and evaluation successfully completed!")
        return metadata

    def extract_salient_terms(self, text: str, predicted_category: str, top_n: int = 4) -> list:
        """Extract top predictive features/words from the input that influenced the prediction."""
        if not self.is_loaded or predicted_category == "Normal":
            return []

        try:
            vec_words = self.vectorizer.get_feature_names_out()
            cat_idx = list(self.classifier.classes_).index(predicted_category)
            coefficients = self.classifier.coef_[cat_idx]

            # Tokenize cleaned words in text
            words = set(re.findall(r"\b[a-zA-Z]{3,}\b", clean_text(text)))
            word_scores = []
            for w in words:
                if w in self.vectorizer.vocabulary_:
                    feat_idx = self.vectorizer.vocabulary_[w]
                    score = coefficients[feat_idx]
                    if score > 0:
                        word_scores.append((w, score))

            word_scores.sort(key=lambda x: x[1], reverse=True)
            return [w for w, _ in word_scores[:top_n]]
        except Exception:
            return []

    def predict(self, text: str) -> dict:
        """Predict the classification category and honest probability confidence for a given text."""
        if not self.is_loaded:
            if not self.load_model():
                raise RuntimeError("NLP Model has not been trained or loaded yet.")

        if not text or not isinstance(text, str) or not text.strip():
            raise ValueError("Input text must be a non-empty string.")

        cleaned = clean_text(text)
        if not cleaned:
            return {
                "category": "Normal",
                "confidence": 1.0,
                "probabilities": {c: 0.0 for c in self.classifier.classes_},
                "highlighted_terms": [],
                "explanation": "No legible text found to analyze.",
                "safety_recommendation": SAFETY_RECOMMENDATIONS["Normal"],
                "safer_rewrite": None,
            }

        vec = self.vectorizer.transform([cleaned])
        probas = self.classifier.predict_proba(vec)[0]
        classes = list(self.classifier.classes_)

        max_idx = int(np.argmax(probas))
        category = classes[max_idx]
        confidence = round(float(probas[max_idx]), 4)

        probabilities_dict = {
            classes[i]: round(float(probas[i]), 4) for i in range(len(classes))
        }

        # Model-derived salient terms
        highlighted = self.extract_salient_terms(text, category)

        # Contextual explanation
        if category == "Normal":
            explanation = "The message wording does not exhibit significant patterns of cyberbullying or toxic hostility."
        elif category == "Threat":
            explanation = "The message contains indicators associated with threats of physical harm, violence, or severe intimidation."
        elif category == "Hate Speech":
            explanation = "The message contains patterns associated with identity-based hatred or discriminatory hostility."
        elif category == "Insult":
            explanation = "The message contains language characteristic of personal demeanment, contempt, or insults."
        else:
            explanation = "The message contains abusive, obscene, or aggressively toxic language."

        return {
            "category": category,
            "confidence": confidence,
            "probabilities": probabilities_dict,
            "highlighted_terms": highlighted,
            "explanation": explanation,
            "safety_recommendation": SAFETY_RECOMMENDATIONS.get(category, ""),
            "safer_rewrite": REWRITE_TEMPLATES.get(category) if category != "Normal" else None,
        }


# Global singleton instance for application use
nlp_service = NLPModelService()

