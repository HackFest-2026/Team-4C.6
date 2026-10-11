"""
CostPilot AI — Parametric Software Estimation Model (COCOMO II Adapted).
Provides parametric software effort and schedule estimates based on
calibrated COCOMO II Post-Architecture equations, equivalent KSLOC, and cost drivers.

Equations:
  Effort (Person-Months) = A * (KSLOC)^B * Product(EffortMultipliers)
    A = 2.94 (Calibrated institutional constant)
    B = 0.91 + 0.01 * Sum(ScaleFactors) (Typical range: 1.05 - 1.15)
    1 Person-Month = 152 Productive Person-Hours
  Duration (Months) = C * (Effort_PM)^D
    C = 3.67
    D = 0.28 + 0.2 * (B - 0.91)
"""

from typing import Dict, Any, List, Optional
import math


class ParametricCOCOMOEngine:
    """
    Computes parametric software effort, schedule, and team size
    based on COCOMO II principles adapted for web and cloud applications.
    """

    KSLOC_PER_FEATURE = {
        "Low": 0.8,        # ~800 SLOC
        "Medium": 1.5,     # ~1,500 SLOC
        "High": 3.0,       # ~3,000 SLOC
        "Very High": 5.0,  # ~5,000 SLOC
    }

    def __init__(self):
        self.nominal_a = 2.94
        self.nominal_c = 3.67
        self.hours_per_person_month = 152.0

    def estimate(
        self,
        features: List[Dict[str, Any]],
        overall_complexity: str = "Medium",
        platform: str = "Web Application",
        quality_requirement: str = "Standard",
        team_experience: str = "Medium",
    ) -> Dict[str, Any]:
        """
        Calculates COCOMO II parametric effort, duration, and comparison metrics.
        """
        # 1. Estimate Equivalent KSLOC from feature portfolio
        total_ksloc = 0.0
        for f in features:
            comp = f.get("complexity", overall_complexity)
            ksloc = self.KSLOC_PER_FEATURE.get(comp, 1.5)
            total_ksloc += ksloc

        if total_ksloc <= 0:
            total_ksloc = len(features) * 1.5 if features else 15.0

        total_ksloc = round(total_ksloc, 2)

        # 2. Scale Factor B computation (nominal 1.06)
        scale_factors = {
            "precedentedness": 3.72,        # Nominal
            "development_flexibility": 3.04, # Nominal
            "architecture_risk_resolution": 4.24,
            "team_cohesion": 3.29,
            "process_maturity": 4.68,
        }
        sum_sf = sum(scale_factors.values())
        b_exponent = round(0.91 + 0.01 * sum_sf, 4)

        # 3. Effort Multipliers (Cost Drivers)
        cost_drivers = {}
        # Platform Difficulty
        if "Mobile" in platform or "Multi-Platform" in platform:
            cost_drivers["platform_difficulty"] = 1.15
        elif "Enterprise" in platform or "Distributed" in platform:
            cost_drivers["platform_difficulty"] = 1.10
        else:
            cost_drivers["platform_difficulty"] = 1.00

        # Quality / Reliability Requirement
        if quality_requirement.lower() in ["high", "mission-critical", "strict"]:
            cost_drivers["reliability_requirement"] = 1.15
        elif quality_requirement.lower() in ["relaxed", "mvp"]:
            cost_drivers["reliability_requirement"] = 0.88
        else:
            cost_drivers["reliability_requirement"] = 1.00

        # Team Capability
        if team_experience.lower() in ["senior", "high"]:
            cost_drivers["team_capability"] = 0.88
        elif team_experience.lower() in ["junior", "low"]:
            cost_drivers["team_capability"] = 1.18
        else:
            cost_drivers["team_capability"] = 1.00

        # Compound Effort Multiplier
        eaf = 1.0
        for val in cost_drivers.values():
            eaf *= val
        eaf = round(eaf, 4)

        # 4. Parametric Effort in Person-Months and Hours
        effort_pm = round(self.nominal_a * (total_ksloc ** b_exponent) * eaf, 2)
        effort_hours = round(effort_pm * self.hours_per_person_month, 1)

        # 5. Parametric Schedule Duration
        d_exponent = round(0.28 + 0.2 * (b_exponent - 0.91), 4)
        duration_months = round(self.nominal_c * (effort_pm ** d_exponent), 2)
        duration_calendar_days = math.ceil(duration_months * 30.4)

        # Average recommended staff
        avg_team_size = round(effort_pm / max(1.0, duration_months), 1)

        return {
            "model_name": "COCOMO II Parametric Early Architecture Model",
            "equivalent_ksloc": total_ksloc,
            "equivalent_sloc": int(total_ksloc * 1000),
            "scale_exponent_b": b_exponent,
            "effort_adjustment_factor_eaf": eaf,
            "cost_drivers": cost_drivers,
            "parametric_effort_person_months": effort_pm,
            "parametric_effort_hours": effort_hours,
            "parametric_duration_months": duration_months,
            "parametric_calendar_days": duration_calendar_days,
            "recommended_average_staff_fte": avg_team_size,
            "equations_reference": (
                "Effort (PM) = 2.94 * (KSLOC)^1.06 * EAF; "
                "Duration (Months) = 3.67 * (Effort_PM)^0.31; "
                "1 PM = 152 productive hours."
            ),
            "calibration_notes": (
                "COCOMO II equations calibrated against standardized modern software modules. "
                "KSLOC derived from functional feature count and complexity."
            ),
        }


parametric_cocomo_engine = ParametricCOCOMOEngine()
