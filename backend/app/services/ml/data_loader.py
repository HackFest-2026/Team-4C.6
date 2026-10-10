import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

REQUIRED_SHEETS = [
    "README_START_HERE",
    "Projects_Training",
    "Feature_Level_Data",
    "Edge_Cases",
    "Feature_Effort_Priors",
    "Summary_By_Project_Type",
    "Data_Dictionary",
]

PROJECTS_REQUIRED_INPUT_COLUMNS = [
    "project_id",
    "project_type",
    "project_complexity",
    "feature_count",
    "website_pages_or_screens",
    "frontend_stack",
    "backend_stack",
    "database",
    "hosting_platform",
    "expected_user_band",
    "integration_count",
    "user_role_count",
    "deadline_pressure",
    "quality_requirement",
    "client_region",
]

PROJECTS_SUPPORTED_TARGETS = [
    "target_estimated_cost_inr",
    "target_cost_excluding_contingency_inr",
    "target_labour_cost_inr",
    "total_estimated_effort_hours",
    "estimated_duration_calendar_days",
]

FEATURE_LEVEL_REQUIRED_COLUMNS = [
    "project_id",
    "feature_name",
    "feature_category",
    "feature_complexity",
    "estimated_effort_hours",
    "reuse_level_pct",
    "feature_integration_count",
]

FEATURE_PRIORS_REQUIRED_COLUMNS = [
    "feature_name",
    "low_complexity_base_hours",
    "medium_complexity_base_hours",
    "high_complexity_base_hours",
    "very_high_complexity_base_hours",
]


class DatasetValidationError(Exception):
    """Raised when dataset structure, integrity or validation fails."""
    pass


