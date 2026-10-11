import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class HistoricalBenchmarker:
    """
    Extracts and computes defensible historical project cohort benchmarks
    from the 2,500 projects in CostPilot_AI_Training_Dataset.xlsx.
    """

    def __init__(self, dataset_path: Optional[str] = None):
        self.dataset_path = Path(dataset_path or settings.DATASET_PATH)
        self._df_projects: Optional[pd.DataFrame] = None

    def _ensure_data_loaded(self) -> Optional[pd.DataFrame]:
        if self._df_projects is not None:
            return self._df_projects
        if not self.dataset_path.exists():
            logger.warning(f"Dataset file not found at {self.dataset_path}")
            return None
        try:
            self._df_projects = pd.read_excel(self.dataset_path, sheet_name="Projects_Training")
            logger.info(f"Loaded {len(self._df_projects)} historical project records for ML benchmarking.")
            return self._df_projects
        except Exception as e:
            logger.error(f"Failed to load historical benchmark dataset: {e}")
            return None

    def get_cohort_benchmark(
        self,
        project_type: str,
        overall_complexity: str,
        current_effort: float,
        current_duration: float,
        current_cost_inr: float,
        currency: str = "INR",
        exchange_rate: float = 1.0,
    ) -> Dict[str, Any]:
        df = self._ensure_data_loaded()
        if df is None or len(df) == 0:
            return {
                "has_benchmark": False,
                "comparable_records_count": 0,
                "description": "Historical dataset unavailable for cohort benchmarking.",
                "provenance": "CostPilot_AI_Training_Dataset.xlsx",
            }

        # Normalize project type using archetype mapping
        archetype = settings.DOMAIN_ARCHETYPE_MAPPING.get(project_type, project_type)

        # Match on project_type and complexity
        mask_exact = (
            (df["project_type"].str.lower() == archetype.lower()) |
            (df["project_type"].str.lower() == project_type.lower())
        ) & (df["project_complexity"].str.lower() == overall_complexity.lower())

        df_matched = df[mask_exact]
        match_type = "Exact archetype & complexity match"

        # Fallback to project_type if less than 3 records
        if len(df_matched) < 3:
            mask_type_only = (
                (df["project_type"].str.lower() == archetype.lower()) |
                (df["project_type"].str.lower() == project_type.lower())
            )
            df_matched = df[mask_type_only]
            match_type = "Domain archetype match across all complexities"

        if len(df_matched) == 0:
            # Fallback to same complexity
            mask_comp = df["project_complexity"].str.lower() == overall_complexity.lower()
            df_matched = df[mask_comp]
            match_type = f"Cross-domain {overall_complexity} complexity baseline"

        count = len(df_matched)
        if count == 0:
            return {
                "has_benchmark": False,
                "comparable_records_count": 0,
                "description": f"No eligible comparable historical projects found for '{project_type}'.",
                "provenance": "CostPilot_AI_Training_Dataset.xlsx (Projects_Training)",
            }

        avg_effort = round(float(df_matched["total_estimated_effort_hours"].mean()), 1)
        median_effort = round(float(df_matched["total_estimated_effort_hours"].median()), 1)

        avg_duration = round(float(df_matched["estimated_duration_calendar_days"].mean()), 1)
        median_duration = round(float(df_matched["estimated_duration_calendar_days"].median()), 1)

        avg_cost_inr = round(float(df_matched["target_estimated_cost_inr"].mean()), 2)
        median_cost_inr = round(float(df_matched["target_estimated_cost_inr"].median()), 2)

        if exchange_rate is not None:
            rate = max(1e-4, float(exchange_rate))
        else:
            cur_info = settings.SUPPORTED_CURRENCIES.get(currency.upper(), {})
            rate = float(cur_info.get("rate_to_inr", 1.0))
        rate = max(1e-4, rate)
        avg_cost_converted = round(avg_cost_inr / rate, 2)
        median_cost_converted = round(median_cost_inr / rate, 2)

        delta_effort = round(current_effort - avg_effort, 1)
        delta_duration = round(current_duration - avg_duration, 1)
        delta_cost_inr = round(current_cost_inr - avg_cost_inr, 2)
        delta_cost_converted = round(delta_cost_inr / rate, 2)

        return {
            "has_benchmark": True,
            "has_cohort_benchmark": True,
            "cohort_sample_size": count,
            "cohort_filter": match_type,
            "cohort_avg_effort_hours": avg_effort,
            "cohort_avg_duration_days": avg_duration,
            "cohort_avg_cost_inr": avg_cost_inr,
            "cohort_effort_diff_hours": delta_effort,
            "cohort_duration_diff_days": delta_duration,
            "cohort_cost_diff_inr": delta_cost_inr,
            "dataset_provenance": "CostPilot_AI_Training_Dataset.xlsx (2,500 projects)",
            "match_criterion": match_type,
            "comparable_records_count": count,
            "dataset_cohort_size": len(df),
            "benchmark_avg_effort_hours": avg_effort,
            "benchmark_median_effort_hours": median_effort,
            "benchmark_avg_duration_days": avg_duration,
            "benchmark_median_duration_days": median_duration,
            "benchmark_avg_cost_inr": avg_cost_inr,
            "benchmark_median_cost_inr": median_cost_inr,
            "benchmark_avg_cost_converted": avg_cost_converted,
            "benchmark_median_cost_converted": median_cost_converted,
            "delta_effort_hours": delta_effort,
            "delta_duration_days": delta_duration,
            "delta_cost_inr": delta_cost_inr,
            "delta_cost_converted": delta_cost_converted,
            "currency_code": currency.upper(),
            "exchange_rate": rate,
            "provenance": "Historical cohort from 2,500 projects in CostPilot_AI_Training_Dataset.xlsx (Projects_Training sheet)",
            "assumptions": "Comparable historical records include all-inclusive lifecycle software budgets with 15% standard contingency.",
        }

    def find_top_analogies(
        self,
        project_type: str,
        overall_complexity: str,
        feature_count: int,
        frontend_stack: str = "React",
        backend_stack: str = "Node.js_Express",
        currency: str = "INR",
        exchange_rate: float = 1.0,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Performs multi-attribute analogy search across 2,500 historical projects.
        Ranks comparable records by similarity score (0-100%).
        """
        df = self._ensure_data_loaded()
        if df is None or len(df) == 0:
            return []

        archetype = settings.DOMAIN_ARCHETYPE_MAPPING.get(project_type, project_type).lower()
        target_p_type = project_type.lower()
        target_comp = overall_complexity.lower()
        target_features = max(1, int(feature_count))
        rate = max(1e-4, float(exchange_rate or 1.0))

        complexity_weights = {"low": 1, "medium": 2, "high": 3, "very high": 4}
        target_comp_val = complexity_weights.get(target_comp, 2)

        candidates = []
        for _, row in df.iterrows():
            row_type = str(row.get("project_type", "")).lower()
            row_comp = str(row.get("project_complexity", "")).lower()
            row_feats = int(row.get("feature_count", 10))
            row_front = str(row.get("frontend_stack", ""))
            row_back = str(row.get("backend_stack", ""))

            # 1. Domain / Archetype Score (max 40 pts)
            if row_type == target_p_type or row_type == archetype:
                domain_score = 40.0
            elif any(w in row_type for w in target_p_type.split()):
                domain_score = 25.0
            else:
                domain_score = 10.0

            # 2. Complexity Score (max 30 pts)
            row_comp_val = complexity_weights.get(row_comp, 2)
            comp_diff = abs(target_comp_val - row_comp_val)
            comp_score = 30.0 if comp_diff == 0 else (15.0 if comp_diff == 1 else 5.0)

            # 3. Feature Count Proximity (max 20 pts)
            feat_diff_ratio = abs(target_features - row_feats) / max(target_features, row_feats, 1)
            feat_score = round(20.0 * max(0.0, 1.0 - feat_diff_ratio), 1)

            # 4. Tech Stack Overlap (max 10 pts)
            stack_score = 0.0
            if frontend_stack.lower() in row_front.lower():
                stack_score += 5.0
            if backend_stack.lower() in row_back.lower():
                stack_score += 5.0

            total_similarity = round(domain_score + comp_score + feat_score + stack_score, 1)

            cost_inr = float(row.get("target_estimated_cost_inr", 0.0))
            cost_converted = round(cost_inr / rate, 2)

            candidates.append({
                "project_id": str(row.get("project_id", "")),
                "project_type": str(row.get("project_type", "")),
                "project_complexity": str(row.get("project_complexity", "")),
                "feature_count": row_feats,
                "frontend_stack": row_front,
                "backend_stack": row_back,
                "similarity_score_pct": total_similarity,
                "historical_effort_hours": round(float(row.get("total_estimated_effort_hours", 0.0)), 1),
                "historical_duration_days": int(row.get("estimated_duration_calendar_days", 0)),
                "historical_cost_inr": cost_inr,
                "historical_cost_converted": cost_converted,
                "currency_code": currency.upper(),
                "matching_notes": f"Historical project with {row_feats} features and {row_comp} complexity in {row_type}.",
                "provenance": "CostPilot_AI_Training_Dataset.xlsx (Projects_Training sheet)",
            })

        candidates.sort(key=lambda x: x["similarity_score_pct"], reverse=True)
        return candidates[:top_k]


historical_benchmarker = HistoricalBenchmarker()

