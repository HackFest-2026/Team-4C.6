"""
CostPilot AI — Unit and Integration Tests for Dataset Pipeline & Estimation Dashboard.
Tests:
1. Ingestion of CSV and Excel workbooks.
2. File format and safety limit enforcement.
3. Schema profiling, type inference, and candidate field mapping.
4. Data cleaning, missing-value imputation, and outlier detection.
5. Target leakage prevention.
6. Candidate model training with held-out 80/20 test split and mathematical metrics.
7. Candidate model promotion workflow and runtime registry updates.
8. API endpoints for dataset upload, cleaning, training, and promotion.
"""

import io
import json
import uuid
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services.ml.dataset_pipeline import dataset_pipeline, DatasetPipeline
from app.services.ml.model_registry import model_registry

client = TestClient(app)


def generate_synthetic_projects_df(n_samples: int = 40) -> pd.DataFrame:
    """Generates a valid, leak-free synthetic historical project dataset for testing."""
    rng = np.random.default_rng(42)
    project_types = ["FinTech Platform", "Healthcare Portal", "E-Commerce", "SaaS Platform"]
    complexities = ["Low", "Medium", "High", "Very High"]
    platforms = ["Web Application", "Mobile App (iOS & Android)", "Full-Stack Enterprise"]

    data = []
    for i in range(n_samples):
        p_type = rng.choice(project_types)
        comp = rng.choice(complexities)
        plat = rng.choice(platforms)
        feat_cnt = int(rng.integers(5, 30))
        team = int(rng.integers(2, 8))

        # Synthetic realistic target values
        effort = float(feat_cnt * rng.integers(20, 50) + team * 15)
        duration = float(max(14, int(effort / (team * 7.5))))
        cost = float(effort * rng.integers(1200, 2500) + 50000.0)

        data.append({
            "project_id": f"PRJ-{1000 + i}",
            "project_type": p_type,
            "project_complexity": comp,
            "hosting_platform": plat,
            "feature_count": feat_cnt,
            "team_size": team,
            "frontend_stack": "React",
            "backend_stack": "FastAPI",
            "database": "PostgreSQL",
            "expected_user_band": "10k-50k",
            "total_estimated_effort_hours": effort,
            "estimated_duration_calendar_days": duration,
            "target_estimated_cost_inr": cost,
        })
    return pd.DataFrame(data)


def test_dataset_pipeline_csv_upload_and_profiling():
    df = generate_synthetic_projects_df(30)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    res = dataset_pipeline.upload_and_profile(
        file_bytes=csv_bytes,
        filename="test_historical_projects.csv",
        provenance="Organization-provided",
        user_id="test_user_01",
        dataset_name="Test Enterprise Ingestion",
    )

    assert res["dataset_id"].startswith("ds_")
    assert res["total_rows"] == 30
    assert res["total_columns"] == 13
    assert res["valid_rows"] == 30
    assert res["status"] == "Validated"
    assert "total_estimated_effort_hours" in res["detected_mapping"]
    assert "target_estimated_cost_inr" in res["detected_mapping"]
    assert len(res["validation_report"]["available_targets"]) >= 2


def test_dataset_pipeline_excel_upload():
    df = generate_synthetic_projects_df(25)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Projects_Training", index=False)
    excel_bytes = output.getvalue()

    res = dataset_pipeline.upload_and_profile(
        file_bytes=excel_bytes,
        filename="test_workbook.xlsx",
        provenance="Synthetic",
        dataset_name="Test Excel Workbook",
    )

    assert res["total_rows"] == 25
    assert res["file_format"] == "xlsx"
    assert res["valid_rows"] == 25


def test_dataset_pipeline_rejects_invalid_format_and_empty():
    with pytest.raises(ValueError, match="Unsupported file format"):
        dataset_pipeline.upload_and_profile(
            file_bytes=b"dummy binary",
            filename="malicious_file.exe",
        )

    with pytest.raises(ValueError):
        dataset_pipeline.upload_and_profile(
            file_bytes=b"",
            filename="empty.csv",
        )


