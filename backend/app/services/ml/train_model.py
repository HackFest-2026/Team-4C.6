import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.core.config import settings
from app.services.ml.data_loader import DatasetLoader, DatasetValidationError

logger = logging.getLogger(__name__)

# Mandatory feature definitions for project-level inference
CATEGORICAL_FEATURES = [
    "project_type",
    "project_complexity",
    "frontend_stack",
    "backend_stack",
    "database",
    "hosting_platform",
    "expected_user_band",
    "deadline_pressure",
    "quality_requirement",
    "client_region",
]

NUMERIC_FEATURES = [
    "feature_count",
    "website_pages_or_screens",
    "integration_count",
    "user_role_count",
]

INPUT_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

# Forbidden columns that must NEVER appear in input features (Leakage Prevention)
FORBIDDEN_LEAKAGE_COLUMNS = [
    "target_estimated_cost_inr",
    "target_cost_excluding_contingency_inr",
    "target_labour_cost_inr",
    "total_estimated_effort_hours",
    "estimated_duration_calendar_days",
    "estimated_feature_hours",
    "shared_project_hours",
    "frontend_developer_hours",
    "backend_developer_hours",
    "ui_ux_designer_hours",
    "qa_tester_hours",
    "devops_engineer_hours",
    "project_manager_hours",
    "data_ml_engineer_hours",
    "frontend_hourly_rate_inr",
    "backend_hourly_rate_inr",
    "designer_hourly_rate_inr",
    "qa_hourly_rate_inr",
    "devops_hourly_rate_inr",
    "pm_hourly_rate_inr",
    "data_ml_hourly_rate_inr",
    "tooling_setup_cost_inr",
    "contingency_pct",
    "developer_count_estimate",
    "designer_count_estimate",
    "tester_count_estimate",
    "stack_fit_adjustment_factor",
    "traffic_adjustment_factor",
    "estimated_confidence_pct",
]


def audit_target_leakage(features: List[str], target_name: str) -> None:
    """Verifies that no target, proxy, or post-project measurement leaks into input features."""
    for col in features:
        if col in FORBIDDEN_LEAKAGE_COLUMNS:
            raise ValueError(f"FATAL: Target leakage detected! Column '{col}' is in input features.")
        if col == target_name:
            raise ValueError(f"FATAL: Target '{target_name}' is included as an input feature.")


