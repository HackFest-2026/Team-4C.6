import pytest
from pathlib import Path
from app.services.ml.data_loader import DatasetLoader, DatasetValidationError
from app.core.config import settings


def test_dataset_file_exists():
    loader = DatasetLoader()
    assert Path(loader.dataset_path).exists(), f"Dataset file missing at {loader.dataset_path}"


def test_load_all_sheets():
    loader = DatasetLoader()
    sheets = loader.load_all_sheets()
    expected_sheets = [
        "README_START_HERE",
        "Projects_Training",
        "Feature_Level_Data",
        "Edge_Cases",
        "Feature_Effort_Priors",
        "Summary_By_Project_Type",
        "Data_Dictionary",
    ]
    for s in expected_sheets:
        assert s in sheets, f"Sheet '{s}' missing from loaded sheets"


def test_inspect_and_validate_dataset():
    loader = DatasetLoader()
    sheets, report = loader.inspect_and_validate()
    
    assert report["is_synthetic"] is True
    assert report["projects_count"] == 2500
    assert report["features_count"] == 44301
    assert report["edge_cases_count"] == 20
    assert len(report["validation_errors"]) == 0
    assert (Path(settings.REPORTS_DIR) / "data_quality_report.json").exists()


def test_feature_to_project_linkage():
    """Mandatory test 28: Verify foreign key integrity between features and projects."""
    loader = DatasetLoader()
    sheets = loader.load_all_sheets()
    df_projects = sheets["Projects_Training"]
    df_features = sheets["Feature_Level_Data"]

    project_ids = set(df_projects["project_id"].unique())
    feature_project_ids = set(df_features["project_id"].unique())

    # Every project_id in features must exist in projects
    assert feature_project_ids.issubset(project_ids), "Found feature records referencing non-existent project_ids"
    # Project IDs must be unique
    assert df_projects["project_id"].is_unique, "Duplicate project_ids detected in Projects_Training"
