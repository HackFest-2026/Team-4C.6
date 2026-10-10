from typing import Dict, Any, List
from app.core.config import settings


class RiskScoringEngine:
    """
    Computes formula-driven project risk score and measurable confidence metrics.
    Distinguishes ML validation metrics, PERT uncertainty, and estimation confidence.
    """

    def __init__(self):
        self.weights = settings.RISK_FACTOR_WEIGHTS

    def calculate_risk(
        self,
        complexity_level: str,
        deadline_pressure: str,
        max_dependency_depth: int,
        integration_count: int,
        security_requirement: str,
        platform_multiplier: float,
        team_size: int,
        is_timeline_feasible: bool,
        fallback_features_count: int,
        total_features_count: int,
    ) -> Dict[str, Any]:
        """
        Calculates weighted risk score (0-100) and risk level (Low, Medium, High, Critical).
        """
        factor_scores: Dict[str, float] = {}

        # 1. Project Complexity factor (0-100)
        comp_map = {"Low": 20.0, "Medium": 45.0, "High": 75.0, "Very High": 95.0}
        factor_scores["project_complexity"] = comp_map.get(complexity_level, 50.0)

        # 2. Deadline pressure factor
        dl_map = {"Relaxed": 15.0, "Moderate": 40.0, "High": 75.0, "Extreme": 100.0}
        factor_scores["deadline_pressure"] = dl_map.get(deadline_pressure, 50.0)
        if not is_timeline_feasible:
            factor_scores["deadline_pressure"] = 100.0

        # 3. Dependency complexity
        base_dep = max_dependency_depth * 25.0
        if security_requirement in ("Critical", "Regulated"):
            base_dep = max(50.0, base_dep)
        factor_scores["dependency_complexity"] = min(100.0, max(10.0, base_dep))

        # 4. External integrations
        base_integ = integration_count * 20.0
        if security_requirement in ("Critical", "Regulated"):
            base_integ = max(50.0, base_integ)
        factor_scores["external_integrations"] = min(100.0, max(10.0, base_integ))

        # 5. Security requirements
        sec_map = {"Standard": 20.0, "High": 60.0, "Critical": 90.0, "Regulated": 95.0}
        factor_scores["security_requirements"] = sec_map.get(security_requirement, 30.0)

        # 6. Platform count
        factor_scores["platform_count"] = min(100.0, max(10.0, (platform_multiplier - 1.0) * 100.0 + 20.0))

        # 7. Team pressure / concurrency limit
        if team_size > 12:
            factor_scores["team_pressure"] = 80.0
        elif team_size > 8:
            factor_scores["team_pressure"] = 55.0
        elif team_size < 2:
            factor_scores["team_pressure"] = 65.0  # single point of failure risk
        else:
            factor_scores["team_pressure"] = 25.0

        # 8. Unknown/fallback requirements
        fallback_ratio = (fallback_features_count / max(1, total_features_count))
        factor_scores["unknown_requirements"] = round(fallback_ratio * 100.0, 1)

        # Weighted risk calculation
        risk_score = 0.0
        for factor, weight in self.weights.items():
            score = factor_scores.get(factor, 50.0)
            risk_score += score * weight

        risk_score = round(risk_score, 1)

        if risk_score < 25.0:
            risk_level = "Low"
        elif risk_score < 50.0:
            risk_level = "Medium"
        elif risk_score < 75.0:
            risk_level = "High"
        else:
            risk_level = "Critical"

        # Risk drivers identification
        top_risk_drivers = sorted(
            [{"factor": f, "score": s, "weight": self.weights[f]} for f, s in factor_scores.items()],
            key=lambda x: x["score"] * x["weight"],
            reverse=True,
        )[:3]

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "factor_scores": factor_scores,
            "weights": self.weights,
            "top_risk_drivers": top_risk_drivers,
        }

    def calculate_confidence(
        self,
        has_project_description: bool,
        feature_count: int,
        fallback_features_count: int,
        is_timeline_feasible: bool,
        ml_model_available: bool,
    ) -> Dict[str, Any]:
        """
        Calculates estimate completeness and confidence (0-100%) based on verifiable signals.
        """
        score = 0.0
        breakdown = {}

        # 1. Project description completeness (up to 20%)
        desc_score = 20.0 if has_project_description else 10.0
        score += desc_score
        breakdown["project_definition"] = f"{desc_score}/20 pts"

        # 2. Scope review & feature breakdown (up to 30%)
        if feature_count >= 5:
            scope_score = 30.0
        elif feature_count >= 1:
            scope_score = 20.0
        else:
            scope_score = 5.0
        score += scope_score
        breakdown["feature_granularity"] = f"{scope_score}/30 pts"

        # 3. Catalog prior coverage vs generic fallbacks (up to 25%)
        fallback_ratio = fallback_features_count / max(1, feature_count)
        catalog_score = round(25.0 * (1.0 - fallback_ratio), 1)
        score += catalog_score
        breakdown["catalog_prior_match"] = f"{catalog_score}/25 pts"

        # 4. Schedule feasibility (up to 15%)
        sched_score = 15.0 if is_timeline_feasible else 5.0
        score += sched_score
        breakdown["schedule_feasibility"] = f"{sched_score}/15 pts"

        # 5. Machine Learning validation available (up to 10%)
        ml_score = 10.0 if ml_model_available else 4.0
        score += ml_score
        breakdown["ml_validation_benchmark"] = f"{ml_score}/10 pts"

        final_confidence = min(100.0, max(10.0, round(score, 1)))

        confidence_label = "High" if final_confidence >= 80 else "Medium" if final_confidence >= 55 else "Low"

        return {
            "confidence_score_pct": final_confidence,
            "confidence_level": confidence_label,
            "signal_breakdown": breakdown,
        }


risk_scoring_engine = RiskScoringEngine()