def calculate_mmre(y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[float, float]:
    """
    Computes MMRE (Mean Magnitude of Relative Error) and MdMRE (Median MRE) safely.
    Handles zero-target cases explicitly by filtering valid positive targets.
    """
    valid_mask = y_true > 0
    if not np.any(valid_mask):
        return 0.0, 0.0
    mre = np.abs(y_true[valid_mask] - y_pred[valid_mask]) / y_true[valid_mask]
    return float(np.mean(mre)), float(np.median(mre))


def calculate_mdmre(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Computes MdMRE (Median Magnitude of Relative Error)."""
    _, mdmre = calculate_mmre(y_true, y_pred)
    return mdmre


def calculate_pred25(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Computes PRED(25), the percentage of predictions whose MRE <= 0.25 (0.0% to 100.0%).
    """
    valid_mask = y_true > 0
    if not np.any(valid_mask):
        return 0.0
    mre = np.abs(y_true[valid_mask] - y_pred[valid_mask]) / y_true[valid_mask]
    return round(float(np.mean(mre <= 0.25) * 100.0), 2)


def build_pipeline() -> Pipeline:
    """Creates reproducible preprocessing and RandomForestRegressor pipeline."""
    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", categorical_transformer, CATEGORICAL_FEATURES),
            ("num", numeric_transformer, NUMERIC_FEATURES),
        ]
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=100,
                    max_depth=16,
                    min_samples_split=4,
                    min_samples_leaf=2,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    return pipeline


def evaluate_edge_cases(
    trained_models: Dict[str, Pipeline], df_edge_cases: pd.DataFrame
) -> Dict[str, Any]:
    """Stress tests trained models against the 20 synthetic edge cases."""
    edge_results = []
    
    # Check what features exist in edge cases
    available_edge_cols = set(df_edge_cases.columns)
    
    for _, row in df_edge_cases.iterrows():
        case_id = row.get("edge_case_id", "UNKNOWN")
        case_name = row.get("scenario_name", "Unknown Scenario")
        why = row.get("why_this_case_matters", "")
        
        # Prepare input row matching model features with defaults if missing
        row_dict = {}
        for col in INPUT_FEATURES:
            if col in available_edge_cols and pd.notnull(row[col]):
                row_dict[col] = row[col]
            else:
                # Provide reasonable schema defaults
                if col in NUMERIC_FEATURES:
                    row_dict[col] = 1 if "count" in col else 5
                elif col == "expected_user_band":
                    row_dict[col] = "1k-10k"
                elif col == "client_region":
                    row_dict[col] = "India"
                elif col == "hosting_platform":
                    row_dict[col] = "AWS"
                else:
                    row_dict[col] = "Standard"

        df_single = pd.DataFrame([row_dict])
        
        preds = {}
        for target, model in trained_models.items():
            try:
                pred_val = float(model.predict(df_single)[0])
                preds[target] = round(pred_val, 2)
            except Exception as e:
                preds[target] = f"Error: {e}"

        edge_results.append({
            "edge_case_id": case_id,
            "scenario_name": case_name,
            "why_this_case_matters": why,
            "predictions": preds,
            "illustrative_target_cost_inr": row.get("illustrative_target_cost_inr", None),
        })

    return {
        "status": "completed",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "edge_case_count": len(edge_results),
        "results": edge_results,
    }


def train_all_models() -> Dict[str, Any]:
    """
    Main training execution function.
    Trains models for target_estimated_cost_inr, total_estimated_effort_hours,
    and estimated_duration_calendar_days.
    """
    artifacts_dir = Path(settings.ARTIFACTS_DIR)
    reports_dir = Path(settings.REPORTS_DIR)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    loader = DatasetLoader()
    sheets, data_report = loader.inspect_and_validate()
    df_projects = sheets["Projects_Training"]
    df_edge = sheets["Edge_Cases"]

    targets_to_train = [
        ("target_estimated_cost_inr", "cost_model.joblib"),
        ("total_estimated_effort_hours", "effort_model.joblib"),
        ("estimated_duration_calendar_days", "duration_model.joblib"),
    ]

    all_metrics: Dict[str, Any] = {
        "provenance": "SIMULATED / SYNTHETIC DATASET (CostPilot_AI_Training_Dataset.xlsx)",
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "input_features": INPUT_FEATURES,
        "models": {},
    }

    trained_pipelines = {}

    for target_col, artifact_filename in targets_to_train:
        logger.info(f"--- Training model for: {target_col} ---")
        audit_target_leakage(INPUT_FEATURES, target_col)

        # Ensure target column exists
        if target_col not in df_projects.columns:
            raise DatasetValidationError(f"Target column '{target_col}' not found in Projects_Training")

        X = df_projects[INPUT_FEATURES].copy()
        y = df_projects[target_col].copy()

        # Split: 80% train, 20% test held-out
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42
        )

        pipeline = build_pipeline()
        pipeline.fit(X_train, y_train)

        # Baseline: DummyRegressor (median)
        dummy = DummyRegressor(strategy="median")
        dummy.fit(X_train, y_train)

        # Test evaluation
        y_pred = pipeline.predict(X_test)
        y_pred_dummy = dummy.predict(X_test)

        test_mae = float(mean_absolute_error(y_test, y_pred))
        test_rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        test_r2 = float(r2_score(y_test, y_pred))
        test_mmre, test_mdmre = calculate_mmre(y_test.values, y_pred)
        test_pred25 = calculate_pred25(y_test.values, y_pred)

        base_mae = float(mean_absolute_error(y_test, y_pred_dummy))
        base_rmse = float(np.sqrt(mean_squared_error(y_test, y_pred_dummy)))
        base_r2 = float(r2_score(y_test, y_pred_dummy))
        base_mmre, base_mdmre = calculate_mmre(y_test.values, y_pred_dummy)
        base_pred25 = calculate_pred25(y_test.values, y_pred_dummy)

        # Save model artifact
        artifact_path = artifacts_dir / artifact_filename
        joblib.dump(pipeline, artifact_path)

        model_info = {
            "artifact_file": artifact_filename,
            "version": "1.0.0",
            "target": target_col,
            "algorithm": "RandomForestRegressor",
            "n_estimators": 100,
            "train_samples": int(len(X_train)),
            "test_samples": int(len(X_test)),
            "metrics": {
                "test_mae": round(test_mae, 2),
                "test_rmse": round(test_rmse, 2),
                "test_r2": round(test_r2, 4),
                "test_mmre": round(test_mmre, 4),
                "test_mdmre": round(test_mdmre, 4),
                "test_pred25": round(test_pred25, 2),
                "baseline_mae": round(base_mae, 2),
                "baseline_rmse": round(base_rmse, 2),
                "baseline_r2": round(base_r2, 4),
                "baseline_mmre": round(base_mmre, 4),
                "baseline_pred25": round(base_pred25, 2),
            },
            "status": "validated_and_saved",
        }

        all_metrics["models"][target_col] = model_info
        trained_pipelines[target_col] = pipeline
        logger.info(f"Target {target_col} R² = {test_r2:.4f}, MAE = {test_mae:.2f} (Baseline MAE = {base_mae:.2f})")

    # Save model metadata in artifacts
    with open(artifacts_dir / "model_metadata.json", "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2)

    # Save metrics report in reports
    with open(reports_dir / "model_metrics.json", "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2)

    # Evaluate stress test edge cases separately
    edge_eval = evaluate_edge_cases(trained_pipelines, df_edge)
    with open(reports_dir / "edge_case_eval.json", "w", encoding="utf-8") as f:
        json.dump(edge_eval, f, indent=2)

    return all_metrics


if __name__ == "__main__":
    print("Starting CostPilot AI Machine Learning Training Pipeline...")
    metrics = train_all_models()
    print("Training COMPLETED SUCCESSFULLY!")
    print(json.dumps(metrics, indent=2))