class DatasetLoader:
    def __init__(self, dataset_path: Optional[str] = None):
        self.dataset_path = Path(dataset_path or settings.DATASET_PATH)
        self.is_synthetic: bool = True
        self.quality_report: Dict[str, Any] = {}

    def validate_file_exists(self) -> None:
        if not self.dataset_path.exists():
            raise DatasetValidationError(
                f"Dataset workbook not found at: {self.dataset_path}. "
                f"Please ensure CostPilot_AI_Training_Dataset.xlsx is placed in backend/data/."
            )

    def load_all_sheets(self) -> Dict[str, pd.DataFrame]:
        self.validate_file_exists()
        try:
            excel_file = pd.ExcelFile(self.dataset_path)
            sheet_names = excel_file.sheet_names
        except Exception as e:
            raise DatasetValidationError(f"Failed to read Excel workbook: {str(e)}")

        missing_sheets = [s for s in REQUIRED_SHEETS if s not in sheet_names]
        if missing_sheets:
            raise DatasetValidationError(f"Missing required sheet(s) in workbook: {missing_sheets}")

        sheets = {}
        for s in REQUIRED_SHEETS:
            sheets[s] = pd.read_excel(excel_file, sheet_name=s)
        return sheets

    def inspect_and_validate(self) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any]]:
        """
        Loads all sheets, validates schemas, relationships, non-negativity, duplicates,
        computes data quality metrics and writes backend/reports/data_quality_report.json.
        """
        sheets = self.load_all_sheets()
        df_projects = sheets["Projects_Training"]
        df_features = sheets["Feature_Level_Data"]
        df_priors = sheets["Feature_Effort_Priors"]
        df_edge = sheets["Edge_Cases"]
        df_readme = sheets["README_START_HERE"]

        report: Dict[str, Any] = {
            "dataset_file": str(self.dataset_path.name),
            "is_synthetic": True,
            "provenance_notice": "SIMULATED / SYNTHETIC DATASET. Not verified commercial contract actuals.",
            "sheets_found": list(sheets.keys()),
            "projects_count": len(df_projects),
            "features_count": len(df_features),
            "edge_cases_count": len(df_edge),
            "validation_errors": [],
            "validation_warnings": [],
            "summary": {},
        }

        # 1. Validate Projects_Training columns
        missing_proj_inputs = [c for c in PROJECTS_REQUIRED_INPUT_COLUMNS if c not in df_projects.columns]
        if missing_proj_inputs:
            err = f"Projects_Training is missing required input columns: {missing_proj_inputs}"
            report["validation_errors"].append(err)
            raise DatasetValidationError(err)

        missing_proj_targets = [c for c in PROJECTS_SUPPORTED_TARGETS if c not in df_projects.columns]
        if missing_proj_targets:
            err = f"Projects_Training is missing required target columns: {missing_proj_targets}"
            report["validation_errors"].append(err)
            raise DatasetValidationError(err)

        # 2. Duplicate project IDs
        dup_projects = df_projects["project_id"].duplicated().sum()
        if dup_projects > 0:
            err = f"Found {dup_projects} duplicate project_id entries in Projects_Training"
            report["validation_errors"].append(err)
            raise DatasetValidationError(err)

        # 3. Non-negative numeric validation on Projects_Training
        numeric_cols_to_check = [
            "feature_count",
            "website_pages_or_screens",
            "integration_count",
            "user_role_count",
            "total_estimated_effort_hours",
            "estimated_duration_calendar_days",
            "target_labour_cost_inr",
            "target_estimated_cost_inr",
            "target_cost_excluding_contingency_inr",
        ]
        for col in numeric_cols_to_check:
            neg_count = (df_projects[col] < 0).sum()
            if neg_count > 0:
                err = f"Column '{col}' has {neg_count} negative values in Projects_Training"
                report["validation_errors"].append(err)
                raise DatasetValidationError(err)

        # 4. Feature_Level_Data validation
        missing_feat_cols = [c for c in FEATURE_LEVEL_REQUIRED_COLUMNS if c not in df_features.columns]
        if missing_feat_cols:
            err = f"Feature_Level_Data is missing required columns: {missing_feat_cols}"
            report["validation_errors"].append(err)
            raise DatasetValidationError(err)

        neg_feat_hours = (df_features["estimated_effort_hours"] < 0).sum()
        if neg_feat_hours > 0:
            err = f"Feature_Level_Data has {neg_feat_hours} negative estimated_effort_hours"
            report["validation_errors"].append(err)
            raise DatasetValidationError(err)

        # Foreign key integrity: feature project_id must exist in Projects_Training
        project_ids_set = set(df_projects["project_id"].unique())
        orphan_features = df_features[~df_features["project_id"].isin(project_ids_set)]
        if len(orphan_features) > 0:
            err = f"Found {len(orphan_features)} orphan features with project_id not in Projects_Training"
            report["validation_errors"].append(err)
            raise DatasetValidationError(err)

        # 5. Feature_Effort_Priors validation
        missing_prior_cols = [c for c in FEATURE_PRIORS_REQUIRED_COLUMNS if c not in df_priors.columns]
        if missing_prior_cols:
            err = f"Feature_Effort_Priors is missing required columns: {missing_prior_cols}"
            report["validation_errors"].append(err)
            raise DatasetValidationError(err)

        # Verify prior hours are non-negative and monotonic
        for _, row in df_priors.iterrows():
            fname = row["feature_name"]
            l, m, h, vh = (
                row["low_complexity_base_hours"],
                row["medium_complexity_base_hours"],
                row["high_complexity_base_hours"],
                row["very_high_complexity_base_hours"],
            )
            if any(val < 0 for val in (l, m, h, vh)):
                report["validation_warnings"].append(f"Prior '{fname}' contains negative base hours")
            if not (l <= m <= h <= vh):
                report["validation_warnings"].append(
                    f"Prior '{fname}' non-monotonic complexity hours: {l} <= {m} <= {h} <= {vh} is violated"
                )

        # 6. Check missing values (nulls)
        proj_nulls = df_projects[PROJECTS_REQUIRED_INPUT_COLUMNS + PROJECTS_SUPPORTED_TARGETS].isnull().sum().to_dict()
        feat_nulls = df_features[FEATURE_LEVEL_REQUIRED_COLUMNS].isnull().sum().to_dict()

        # Summary statistics
        report["summary"] = {
            "projects_count": int(len(df_projects)),
            "features_count": int(len(df_features)),
            "priors_count": int(len(df_priors)),
            "edge_cases_count": int(len(df_edge)),
            "project_types": sorted(df_projects["project_type"].unique().tolist()),
            "complexity_levels": sorted(df_projects["project_complexity"].unique().tolist()),
            "frontend_stacks": sorted(df_projects["frontend_stack"].unique().tolist()),
            "backend_stacks": sorted(df_projects["backend_stack"].unique().tolist()),
            "databases": sorted(df_projects["database"].unique().tolist()),
            "hosting_platforms": sorted(df_projects["hosting_platform"].unique().tolist()),
            "client_regions": sorted(df_projects["client_region"].unique().tolist()),
            "null_values_projects": {k: int(v) for k, v in proj_nulls.items() if v > 0},
            "null_values_features": {k: int(v) for k, v in feat_nulls.items() if v > 0},
            "cost_target_mean_inr": float(df_projects["target_estimated_cost_inr"].mean()),
            "cost_target_median_inr": float(df_projects["target_estimated_cost_inr"].median()),
            "effort_target_mean_hours": float(df_projects["total_estimated_effort_hours"].mean()),
            "effort_target_median_hours": float(df_projects["total_estimated_effort_hours"].median()),
            "duration_target_mean_days": float(df_projects["estimated_duration_calendar_days"].mean()),
        }

        # Write data quality report to reports directory
        reports_dir = Path(settings.REPORTS_DIR)
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_file = reports_dir / "data_quality_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Data quality report saved to {report_file}")
        self.quality_report = report
        return sheets, report


if __name__ == "__main__":
    loader = DatasetLoader()
    sheets, report = loader.inspect_and_validate()
    print("Dataset validation SUCCESSFUL!")
    print(f"Projects: {report['projects_count']}, Features: {report['features_count']}")
    print(f"Quality report written to: {settings.REPORTS_DIR}/data_quality_report.json")
