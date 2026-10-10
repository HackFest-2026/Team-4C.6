import logging
import math
from typing import Dict, Any, List, Optional

from app.core.config import settings
from app.services.estimation.feature_effort import feature_effort_engine
from app.services.estimation.complexity import complexity_analyzer
from app.services.estimation.dependency_graph import DependencyGraph, CircularDependencyError
from app.services.estimation.team_timeline import team_timeline_engine
from app.services.estimation.cost_budget import cost_budget_engine
from app.services.estimation.risk_scoring import risk_scoring_engine
from app.services.estimation.explanations import explanation_generator
from app.services.ml.predictor import project_predictor
from app.services.ml.model_registry import model_registry

logger = logging.getLogger(__name__)


class EstimationEngine:
    """
    Authoritative Estimation Engine for CostPilot AI.
    Every estimate, recalculation, comparison, and what-if scenario invokes this service.
    """

    def __init__(self):
        self.version = "2.0.0"

    def estimate_project(self, project_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the full authoritative 23-step estimation sequence.
        """
        # Step 1: Validate project inputs
        project_name = str(project_input.get("name") or project_input.get("project_name") or "Untitled Project").strip()
        project_type = str(project_input.get("project_type") or "SaaS Web Application").strip()
        overall_complexity = str(project_input.get("overall_complexity") or project_input.get("complexity") or "Medium").strip()
        description = str(project_input.get("description") or "").strip()
        platform_name = str(project_input.get("hosting_platform") or project_input.get("platform") or "Web").strip()
        
        # Team & Deadline constraints
        team_size = int(project_input.get("team_size", 4))
        requested_deadline_days = project_input.get("deadline_days") or project_input.get("target_deadline_days")
        if requested_deadline_days is not None:
            try:
                requested_deadline_days = int(requested_deadline_days)
            except (ValueError, TypeError):
                requested_deadline_days = None

        rate_profile = str(project_input.get("rate_profile") or "Professional").strip()
        custom_rates = project_input.get("custom_rates") or {}
        custom_role_allocations = project_input.get("custom_role_allocations") or None
        
        # Financial params
        contingency_rate = float(project_input.get("contingency_pct") or settings.DEFAULT_CONTINGENCY_PCT)
        if contingency_rate > 1.0:  # in case user passed 15 instead of 0.15
            contingency_rate /= 100.0
        
        one_time_infra_inr = float(project_input.get("one_time_infra_inr", 25000.0))
        tooling_setup_inr = float(project_input.get("tooling_setup_inr", 15000.0))
        other_direct_costs_inr = float(project_input.get("other_direct_costs_inr", 0.0))

        # Step 2: Validate features and identifiers
        raw_features = project_input.get("features", []) or []
        if not raw_features:
            # Fallback default feature if empty list provided
            raw_features = [
                {
                    "id": "feat_1",
                    "name": "Core Application Module",
                    "category": "CRUD/data module",
                    "complexity": overall_complexity,
                    "dependencies": [],
                    "reuse_level_pct": 0.0,
                    "integration_count": 0,
                }
            ]

        # Step 3 & 4: Dependency Graph and DAG Validation
        sanitized_features = []
        for i, f in enumerate(raw_features):
            feat_copy = dict(f)
            feat_copy["id"] = str(feat_copy.get("id") or f"feat_{i+1}")
            sanitized_features.append(feat_copy)

        dep_graph = DependencyGraph(sanitized_features)
        dep_graph.validate()  # Throws CircularDependencyError if cyclic

        # Step 5 & 6: Feature-Level O/M/P Estimation
        estimated_features = []
        fallback_count = 0
        sum_features_expected = 0.0
        sum_features_opt = 0.0
        sum_features_pess = 0.0

        for f in sanitized_features:
            # Complexity determination
            comp = f.get("complexity")
            if not comp or comp not in ("Low", "Medium", "High", "Very High") or comp == "Auto":
                factor_scores = f.get("factor_scores")
                if factor_scores and isinstance(factor_scores, dict):
                    _, comp, _ = complexity_analyzer.evaluate_9_factors(factor_scores)
                elif overall_complexity in ("Low", "Medium", "High", "Very High"):
                    comp = overall_complexity
                else:
                    comp = complexity_analyzer.suggest_complexity(f.get("name", ""), f.get("description", ""))

            est = feature_effort_engine.estimate_feature(
                name=f.get("name", "Untitled Feature"),
                category=f.get("category"),
                complexity=comp,
                reuse_level_pct=float(f.get("reuse_level_pct", 0.0)),
                integration_count=int(f.get("integration_count", len(f.get("integration_requirements", [])))),
                notes=f.get("description", ""),
            )
            est["id"] = f["id"]
            est["dependencies"] = f.get("dependencies", [])

            if est["estimation_method"] == "generic_fallback":
                fallback_count += 1

            estimated_features.append(est)
            sum_features_expected += est["expected_effort_hours"]
            sum_features_opt += est["optimistic_effort_hours"]
            sum_features_pess += est["pessimistic_effort_hours"]

        # Step 7 & 8: Platform Adjustment (Applied ONLY to client-side effort)
        # Default architecture split: 40% client-side / UI, 60% backend / API / database
        platform_multiplier = settings.PLATFORM_MULTIPLIERS.get(platform_name, 1.0)
        client_ratio = 0.40
        backend_ratio = 0.60

        adjusted_features_expected = (sum_features_expected * backend_ratio) + (sum_features_expected * client_ratio * platform_multiplier)
        adjusted_features_opt = (sum_features_opt * backend_ratio) + (sum_features_opt * client_ratio * platform_multiplier)
        adjusted_features_pess = (sum_features_pess * backend_ratio) + (sum_features_pess * client_ratio * platform_multiplier)

        # Step 9: Add Fixed Project-Level Work (Foundation activities)
        # Setup, CI/CD, deployment, baseline docs scaled by overall project complexity
        complexity_foundation_factors = {
            "Low": 0.85,
            "Medium": 1.00,
            "High": 1.25,
            "Very High": 1.55,
        }
        comp_scale = complexity_foundation_factors.get(overall_complexity, 1.00)
        base_fixed = 48.0 * comp_scale
        fixed_work_hours = round(min(base_fixed, max(16.0 * comp_scale, sum_features_expected * 0.15 * comp_scale)), 1)
        fixed_opt = round(fixed_work_hours * 0.75, 1)
        fixed_pess = round(fixed_work_hours * 1.50, 1)

        # Step 10: Total Expected Effort
        total_effort_expected = round(adjusted_features_expected + fixed_work_hours, 1)
        total_effort_opt = round(adjusted_features_opt + fixed_opt, 1)
        total_effort_pess = round(adjusted_features_pess + fixed_pess, 1)

        # Step 11: Machine Learning Top-Down Benchmark & Reconciliation
        ml_inputs = {
            "project_type": project_type,
            "project_complexity": overall_complexity,
            "feature_count": len(estimated_features),
            "website_pages_or_screens": project_input.get("pages_or_screens", max(5, len(estimated_features))),
            "frontend_stack": project_input.get("frontend_stack", "React"),
            "backend_stack": project_input.get("backend_stack", "Node.js_Express"),
            "database": project_input.get("database", "PostgreSQL"),
            "hosting_platform": project_input.get("hosting_platform", "AWS"),
            "expected_user_band": project_input.get("user_band", "1k-10k"),
            "integration_count": sum(f.get("integration_count", 0) for f in estimated_features),
            "user_role_count": project_input.get("user_role_count", 2),
            "deadline_pressure": project_input.get("deadline_pressure", "Moderate"),
            "quality_requirement": project_input.get("quality_requirement", "Standard"),
            "client_region": project_input.get("client_region", "India"),
        }
        ml_prediction = project_predictor.predict_project(ml_inputs)
        ml_effort_benchmark = ml_prediction["predictions"].get("estimated_effort_hours", 0.0)
        ml_cost_benchmark = ml_prediction["predictions"].get("estimated_cost_inr", 0.0)

        # Effort reconciliation notice (never add them together)
        reconciliation_discrepancy_pct = 0.0
        reconciliation_warning = None
        if ml_effort_benchmark > 0:
            reconciliation_discrepancy_pct = round(
                abs(total_effort_expected - ml_effort_benchmark) / total_effort_expected * 100.0, 1
            )
            if reconciliation_discrepancy_pct > 35.0:
                reconciliation_warning = (
                    f"Effort Discrepancy Warning: Bottom-up feature sum ({total_effort_expected}h) diverges "
                    f"from top-down ML prediction ({ml_effort_benchmark}h) by {reconciliation_discrepancy_pct}%. "
                    f"Check individual feature complexities or scope details."
                )

        # Step 12: Role Allocations (guaranteed to sum to total_effort_expected)
        role_allocations = team_timeline_engine.calculate_role_allocations(
            total_effort_hours=total_effort_expected,
            project_type=project_type,
            custom_profile=custom_role_allocations,
        )

        # Step 14 & 15: Critical Path & Graph Depth
        critical_path_hours, critical_path_nodes, max_depth = dep_graph.calculate_critical_path(
            effort_key="expected_effort_hours"
        )

        # Step 13 & 16: Staffing Capacity and Timeline Feasibility
        timeline_data = team_timeline_engine.calculate_timeline_and_capacity(
            total_effort_hours=total_effort_expected,
            critical_path_hours=critical_path_hours,
            team_size=team_size,
            requested_deadline_days=requested_deadline_days,
            role_allocations=role_allocations,
        )

        # Step 17, 18, 19, 20: Cost Engine and Budget Range
        role_rates = cost_budget_engine.get_role_rates(rate_profile, custom_rates)
        budget_data = cost_budget_engine.calculate_budget(
            total_effort_hours=total_effort_expected,
            optimistic_hours=total_effort_opt,
            pessimistic_hours=total_effort_pess,
            role_allocations=role_allocations,
            role_rates=role_rates,
            one_time_infra_inr=one_time_infra_inr,
            tooling_setup_inr=tooling_setup_inr,
            other_direct_costs_inr=other_direct_costs_inr,
            contingency_rate=contingency_rate,
        )

        # Step 21: Risk Scoring and Confidence
        total_integrations = sum(f.get("integration_count", 0) for f in estimated_features)
        risk_data = risk_scoring_engine.calculate_risk(
            complexity_level=overall_complexity,
            deadline_pressure=str(project_input.get("deadline_pressure", "Moderate")),
            max_dependency_depth=max_depth,
            integration_count=total_integrations,
            security_requirement=str(project_input.get("quality_requirement", "Standard")),
            platform_multiplier=platform_multiplier,
            team_size=team_size,
            is_timeline_feasible=timeline_data["is_timeline_feasible"],
            fallback_features_count=fallback_count,
            total_features_count=len(estimated_features),
        )

        confidence_data = risk_scoring_engine.calculate_confidence(
            has_project_description=bool(description and len(description) > 10),
            feature_count=len(estimated_features),
            fallback_features_count=fallback_count,
            is_timeline_feasible=timeline_data["is_timeline_feasible"],
            ml_model_available=model_registry.is_model_available("target_estimated_cost_inr"),
        )

        # Step 22: Explanations and Assumptions
        explanations = explanation_generator.generate(
            features_estimated=estimated_features,
            platform_name=platform_name,
            platform_multiplier=platform_multiplier,
            fixed_work_hours=fixed_work_hours,
            total_effort_hours=total_effort_expected,
            ml_effort_hours=ml_effort_benchmark,
            ml_cost_inr=ml_cost_benchmark,
            likely_cost_inr=budget_data["final_build_budget_inr"],
            rate_profile=rate_profile,
            contingency_pct=budget_data["contingency_pct"],
            timeline_data=timeline_data,
            risk_data=risk_data,
        )

        # Step 23: Return Authoritative Structured Estimate
        return {
            "project_name": project_name,
            "project_type": project_type,
            "overall_complexity": overall_complexity,
            "platform": platform_name,
            "platform_multiplier": platform_multiplier,
            "engine_version": self.version,
            "features": estimated_features,
            "feature_count": len(estimated_features),
            "effort": {
                "features_subtotal_hours": round(sum_features_expected, 1),
                "platform_adjusted_features_hours": round(adjusted_features_expected, 1),
                "fixed_foundation_hours": fixed_work_hours,
                "total_expected_effort_hours": total_effort_expected,
                "optimistic_effort_hours": total_effort_opt,
                "pessimistic_effort_hours": total_effort_pess,
                "three_point_standard_deviation_hours": round((total_effort_pess - total_effort_opt) / 6.0, 2),
            },
            "ml_benchmark": {
                "ml_effort_hours": ml_effort_benchmark,
                "ml_cost_inr": ml_cost_benchmark,
                "discrepancy_pct": reconciliation_discrepancy_pct,
                "reconciliation_warning": reconciliation_warning,
                "provenance": ml_prediction.get("provenance"),
            },
            "role_allocations": role_allocations,
            "timeline": timeline_data,
            "critical_path": {
                "critical_path_hours": critical_path_hours,
                "critical_path_features": critical_path_nodes,
                "dependency_depth": max_depth,
            },
            "budget": budget_data,
            "risk": risk_data,
            "confidence": confidence_data,
            "explanations": explanations,
            "inputs_echo": {
                "team_size": team_size,
                "rate_profile": rate_profile,
                "contingency_pct": contingency_rate,
                "deadline_days": requested_deadline_days,
            },
        }


estimation_engine = EstimationEngine()
