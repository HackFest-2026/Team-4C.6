import pytest
import json
from pathlib import Path
from app.services.ml.train_model import audit_target_leakage, INPUT_FEATURES, calculate_mmre
from app.services.ml.predictor import project_predictor
from app.services.ml.model_registry import model_registry
from app.core.config import settings


def test_target_leakage_audit():
    """Mandatory test 27: Verify leakage auditor rejects target and derived fields."""
    # Target column must be rejected
    with pytest.raises(ValueError, match="Target leakage detected"):
        audit_target_leakage(["feature_count", "target_estimated_cost_inr"], "target_estimated_cost_inr")

    # Post-project rate columns must be rejected
    with pytest.raises(ValueError, match="Target leakage detected"):
        audit_target_leakage(["feature_count", "frontend_hourly_rate_inr"], "target_estimated_cost_inr")

    # Effort output column must be rejected when predicting cost
    with pytest.raises(ValueError, match="Target leakage detected"):
        audit_target_leakage(["feature_count", "total_estimated_effort_hours"], "target_estimated_cost_inr")

    # Valid inputs should pass without error
    audit_target_leakage(INPUT_FEATURES, "target_estimated_cost_inr")


def test_unseen_categorical_values_handled_safely():
    """Mandatory test 18: Unseen categorical values should be gracefully ignored by OneHotEncoder."""
    weird_input = {
        "project_type": "Quantum_Blockchain_Metaverse_App",  # Unseen category!
        "project_complexity": "Ultra_Extreme",               # Unseen category!
        "frontend_stack": "COBOL_Web_Assembly",              # Unseen category!
        "backend_stack": "Fortran_90",                       # Unseen category!
        "database": "PunchCardsDB",                          # Unseen category!
        "hosting_platform": "SpaceX_Satellite",              # Unseen category!
        "expected_user_band": "100B+",                       # Unseen category!
        "deadline_pressure": "WarpSpeed",                    # Unseen category!
        "quality_requirement": "NASA_Grade",                 # Unseen category!
        "client_region": "Mars_Colony",                      # Unseen category!
        "feature_count": 5,
        "website_pages_or_screens": 10,
        "integration_count": 2,
        "user_role_count": 3,
    }
    result = project_predictor.predict_project(weird_input)
    assert result["is_ml_prediction"] is True
    # Values must be positive numbers despite unseen categories
    assert result["predictions"]["estimated_cost_inr"] > 0
    assert result["predictions"]["estimated_effort_hours"] > 0
    assert result["predictions"]["estimated_duration_calendar_days"] > 0


def test_model_metrics_report_held_out_evaluation():
    """Mandatory test 29: Model metrics must exist and beat naive baseline."""
    metrics_path = Path(settings.REPORTS_DIR) / "model_metrics.json"
    assert metrics_path.exists(), "model_metrics.json not found in reports/"

    with open(metrics_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cost_m = data["models"]["target_estimated_cost_inr"]
    effort_m = data["models"]["total_estimated_effort_hours"]

    # Must have evaluated on held-out test data
    assert cost_m["test_samples"] == 500
    assert cost_m["train_samples"] == 2000

    # Model R² should comfortably beat baseline R²
    assert cost_m["metrics"]["test_r2"] > cost_m["metrics"]["baseline_r2"]
    assert effort_m["metrics"]["test_r2"] > effort_m["metrics"]["baseline_r2"]

    # Model MAE must be substantially lower than baseline MAE
    assert cost_m["metrics"]["test_mae"] < cost_m["metrics"]["baseline_mae"]
    assert effort_m["metrics"]["test_mae"] < effort_m["metrics"]["baseline_mae"]


def test_mmre_safe_zero_handling():
    """Verify MMRE computation safely handles zeros and edge cases."""
    import numpy as np
    y_true = np.array([100.0, 200.0, 0.0])
    y_pred = np.array([110.0, 180.0, 50.0])
    mmre, mdmre = calculate_mmre(y_true, y_pred)
    assert mmre > 0.0
    assert not np.isnan(mmre)
    assert not np.isinf(mmre)
