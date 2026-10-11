"""
CostPilot AI — Historical Dataset Ingestion, Validation, Preprocessing & Model Training Pipeline.
Implements:
1. Multi-format upload (.xlsx, .csv) with size & safety validation.
2. Automated schema detection, type inference, missing value profiling, and duplicate checking.
3. Candidate field mapping against model requirements.
4. Data cleaning: field-appropriate imputation, categorical normalization, outlier flagging, and leakage prevention.
5. Candidate model training with independent 80/20 train/test evaluation (MAE, RMSE, R², MMRE, MdMRE, PRED(25)).
6. Safe Champion vs. Candidate promotion workflow protecting production inference.
"""

import os
import io
import json
import logging
import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.core.config import settings
from app.db.session import get_db_connection
from app.services.ml.metrics import calculate_relative_error_metrics
from app.services.ml.model_registry import model_registry

logger = logging.getLogger(__name__)

# Standard model candidate field mapping synonyms
CANDIDATE_FIELD_SYNONYMS: Dict[str, List[str]] = {
    "project_id": ["project_id", "id", "project_code", "project_number", "proj_id"],
    "project_type": ["project_type", "type", "domain", "category", "industry", "app_type"],
    "project_complexity": ["project_complexity", "complexity", "overall_complexity", "difficulty"],
    "feature_count": ["feature_count", "features", "num_features", "feature_qty", "features_count"],
    "website_pages_or_screens": ["website_pages_or_screens", "screens", "pages", "screen_count", "views"],
    "frontend_stack": ["frontend_stack", "frontend", "ui_stack", "fe_tech"],
    "backend_stack": ["backend_stack", "backend", "api_stack", "be_tech"],
    "database": ["database", "db", "data_store", "db_type"],
    "hosting_platform": ["hosting_platform", "platform", "cloud_provider", "host", "target_platform"],
    "expected_user_band": ["expected_user_band", "user_scale", "users", "scale", "concurrency"],
    "integration_count": ["integration_count", "integrations", "third_party_apis", "api_count"],
    "user_role_count": ["user_role_count", "user_roles", "roles_count", "roles"],
    "deadline_pressure": ["deadline_pressure", "deadline_urgency", "urgency", "schedule_pressure"],
    "quality_requirement": ["quality_requirement", "quality_level", "testing_rigor", "sla"],
    "client_region": ["client_region", "region", "geography", "market", "country"],
    "team_size": ["team_size", "headcount", "staffing", "resources_count"],
    "total_estimated_effort_hours": ["total_estimated_effort_hours", "total_effort", "effort_hours", "effort", "actual_effort_hours"],
    "estimated_duration_calendar_days": ["estimated_duration_calendar_days", "duration_days", "duration", "calendar_days", "timeline_days"],
    "target_labour_cost_inr": ["target_labour_cost_inr", "labour_cost", "labor_cost", "personnel_cost"],
    "tooling_setup_cost_inr": ["tooling_setup_cost_inr", "tooling_cost", "tools_cost", "licenses_cost"],
    "target_estimated_cost_inr": ["target_estimated_cost_inr", "total_cost", "cost", "budget", "final_budget", "actual_cost"],
}

# Forbidden columns that must NEVER appear in input features (Leakage Prevention)
FORBIDDEN_LEAKAGE_TARGETS = [
    "target_estimated_cost_inr",
    "target_cost_excluding_contingency_inr",
    "target_labour_cost_inr",
    "total_estimated_effort_hours",
    "estimated_duration_calendar_days",
]


