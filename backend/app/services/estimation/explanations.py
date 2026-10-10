from typing import Dict, Any, List


class ExplanationGenerator:
    """
    Generates transparent, defensible, natural-language explanations
    for all drivers, assumptions, adjustments, and reconciliation factors.
    """

    def generate(
        self,
        features_estimated: List[Dict[str, Any]],
        platform_name: str,
        platform_multiplier: float,
        fixed_work_hours: float,
        total_effort_hours: float,
        ml_effort_hours: float,
        ml_cost_inr: float,
        likely_cost_inr: float,
        rate_profile: str,
        contingency_pct: float,
        timeline_data: Dict[str, Any],
        risk_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        # 1. Top Effort Drivers
        sorted_features = sorted(
            features_estimated,
            key=lambda x: x.get("expected_effort_hours", 0.0),
            reverse=True,
        )
        top_drivers = []
        for f in sorted_features[:4]:
            top_drivers.append({
                "feature_name": f.get("feature_name"),
                "expected_hours": f.get("expected_effort_hours"),
                "complexity": f.get("complexity"),
                "method": f.get("estimation_method"),
                "rationale": f"Accounts for {round((f.get('expected_effort_hours', 0.0) / max(1.0, total_effort_hours)) * 100, 1)}% of total effort.",
            })

        # 2. Platform Adjustment Explanation
        if platform_multiplier > 1.0:
            platform_explanation = (
                f"Platform target '{platform_name}' applies a client-side multiplier of {platform_multiplier}x. "
                f"Crucially, backend engineering effort remains uninflated ({1.0}x), ensuring we do not double-count shared APIs and databases."
            )
        else:
            platform_explanation = (
                f"Platform target '{platform_name}' uses standard 1.0x single-target client effort. No cross-platform overhead required."
            )

        # 3. Effort Reconciliation Explanation
        reconciliation_notes = []
        if ml_effort_hours and ml_effort_hours > 0:
            diff_hours = abs(total_effort_hours - ml_effort_hours)
            diff_pct = round((diff_hours / total_effort_hours) * 100, 1)
            if diff_pct > 35.0:
                reconciliation_notes.append(
                    f"Noticeable divergence: Bottom-up feature sum ({total_effort_hours:.1f}h) differs from top-down ML prediction ({ml_effort_hours:.1f}h) by {diff_pct}%. "
                    f"CostPilot prioritizes the bottom-up feature-by-feature breakdown as authoritative and uses the ML prediction as a macro sanity check."
                )
            else:
                reconciliation_notes.append(
                    f"Strong alignment: Bottom-up feature sum ({total_effort_hours:.1f}h) is consistent with macro ML model benchmark ({ml_effort_hours:.1f}h) within {diff_pct}%."
                )
        else:
            reconciliation_notes.append("ML benchmark model was offline; bottom-up feature catalog was solely used.")

        # 4. Schedule and Capacity Rationale
        if not timeline_data.get("is_timeline_feasible", True):
            schedule_note = timeline_data.get("feasibility_warning")
        else:
            schedule_note = (
                f"Feasible timeline of {timeline_data.get('min_feasible_calendar_days')} to {timeline_data.get('likely_calendar_days')} calendar days "
                f"based on critical path of {timeline_data.get('critical_path_calendar_days')} days and team size of {timeline_data.get('team_size')}."
            )

        # 5. Provenance & Limitations Disclaimer
        provenance_disclaimer = (
            "ESTIMATION METHODOLOGY & PROVENANCE NOTICE: "
            "Model benchmarks and historical feature distributions were derived from the simulated CostPilot AI training dataset. "
            "These represent rigorous engineering models, not guaranteed vendor quotes. "
            "Actual client invoices and third-party API usage must be validated during sprint planning."
        )

        return {
            "top_effort_drivers": top_drivers,
            "platform_explanation": platform_explanation,
            "fixed_project_work_explanation": (
                f"Included {fixed_work_hours}h of shared foundation activities (kickoff, repo/environment setup, CI/CD pipeline, and architecture documentation) "
                f"not covered by individual feature items."
            ),
            "reconciliation_explanation": " ".join(reconciliation_notes),
            "schedule_explanation": schedule_note,
            "rate_profile_explanation": f"Applied {rate_profile} rate schedule in Indian Rupees (INR) with role-specialized rate differentials.",
            "contingency_explanation": (
                f"Contingency buffer of {contingency_pct}% applied exactly once to pre-contingency build total to buffer against discovery unknowns."
            ),
            "provenance_and_limitations": provenance_disclaimer,
        }


explanation_generator = ExplanationGenerator()
