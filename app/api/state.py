import os

import xgboost as xgb

from .schemas import AnalysisStoreRecord, CsvProcessingSummary

TRADER_TYPES = {
    0: "calm_trader",
    1: "loss_averse_trader",
    2: "overtrader",
    3: "revenge_trader",
}

uploaded_files: dict[str, bytes] = {}
analysis_results: dict[str, AnalysisStoreRecord] = {}
csv_processing_summaries: dict[str, CsvProcessingSummary] = {}
model: xgb.XGBClassifier | None = None


def load_model() -> None:
    global model
    try:
        # Try loading v2 model first, then fall back to classifier.json
        model_candidates = [
            "trader_classifier2.json",
            "trader_classifier95.json",
            "trader_classifier.json",
        ]
        
        base_path = os.path.join(os.path.dirname(__file__), "../mltraining")
        
        for model_filename in model_candidates:
            model_path = os.path.join(base_path, model_filename)
            if os.path.exists(model_path):
                try:
                    loaded_model = xgb.XGBClassifier()
                    loaded_model.load_model(str(model_path))
                    model = loaded_model
                    print(f"✓ Model loaded successfully from {model_filename}")
                    return
                except Exception as load_exc:
                    print(f"Failed to load {model_filename}: {load_exc}")
                    continue
        
        print("⚠ No suitable model found in mltraining directory")
    except Exception as exc:
        print(f"Error loading model: {exc}")
