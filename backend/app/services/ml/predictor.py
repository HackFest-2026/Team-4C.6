import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from app.services.ml.model_registry import model_registry
from app.services.ml.train_model import INPUT_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES

logger = logging.getLogger(__name__)


class ProjectPredictor:
    """
    Safely executes inference using trained scikit-learn models for:
    - target_estimated_cost_inr
    - total_estimated_effort_hours
    - estimated_duration_calendar_days
    """

    def __init__(self):
        self.registry = model_registry

    def predict_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes prediction with input sanitization, imputation for missing fields,
        and returns predictions for cost, effort, and duration.
        """
        # Map or extract candidate input features
        feature_dict = {}
        for col in INPUT_FEATURES:
            val = project_data.get(col)
            if val is not None and str(val).strip() != "":
                if col in NUMERIC_FEATURES:
                    try:
                        feature_dict[col] = float(val)
                    except (ValueError, TypeError):
                        feature_dict[col] = 1.0 if "count" in col else 5.0
                else:
                    raw_str = str(val).strip()
                    if col == "project_type":
                        from app.core.config import settings
                        raw_str = settings.DOMAIN_ARCHETYPE_MAPPING.get(raw_str, raw_str)
                    feature_dict[col] = raw_str
            else:
                # Defaults
                if col == "project_type":
                    feature_dict[col] = "SaaS Web Application"
                elif col == "project_complexity":
                    feature_dict[col] = "Medium"
                elif col == "frontend_stack":
                    feature_dict[col] = "React"
                elif col == "backend_stack":
                    feature_dict[col] = "Node.js_Express"
                elif col == "database":
                    feature_dict[col] = "PostgreSQL"
                elif col == "hosting_platform":
                    feature_dict[col] = "AWS"
                elif col == "expected_user_band":
                    feature_dict[col] = "1k-10k"
                elif col == "deadline_pressure":
                    feature_dict[col] = "Moderate"
                elif col == "quality_requirement":
                    feature_dict[col] = "Standard"
                elif col == "client_region":
                    feature_dict[col] = "India"
                elif col in NUMERIC_FEATURES:
                    feature_dict[col] = 1.0 if "count" in col else 5.0

        df_input = pd.DataFrame([feature_dict])

        results: Dict[str, Any] = {
            "is_ml_prediction": True,
            "provenance": "SIMULATED_SYNTHETIC_DATA_BENCHMARK",
            "model_version": "1.0.0",
            "predictions": {},
            "warnings": [],
        }

        # 1. Cost model
        cost_model = self.registry.load_model("target_estimated_cost_inr")
        if cost_model is not None:
            try:
                pred_cost = float(cost_model.predict(df_input)[0])
                results["predictions"]["estimated_cost_inr"] = max(0.0, round(pred_cost, 2))
            except Exception as e:
                logger.error(f"Cost prediction failed: {e}")
                results["warnings"].append(f"Cost ML model error: {e}")
        else:
            results["warnings"].append("Cost model not loaded; ML cost unavailable")

        # 2. Effort model
        effort_model = self.registry.load_model("total_estimated_effort_hours")
        if effort_model is not None:
            try:
                pred_effort = float(effort_model.predict(df_input)[0])
                results["predictions"]["estimated_effort_hours"] = max(0.0, round(pred_effort, 2))
            except Exception as e:
                logger.error(f"Effort prediction failed: {e}")
                results["warnings"].append(f"Effort ML model error: {e}")
        else:
            results["warnings"].append("Effort model not loaded; ML effort unavailable")

        # 3. Duration model
        duration_model = self.registry.load_model("estimated_duration_calendar_days")
        if duration_model is not None:
            try:
                pred_duration = float(duration_model.predict(df_input)[0])
                results["predictions"]["estimated_duration_calendar_days"] = max(1.0, round(pred_duration, 1))
            except Exception as e:
                logger.error(f"Duration prediction failed: {e}")
                results["warnings"].append(f"Duration ML model error: {e}")
        else:
            results["warnings"].append("Duration model not loaded; ML duration unavailable")

        return results


project_predictor = ProjectPredictor()