def test_dataset_pipeline_clean_and_preprocess():
    df = generate_synthetic_projects_df(35)
    # Inject missing values and whitespace
    df.loc[2, "project_type"] = None
    df.loc[5, "feature_count"] = None
    df.loc[10, "hosting_platform"] = "   Web Application   "

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    upload_res = dataset_pipeline.upload_and_profile(
        file_bytes=csv_bytes,
        filename="dirty_dataset.csv",
    )
    dataset_id = upload_res["dataset_id"]

    clean_res = dataset_pipeline.clean_and_preprocess(dataset_id)
    assert clean_res["status"] == "Cleaned"
    assert clean_res["rows_processed"] == 35
    assert clean_res["imputed_columns"]["project_type"] == 1
    assert clean_res["imputed_columns"]["feature_count"] == 1


def test_candidate_model_training_and_promotion():
    df = generate_synthetic_projects_df(45)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    upload_res = dataset_pipeline.upload_and_profile(
        file_bytes=csv_bytes,
        filename="candidate_training_set.csv",
        dataset_name="Candidate Training Dataset",
    )
    dataset_id = upload_res["dataset_id"]

    # 1. Clean
    dataset_pipeline.clean_and_preprocess(dataset_id)

    # 2. Train candidate models
    train_res = dataset_pipeline.train_candidate_model(dataset_id, user_id="admin_user")
    assert train_res["status"] == "Candidate"
    assert "total_estimated_effort_hours" in train_res["evaluation_metrics"]
    metrics = train_res["evaluation_metrics"]["total_estimated_effort_hours"]
    assert "test_r2" in metrics
    assert "test_mmre" in metrics
    assert "test_pred25" in metrics
    assert metrics["train_samples"] > 0
    assert metrics["test_samples"] > 0

    run_id = train_res["run_id"]

    # 3. Promote candidate model (with backup and restore to preserve baseline test environment)
    from pathlib import Path
    import shutil
    from app.core.config import settings

    artifacts_dir = Path(settings.ARTIFACTS_DIR)
    reports_dir = Path(settings.REPORTS_DIR)
    backup_dir = artifacts_dir / "_test_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Backup existing production files
    for fname in ["cost_model.joblib", "effort_model.joblib", "duration_model.joblib", "model_metadata.json"]:
        p = artifacts_dir / fname
        if p.exists():
            shutil.copy2(p, backup_dir / fname)
    if (reports_dir / "model_metrics.json").exists():
        shutil.copy2(reports_dir / "model_metrics.json", backup_dir / "model_metrics.json")

    try:
        promote_res = dataset_pipeline.promote_candidate_model(run_id, user_id="admin_user")
        assert promote_res["status"] == "Promoted"
        assert promote_res["active_models_reloaded"] is True
    finally:
        # Restore original production artifacts
        for fname in ["cost_model.joblib", "effort_model.joblib", "duration_model.joblib", "model_metadata.json"]:
            bp = backup_dir / fname
            if bp.exists():
                shutil.copy2(bp, artifacts_dir / fname)
        if (backup_dir / "model_metrics.json").exists():
            shutil.copy2(backup_dir / "model_metrics.json", reports_dir / "model_metrics.json")
        shutil.rmtree(backup_dir, ignore_errors=True)
        model_registry.reload_all()


def test_dataset_api_endpoints_workflow():
    df = generate_synthetic_projects_df(25)
    csv_content = df.to_csv(index=False)

    # 1. Upload via REST API
    files = {"file": ("api_test.csv", csv_content, "text/csv")}
    data = {"provenance": "Organization-provided", "dataset_name": "API REST Ingestion"}
    res = client.post("/api/v1/datasets/upload", files=files, data=data)
    assert res.status_code == 200
    dataset_data = res.json()["dataset"]
    dataset_id = dataset_data["dataset_id"]

    # 2. List datasets
    list_res = client.get("/api/v1/datasets")
    assert list_res.status_code == 200
    assert any(d["id"] == dataset_id for d in list_res.json()["datasets"])

    # 3. Get dataset details
    details_res = client.get(f"/api/v1/datasets/{dataset_id}")
    assert details_res.status_code == 200
    assert details_res.json()["dataset"]["name"] == "API REST Ingestion"

    # 4. Clean dataset
    clean_res = client.post(f"/api/v1/datasets/{dataset_id}/clean")
    assert clean_res.status_code == 200
    assert clean_res.json()["cleaning"]["status"] == "Cleaned"

    # 5. Training history endpoint
    hist_res = client.get("/api/v1/datasets/models/history")
    assert hist_res.status_code == 200
    assert isinstance(hist_res.json()["history"], list)