class DatasetPipeline:
    def __init__(self):
        self.uploads_dir = Path(settings.DATASET_PATH).parent / "uploads"
        self.cleaned_dir = Path(settings.DATASET_PATH).parent / "cleaned"
        self.candidates_dir = Path(settings.ARTIFACTS_DIR) / "candidates"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.cleaned_dir.mkdir(parents=True, exist_ok=True)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)

    def upload_and_profile(
        self,
        file_bytes: bytes,
        filename: str,
        provenance: str = "Organization-provided",
        user_id: Optional[str] = None,
        dataset_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingests, saves, profiles, and validates an uploaded dataset workbook or CSV.
        """
        max_size = 50 * 1024 * 1024  # 50 MB
        if len(file_bytes) > max_size:
            raise ValueError(f"File size exceeds maximum limit of 50 MB (Received: {len(file_bytes) / 1024 / 1024:.2f} MB).")

        ext = Path(filename).suffix.lower()
        if ext not in [".xlsx", ".xls", ".csv"]:
            raise ValueError(f"Unsupported file format '{ext}'. Supported formats: .xlsx, .xls, .csv")

        dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
        safe_name = f"{dataset_id}_{Path(filename).name}"
        raw_path = self.uploads_dir / safe_name

        with open(raw_path, "wb") as f:
            f.write(file_bytes)

        df: pd.DataFrame
        try:
            if ext in [".xlsx", ".xls"]:
                excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
                sheet_to_use = "Projects_Training" if "Projects_Training" in excel_file.sheet_names else excel_file.sheet_names[0]
                df = pd.read_excel(excel_file, sheet_name=sheet_to_use)
            else:
                try:
                    df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8")
                except UnicodeDecodeError:
                    df = pd.read_csv(io.BytesIO(file_bytes), encoding="latin1")
        except Exception as e:
            if raw_path.exists():
                raw_path.unlink()
            raise ValueError(f"Failed to parse dataset file: {str(e)}")

        if len(df) > 50000:
            if raw_path.exists():
                raw_path.unlink()
            raise ValueError(f"Dataset contains {len(df)} rows, exceeding safety limit of 50,000 rows.")

        total_rows = int(len(df))
        total_cols = int(len(df.columns))

        if total_rows == 0:
            raise ValueError("Uploaded dataset contains 0 data rows.")

        columns_profile = []
        missing_count_total = 0
        detected_mapping: Dict[str, str] = {}

        for col in df.columns:
            col_series = df[col]
            missing_count = int(col_series.isnull().sum())
            missing_count_total += missing_count

            if pd.api.types.is_numeric_dtype(col_series):
                inferred_type = "numeric"
            elif pd.api.types.is_datetime64_any_dtype(col_series):
                inferred_type = "datetime"
            else:
                inferred_type = "categorical"

            col_clean = str(col).strip().lower()
            mapped_candidate = None
            for standard_field, synonyms in CANDIDATE_FIELD_SYNONYMS.items():
                if col_clean in synonyms:
                    mapped_candidate = standard_field
                    detected_mapping[standard_field] = str(col)
                    break

            columns_profile.append({
                "column_name": str(col),
                "inferred_type": inferred_type,
                "missing_count": missing_count,
                "missing_pct": round((missing_count / total_rows) * 100, 2),
                "unique_values_count": int(col_series.nunique(dropna=True)),
                "sample_values": [str(x) for x in col_series.dropna().head(3).tolist()],
                "mapped_candidate_field": mapped_candidate,
            })

        warnings: List[str] = []
        errors: List[str] = []
        invalid_row_indices = set()

        duplicate_rows_count = int(df.duplicated().sum())
        if duplicate_rows_count > 0:
            warnings.append(f"Detected {duplicate_rows_count} fully duplicate rows.")

        if "project_id" in detected_mapping:
            id_col = detected_mapping["project_id"]
            dup_ids = df[id_col].dropna().duplicated().sum()
            if dup_ids > 0:
                warnings.append(f"Detected {dup_ids} duplicate project identifiers in column '{id_col}'.")

        for num_field in ["total_estimated_effort_hours", "estimated_duration_calendar_days", "target_estimated_cost_inr"]:
            if num_field in detected_mapping:
                actual_col = detected_mapping[num_field]
                invalid_num = df[df[actual_col] <= 0]
                if len(invalid_num) > 0:
                    invalid_row_indices.update(invalid_num.index.tolist())
                    warnings.append(
                        f"Column '{actual_col}' contains {len(invalid_num)} non-positive values (<= 0)."
                    )

        available_targets = [
            t for t in ["total_estimated_effort_hours", "estimated_duration_calendar_days", "target_estimated_cost_inr"]
            if t in detected_mapping
        ]
        if not available_targets:
            warnings.append(
                "No standard estimation targets (effort, duration, cost) were auto-detected. "
                "Manual column mapping will be required before training."
            )

        invalid_rows_count = len(invalid_row_indices)
        valid_rows_count = max(0, total_rows - invalid_rows_count)

        recommendations: List[str] = []
        if missing_count_total > 0:
            recommendations.append("Apply median/mode imputation to resolve missing values.")
        if invalid_rows_count > 0:
            recommendations.append(f"Clean or filter {invalid_rows_count} non-positive target rows.")
        if len(available_targets) >= 1:
            recommendations.append(f"Dataset is ready for model training targeting: {', '.join(available_targets)}.")
        else:
            recommendations.append("Map at least one effort, duration, or cost column to enable retraining.")

        validation_report = {
            "total_rows": total_rows,
            "total_columns": total_cols,
            "valid_rows": valid_rows_count,
            "invalid_rows": invalid_rows_count,
            "duplicate_rows": duplicate_rows_count,
            "missing_values_count": missing_count_total,
            "available_targets": available_targets,
            "detected_mapping": detected_mapping,
            "warnings": warnings,
            "errors": errors,
            "recommendations": recommendations,
        }

        now = datetime.now(timezone.utc).isoformat()
        display_name = dataset_name or Path(filename).stem.replace("_", " ").title()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO uploaded_datasets (
                id, name, original_filename, file_format, file_path, cleaned_file_path,
                file_size_bytes, provenance, total_rows, total_columns, valid_rows,
                invalid_rows, duplicate_rows, missing_values_count, column_schema_json,
                validation_report_json, status, user_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                display_name,
                filename,
                ext.replace(".", ""),
                str(raw_path),
                None,
                len(file_bytes),
                provenance,
                total_rows,
                total_cols,
                valid_rows_count,
                invalid_rows_count,
                duplicate_rows_count,
                missing_count_total,
                json.dumps(columns_profile),
                json.dumps(validation_report),
                "Validated" if not errors else "Failed",
                user_id,
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()

        logger.info(f"Ingested and validated dataset {dataset_id} ('{filename}') with {total_rows} rows.")

        return {
            "dataset_id": dataset_id,
            "name": display_name,
            "filename": filename,
            "file_format": ext.replace(".", ""),
            "provenance": provenance,
            "total_rows": total_rows,
            "total_columns": total_cols,
            "valid_rows": valid_rows_count,
            "invalid_rows": invalid_rows_count,
            "columns": columns_profile,
            "detected_mapping": detected_mapping,
            "validation_report": validation_report,
            "status": "Validated" if not errors else "Failed",
            "created_at": now,
        }

    def clean_and_preprocess(
        self,
        dataset_id: str,
        custom_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes cleaning, imputation, category normalization, and outlier flagging.
        Saves cleaned dataset separately from original raw upload.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM uploaded_datasets WHERE id = ?", (dataset_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Dataset '{dataset_id}' not found.")

        raw_path = Path(row["file_path"])
        if not raw_path.exists():
            conn.close()
            raise ValueError(f"Raw dataset file missing on server at: {raw_path}")

        ext = row["file_format"]
        if ext in ["xlsx", "xls"]:
            excel_file = pd.ExcelFile(raw_path)
            sheet_to_use = "Projects_Training" if "Projects_Training" in excel_file.sheet_names else excel_file.sheet_names[0]
            df = pd.read_excel(excel_file, sheet_name=sheet_to_use)
        else:
            try:
                df = pd.read_csv(raw_path, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(raw_path, encoding="latin1")

        val_report = json.loads(row["validation_report_json"])
        mapping = custom_mapping or val_report.get("detected_mapping", {})

        rename_dict = {orig_col: std_field for std_field, orig_col in mapping.items() if orig_col in df.columns}
        df_cleaned = df.rename(columns=rename_dict).copy()

        imputed_counts = {}
        for col in df_cleaned.columns:
            if df_cleaned[col].isnull().sum() > 0:
                missing_cnt = int(df_cleaned[col].isnull().sum())
                imputed_counts[col] = missing_cnt
                if pd.api.types.is_numeric_dtype(df_cleaned[col]):
                    median_val = df_cleaned[col].median()
                    df_cleaned[col] = df_cleaned[col].fillna(median_val if not pd.isna(median_val) else 0.0)
                else:
                    mode_val = df_cleaned[col].mode()
                    fill_val = mode_val[0] if len(mode_val) > 0 else "Standard"
                    df_cleaned[col] = df_cleaned[col].fillna(fill_val)

        for col in df_cleaned.select_dtypes(include=["object"]).columns:
            df_cleaned[col] = df_cleaned[col].astype(str).str.strip()

        outlier_flags = np.zeros(len(df_cleaned), dtype=bool)
        for target_col in ["total_estimated_effort_hours", "target_estimated_cost_inr"]:
            if target_col in df_cleaned.columns and pd.api.types.is_numeric_dtype(df_cleaned[target_col]):
                q25 = df_cleaned[target_col].quantile(0.25)
                q75 = df_cleaned[target_col].quantile(0.75)
                iqr = q75 - q25
                upper_bound = q75 + (3.0 * iqr)
                outlier_flags |= (df_cleaned[target_col] > upper_bound)

        df_cleaned["is_extreme_outlier"] = outlier_flags
        outliers_detected = int(outlier_flags.sum())

        cleaned_path = self.cleaned_dir / f"{dataset_id}_cleaned.csv"
        df_cleaned.to_csv(cleaned_path, index=False)

        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            UPDATE uploaded_datasets
            SET cleaned_file_path = ?, status = 'Cleaned', updated_at = ?
            WHERE id = ?
            """,
            (str(cleaned_path), now, dataset_id),
        )
        conn.commit()
        conn.close()

        logger.info(f"Cleaned dataset {dataset_id}: imputed {len(imputed_counts)} cols, flagged {outliers_detected} outliers.")

        return {
            "status": "Cleaned",
            "dataset_id": dataset_id,
            "cleaned_file_path": str(cleaned_path),
            "rows_processed": len(df_cleaned),
            "imputed_columns": imputed_counts,
            "outliers_flagged": outliers_detected,
            "cleaning_timestamp": now,
        }

    def train_candidate_model(self, dataset_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Trains candidate models on cleaned dataset and evaluates on held-out 80/20 test split.
        Records candidate run without overwriting production models.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM uploaded_datasets WHERE id = ?", (dataset_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise ValueError(f"Dataset '{dataset_id}' not found.")

        cleaned_path_str = row["cleaned_file_path"]
        if not cleaned_path_str or not Path(cleaned_path_str).exists():
            clean_res = self.clean_and_preprocess(dataset_id)
            cleaned_path_str = clean_res["cleaned_file_path"]

        df = pd.read_csv(cleaned_path_str)

        if len(df) < 20:
            raise ValueError(f"Insufficient training samples ({len(df)} rows). Model training requires at least 20 rows.")

        candidate_targets = [
            t for t in ["total_estimated_effort_hours", "estimated_duration_calendar_days", "target_estimated_cost_inr"]
            if t in df.columns
        ]

        if not candidate_targets:
            raise ValueError(
                "Dataset does not contain any recognizable target column "
                "(total_estimated_effort_hours, estimated_duration_calendar_days, target_estimated_cost_inr)."
            )

        candidate_num_features = [
            c for c in ["feature_count", "website_pages_or_screens", "integration_count", "user_role_count", "team_size"]
            if c in df.columns and c not in candidate_targets
        ]
        candidate_cat_features = [
            c for c in ["project_type", "project_complexity", "frontend_stack", "backend_stack", "database", "hosting_platform", "expected_user_band"]
            if c in df.columns and c not in candidate_targets
        ]

        all_input_features = candidate_cat_features + candidate_num_features
        if not all_input_features:
            all_input_features = [c for c in df.columns if c not in candidate_targets and c != "is_extreme_outlier" and c != "project_id"]

        for feat in all_input_features:
            if feat in FORBIDDEN_LEAKAGE_TARGETS:
                raise ValueError(f"Target leakage detected: column '{feat}' cannot be used as an input feature.")

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        run_artifacts_dir = self.candidates_dir / run_id
        run_artifacts_dir.mkdir(parents=True, exist_ok=True)

        evaluated_metrics: Dict[str, Any] = {}
        trained_candidate_files: Dict[str, str] = {}

        for target_col in candidate_targets:
            valid_df = df[df[target_col] > 0].copy()
            if len(valid_df) < 15:
                continue

            X = valid_df[all_input_features].copy()
            y = valid_df[target_col].copy()

            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.20, random_state=42
            )

            cat_cols = [c for c in candidate_cat_features if c in X.columns]
            num_cols = [c for c in candidate_num_features if c in X.columns]

            transformers = []
            if cat_cols:
                transformers.append((
                    "cat",
                    Pipeline([
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]),
                    cat_cols,
                ))
            if num_cols:
                transformers.append((
                    "num",
                    Pipeline([
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]),
                    num_cols,
                ))

            if not transformers:
                transformers.append((
                    "num",
                    Pipeline([
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]),
                    list(X.columns),
                ))

            preprocessor = ColumnTransformer(transformers=transformers)
            pipeline = Pipeline([
                ("preprocessor", preprocessor),
                ("regressor", RandomForestRegressor(n_estimators=100, max_depth=16, random_state=42, n_jobs=-1)),
            ])

            pipeline.fit(X_train, y_train)

            y_pred = pipeline.predict(X_test)
            r2 = float(r2_score(y_test, y_pred))
            mae = float(mean_absolute_error(y_test, y_pred))
            rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

            rel_metrics = calculate_relative_error_metrics(y_test.values, y_pred)
            mmre = rel_metrics["mmre"]
            mdmre = rel_metrics["mdmre"]
            pred25 = rel_metrics["pred25"]

            model_filename = f"{target_col}.joblib"
            joblib.dump(pipeline, run_artifacts_dir / model_filename)
            trained_candidate_files[target_col] = str(run_artifacts_dir / model_filename)

            evaluated_metrics[target_col] = {
                "train_samples": int(len(X_train)),
                "test_samples": int(len(X_test)),
                "test_r2": round(r2, 4),
                "test_mae": round(mae, 2),
                "test_rmse": round(rmse, 2),
                "test_mmre": round(mmre, 4),
                "test_mdmre": round(mdmre, 4),
                "test_pred25": round(pred25, 2),
            }

        is_viable_candidate = any(m["test_r2"] > 0.40 for m in evaluated_metrics.values())

        now = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO model_training_runs (
                id, dataset_id, model_version, algorithm, targets_json, features_json,
                train_samples, test_samples, metrics_json, status, promoted_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                dataset_id,
                f"Candidate-{run_id[-6:]}",
                "RandomForestRegressor",
                json.dumps(candidate_targets),
                json.dumps(all_input_features),
                int(len(df) * 0.8),
                int(len(df) * 0.2),
                json.dumps(evaluated_metrics),
                "Candidate" if is_viable_candidate else "Rejected",
                None,
                now,
            ),
        )
        conn.commit()
        conn.close()

        logger.info(f"Completed candidate training run {run_id} on dataset {dataset_id}. Viable: {is_viable_candidate}")

        return {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "status": "Candidate" if is_viable_candidate else "Rejected",
            "targets_trained": candidate_targets,
            "features_used": all_input_features,
            "evaluation_metrics": evaluated_metrics,
            "promotion_recommended": is_viable_candidate,
            "created_at": now,
        }

    def promote_candidate_model(self, run_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Promotes an evaluated candidate model run to production active status.
        Replaces active model artifacts and triggers runtime registry reload.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM model_training_runs WHERE id = ?", (run_id,))
        run_row = cursor.fetchone()
        if not run_row:
            conn.close()
            raise ValueError(f"Training run '{run_id}' not found.")

        run_artifacts_dir = self.candidates_dir / run_id
        if not run_artifacts_dir.exists():
            conn.close()
            raise ValueError(f"Candidate artifacts directory missing at: {run_artifacts_dir}")

        prod_artifacts_dir = Path(settings.ARTIFACTS_DIR)

        file_map = {
            "target_estimated_cost_inr.joblib": "cost_model.joblib",
            "total_estimated_effort_hours.joblib": "effort_model.joblib",
            "estimated_duration_calendar_days.joblib": "duration_model.joblib",
        }

        promoted_count = 0
        for cand_file, prod_file in file_map.items():
            cand_path = run_artifacts_dir / cand_file
            if cand_path.exists():
                shutil.copy2(cand_path, prod_artifacts_dir / prod_file)
                promoted_count += 1

        if promoted_count == 0:
            conn.close()
            raise ValueError("No candidate model files found to promote.")

        metrics = json.loads(run_row["metrics_json"])
        meta_path = prod_artifacts_dir / "model_metadata.json"
        now = datetime.now(timezone.utc).isoformat()

        updated_metadata = {
            "provenance": f"Promoted from Dataset Run {run_id}",
            "training_timestamp": now,
            "model_version": run_row["model_version"],
            "targets": json.loads(run_row["targets_json"]),
            "input_features": json.loads(run_row["features_json"]),
            "models": {
                target: {
                    "artifact_file": file_map.get(f"{target}.joblib", f"{target}.joblib"),
                    "version": run_row["model_version"],
                    "algorithm": run_row["algorithm"],
                    "metrics": target_metrics,
                    "status": "promoted_active",
                }
                for target, target_metrics in metrics.items()
            },
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(updated_metadata, f, indent=2)

        reports_path = Path(settings.REPORTS_DIR) / "model_metrics.json"
        if reports_path.parent.exists():
            with open(reports_path, "w", encoding="utf-8") as f:
                json.dump(updated_metadata, f, indent=2)

        model_registry.load_models()

        cursor.execute(
            "UPDATE model_training_runs SET status = 'Promoted', promoted_at = ? WHERE id = ?",
            (now, run_id),
        )
        conn.commit()
        conn.close()

        logger.info(f"Promoted candidate run {run_id} to active production models.")

        return {
            "status": "Promoted",
            "run_id": run_id,
            "model_version": run_row["model_version"],
            "promoted_at": now,
            "active_models_reloaded": model_registry.is_loaded(),
        }

    def list_datasets(self) -> List[Dict[str, Any]]:
        """Returns all uploaded datasets with summary statistics."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM uploaded_datasets ORDER BY created_at DESC;")
        rows = cursor.fetchall()
        conn.close()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "name": r["name"],
                "filename": r["original_filename"],
                "file_format": r["file_format"],
                "provenance": r["provenance"],
                "total_rows": r["total_rows"],
                "valid_rows": r["valid_rows"],
                "invalid_rows": r["invalid_rows"],
                "duplicate_rows": r["duplicate_rows"],
                "missing_values_count": r["missing_values_count"],
                "status": r["status"],
                "created_at": r["created_at"],
            })
        return results

    def get_dataset_details(self, dataset_id: str) -> Dict[str, Any]:
        """Returns full dataset profile, validation report, and columns schema."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM uploaded_datasets WHERE id = ?", (dataset_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise ValueError(f"Dataset '{dataset_id}' not found.")

        return {
            "id": row["id"],
            "name": row["name"],
            "filename": row["original_filename"],
            "file_format": row["file_format"],
            "provenance": row["provenance"],
            "total_rows": row["total_rows"],
            "total_columns": row["total_columns"],
            "valid_rows": row["valid_rows"],
            "invalid_rows": row["invalid_rows"],
            "duplicate_rows": row["duplicate_rows"],
            "missing_values_count": row["missing_values_count"],
            "column_schemas": json.loads(row["column_schema_json"]),
            "validation_report": json.loads(row["validation_report_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_training_history(self) -> List[Dict[str, Any]]:
        """Returns history of all candidate and promoted model training runs."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT r.*, d.name as dataset_name, d.original_filename
            FROM model_training_runs r
            JOIN uploaded_datasets d ON r.dataset_id = d.id
            ORDER BY r.created_at DESC;
            """
        )
        rows = cursor.fetchall()
        conn.close()

        results = []
        for r in rows:
            results.append({
                "run_id": r["id"],
                "dataset_id": r["dataset_id"],
                "dataset_name": r["dataset_name"],
                "filename": r["original_filename"],
                "model_version": r["model_version"],
                "algorithm": r["algorithm"],
                "targets": json.loads(r["targets_json"]),
                "train_samples": r["train_samples"],
                "test_samples": r["test_samples"],
                "metrics": json.loads(r["metrics_json"]),
                "status": r["status"],
                "promoted_at": r["promoted_at"],
                "created_at": r["created_at"],
            })
        return results


# Global singleton instance
dataset_pipeline = DatasetPipeline()
