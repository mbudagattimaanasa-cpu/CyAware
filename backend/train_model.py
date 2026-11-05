import json
import sys
from pathlib import Path
from backend.app import create_app, database
from backend.app.services.nlp_service import nlp_service

def main():
    print("=" * 60)
    print("CyAware — Training Baseline NLP Classifier (Option A)")
    print("=" * 60)

    app = create_app("development")

    with app.app_context():
        # Ensure database tables exist
        database.init_db()

        # Run training and evaluation pipeline
        metadata = nlp_service.train_and_evaluate()

        # Save metadata record into database
        model_id = metadata["model_id"]
        version = metadata["version"]
        algorithm = metadata["algorithm"]
        metrics_json = json.dumps(metadata["evaluation_metrics"])

        # Deactivate old versions and set this one active
        database.execute_db("UPDATE model_metadata SET is_active = 0 WHERE is_active = 1")
        database.execute_db(
            """INSERT INTO model_metadata (model_id, version, algorithm, metrics_json, is_active, notes)
               VALUES (?, ?, ?, ?, 1, 'Trained on 159,571 Jigsaw records with balanced weights and 80/20 split')
               ON CONFLICT(model_id) DO UPDATE SET
                   version = excluded.version,
                   algorithm = excluded.algorithm,
                   metrics_json = excluded.metrics_json,
                   is_active = 1,
                   trained_at = CURRENT_TIMESTAMP;""",
            (model_id, version, algorithm, metrics_json)
        )

        print("\n" + "=" * 60)
        print("EVALUATION RESULTS SUMMARY (Unseen Test Split)")
        print("=" * 60)
        eval_m = metadata["evaluation_metrics"]
        print(f"Overall Accuracy:  {eval_m['accuracy'] * 100:.2f}%")
        print(f"Macro Precision:   {eval_m['macro_precision']:.4f}")
        print(f"Macro Recall:      {eval_m['macro_recall']:.4f}")
        print(f"Macro F1-Score:    {eval_m['macro_f1']:.4f}")
        print(f"Weighted F1-Score: {eval_m['weighted_f1']:.4f}")

        print("\n--- Class-Wise Metrics ---")
        for cls, m in eval_m["class_wise_metrics"].items():
            print(f"  {cls:25s} | Prec: {m['precision']:.4f} | Rec: {m['recall']:.4f} | F1: {m['f1_score']:.4f} | Support: {m['test_support']}")

        print("\n--- Confusion Matrix ---")
        classes = metadata["classes"]
        print(f"Classes: {classes}")
        for row in eval_m["confusion_matrix"]:
            print(f"  {row}")
        print("=" * 60)
        print("Model artifact successfully saved and registered in database!")

if __name__ == "__main__":
    main()

