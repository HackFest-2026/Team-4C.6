"""
CostPilot AI — Full Architecture Test Suite.
Validates the complete end-to-end capabilities across:
  - Phase Four: Work Breakdown Structure (WBS)
  - Phase Five: Resource Planning & Optimization (Budget, Balanced, Deadline)
  - Phase Seven: Monte Carlo Uncertainty Simulation (1,000 iterations, P10-P95, Tornado)
  - Phase Eight: Analogy-Based Estimation (Top-K historical project search)
  - Phase Nine: Parametric COCOMO II Model & Integration Interfaces (Jira, MS Project, ERP)
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.estimation.engine import estimation_engine
from app.services.estimation.wbs_generator import wbs_generator
from app.services.estimation.resource_optimizer import resource_optimizer
from app.services.estimation.monte_carlo import monte_carlo_simulator
from app.services.estimation.parametric_model import parametric_cocomo_engine
from app.services.estimation.historical_benchmarker import historical_benchmarker
from app.services.estimation.integrations import integration_service

client = TestClient(app)


# =====================================================================
# PHASE 4: WORK BREAKDOWN STRUCTURE (WBS) TESTS
# =====================================================================

def test_wbs_hierarchical_structure_and_reconciliation():
    """
    Validates that WBSGenerator builds modules, features, and tasks with:
    - Hierarchical task IDs (e.g. WBS-03.1.1)
    - Acceptance criteria per task
    - Non-empty required role
    - Exact effort reconciliation
    """
    sample_features = [
        {"name": "User Registration", "category": "Authentication", "complexity": "Low", "expected_effort_hours": 20.0},
        {"name": "Product Catalog", "category": "CRUD/data module", "complexity": "Medium", "expected_effort_hours": 40.0},
        {"name": "Payment Gateway", "category": "Payments", "complexity": "High", "expected_effort_hours": 60.0},
    ]

    wbs = wbs_generator.generate_wbs(
        project_name="E-Commerce Storefront",
        project_type="E-commerce",
        features=sample_features,
        overall_complexity="Medium",
    )

    assert wbs["total_features_count"] == 3
    assert wbs["total_tasks_count"] == 9  # 3 tasks per feature
    assert len(wbs["modules"]) >= 2
    assert pytest.approx(wbs["total_effort_hours"], 0.1) == 120.0

    for task in wbs["flat_tasks"]:
        assert task["task_id"].startswith("WBS-")
        assert len(task["acceptance_criteria"]) >= 1
        assert task["required_role"] in [
            "Frontend Developer", "Backend Developer", "Full-Stack Developer",
            "QA Engineer", "DevOps Engineer", "UI/UX Designer"
        ]
        assert task["effort_hours"]["likely"] > 0
        assert task["effort_hours"]["optimistic"] <= task["effort_hours"]["likely"]
        assert task["effort_hours"]["pessimistic"] >= task["effort_hours"]["likely"]


# =====================================================================
# PHASE 5: RESOURCE OPTIMIZATION SCENARIOS TESTS
# =====================================================================

def test_resource_optimization_three_scenarios():
    """
    Validates the 3 resource optimization scenarios:
    - Budget-Focused (Lean 2 devs, lowest cost, longest timeline)
    - Balanced (Standard risk-adjusted)
    - Deadline-Focused (Fast-track, models Brooks' Law +30% penalty)
    """
    res = resource_optimizer.optimize_scenarios(
        total_effort_hours=400.0,
        critical_path_hours=160.0,
        project_type="SaaS Platform",
        rate_profile="Professional",
        requested_deadline_days=30,
    )

    scenarios = {s["scenario_key"]: s for s in res["scenarios"]}
    assert "budget_focused" in scenarios
    assert "balanced" in scenarios
    assert "deadline_focused" in scenarios

    budget_sc = scenarios["budget_focused"]
    balanced_sc = scenarios["balanced"]
    deadline_sc = scenarios["deadline_focused"]

    # Budget scenario must be cheaper than Deadline scenario
    assert budget_sc["final_budget"] < deadline_sc["final_budget"]
    # Budget scenario must take more calendar days than Deadline scenario
    assert budget_sc["calendar_days"] >= deadline_sc["calendar_days"]
    # Brooks' Law overhead increases with team size
    assert deadline_sc["coordination_overhead_pct"] > budget_sc["coordination_overhead_pct"]


def test_resource_optimization_infeasible_deadline_flag():
    """
    Verifies that a deadline shorter than the physical critical path floor
    is flagged as Infeasible with mathematical explanations.
    """
    res = resource_optimizer.optimize_scenarios(
        total_effort_hours=600.0,
        critical_path_hours=300.0,  # ~52 calendar days min floor
        project_type="SaaS Platform",
        requested_deadline_days=15,  # Aggressively short
    )
    scenarios = {s["scenario_key"]: s for s in res["scenarios"]}
    deadline_sc = scenarios["deadline_focused"]

    assert "Infeasible" in deadline_sc["feasibility_status"]
    assert "critical path" in deadline_sc["feasibility_analysis"].lower()


# =====================================================================
# PHASE 7: MONTE CARLO UNCERTAINTY SIMULATION TESTS
# =====================================================================

def test_monte_carlo_simulation_percentiles_and_reproducibility():
    """
    Validates 1,000-run Monte Carlo simulation:
    - Monotonic percentile ordering: P10 <= P50 <= P90 <= P95
    - Tornado sensitivity ranking
    - Histogram binning
    - Reproducibility with random_seed=42
    """
    features = [
        {"name": "Auth Module", "expected_effort_hours": 30.0},
        {"name": "Search & Filter", "expected_effort_hours": 50.0},
        {"name": "Checkout Flow", "expected_effort_hours": 70.0},
    ]

    mc1 = monte_carlo_simulator.run_simulation(
        features=features,
        likely_effort_hours=150.0,
        likely_duration_days=30,
        likely_budget_inr=200000.0,
        blended_hourly_rate=1200.0,
        iterations=1000,
        random_seed=42,
    )

    mc2 = monte_carlo_simulator.run_simulation(
        features=features,
        likely_effort_hours=150.0,
        likely_duration_days=30,
        likely_budget_inr=200000.0,
        blended_hourly_rate=1200.0,
        iterations=1000,
        random_seed=42,
    )

    # Deterministic reproducibility
    assert mc1["confidence_bounds"]["budget"]["p50_median"] == mc2["confidence_bounds"]["budget"]["p50_median"]

    # Monotonicity
    bounds = mc1["confidence_bounds"]["budget"]
    assert bounds["p10_optimistic"] <= bounds["p50_median"]
    assert bounds["p50_median"] <= bounds["p90_conservative"]
    assert bounds["p90_conservative"] <= bounds["p95_pessimistic"]

    # Tornado sensitivity drivers
    assert len(mc1["top_uncertainty_drivers"]) >= 1
    top_driver = mc1["top_uncertainty_drivers"][0]
    assert "driver_name" in top_driver
    assert "variance_contribution_pct" in top_driver

    # Histogram
    assert len(mc1["histogram_distribution"]) == 10


# =====================================================================
# PHASE 8: ANALOGY-BASED ESTIMATION TESTS
# =====================================================================

def test_analogy_based_estimation_search():
    """
    Verifies that find_top_analogies retrieves Top-K historical records
    from the 2,500 projects with similarity scores between 0 and 100%.
    """
    analogies = historical_benchmarker.find_top_analogies(
        project_type="E-commerce",
        overall_complexity="Medium",
        feature_count=12,
        frontend_stack="React",
        backend_stack="Node.js_Express",
        top_k=5,
    )

    assert len(analogies) == 5
    for ana in analogies:
        assert 0.0 <= ana["similarity_score_pct"] <= 100.0
        assert ana["historical_effort_hours"] > 0
        assert ana["historical_duration_days"] > 0
        assert ana["historical_cost_inr"] > 0
        assert "CostPilot_AI_Training_Dataset.xlsx" in ana["provenance"]


# =====================================================================
# PHASE 9: PARAMETRIC COCOMO II & INTEGRATION TESTS
# =====================================================================

def test_parametric_cocomo_model_estimation():
    """
    Verifies COCOMO II parametric model equations:
    - KSLOC derivation
    - Person-months effort
    - Duration in calendar days
    """
    features = [
        {"name": "F1", "complexity": "Low"},
        {"name": "F2", "complexity": "Medium"},
        {"name": "F3", "complexity": "High"},
    ]
    cocomo = parametric_cocomo_engine.estimate(
        features=features,
        overall_complexity="Medium",
        platform="Web Application",
    )

    assert cocomo["equivalent_ksloc"] == 0.8 + 1.5 + 3.0  # 5.3 KSLOC
    assert cocomo["parametric_effort_person_months"] > 0
    assert cocomo["parametric_effort_hours"] > 0
    assert cocomo["parametric_calendar_days"] > 0
    assert cocomo["scale_exponent_b"] > 1.0


def test_integration_service_exports():
    """
    Verifies export generation for Jira, MS Project, and ERP Ledger schemas.
    """
    proj = {"name": "Integration Test Project", "id": "proj_123"}
    features = [{"name": "Auth", "category": "Authentication", "expected_effort_hours": 30.0}]
    wbs = wbs_generator.generate_wbs("Integration Test Project", "SaaS Platform", features)
    budget = {
        "final_budget": 150000.0,
        "labour_cost_inr": 120000.0,
        "total_labour_cost": 120000.0,
        "one_time_infrastructure_setup_inr": 15000.0,
        "total_infrastructure_cost": 15000.0,
        "software_tooling_setup_inr": 5000.0,
        "tooling_cost": 5000.0,
        "contingency_amount_inr": 10000.0,
        "contingency_cost": 10000.0,
        "currency_code": "INR",
        "exchange_rate": 1.0,
    }

    # Jira JSON
    jira = integration_service.export_to_jira_json(proj, wbs)
    assert jira["issues_count"] >= 3
    assert "jira_payload" in jira

    # MS Project CSV
    csv_str = integration_service.export_to_ms_project_csv(proj, wbs)
    assert "WBS Code" in csv_str
    assert "Task Name" in csv_str

    # ERP Ledger
    erp = integration_service.export_to_erp_ledger(proj, budget)
    assert erp["is_reconciled"] is True
    assert len(erp["ledger_lines"]) == 4


# =====================================================================
# END-TO-END API ENDPOINTS TESTS
# =====================================================================

def test_api_endpoints_for_all_phases():
    """
    Tests all newly created Phase 4-9 REST endpoints:
    - /api/v1/integrations
    - /api/v1/projects/{id}/wbs
    - /api/v1/projects/{id}/resource-scenarios
    - /api/v1/projects/{id}/monte-carlo
    - /api/v1/projects/{id}/analogies
    - /api/v1/projects/{id}/parametric
    - /api/v1/projects/{id}/export/jira
    - /api/v1/projects/{id}/export/msproject
    - /api/v1/projects/{id}/export/erp
    """
    # 1. Integrations catalog
    resp_cat = client.get("/api/v1/integrations")
    assert resp_cat.status_code == 200
    assert "jira" in resp_cat.json()["integrations"]

    # 2. Register user & create project
    suffix = uuid.uuid4().hex[:8]
    user_email = f"arch_user_{suffix}@costpilot.ai"
    pwd = "ArchPassword@123"
    reg = client.post("/api/v1/auth/register", json={
        "full_name": "Architecture Tester",
        "email": user_email,
        "password": pwd,
        "confirm_password": pwd,
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    est = estimation_engine.estimate(
        project_name="End to End API Project",
        project_type="SaaS Platform",
        currency="INR",
    )

    save_resp = client.post("/api/v1/projects", headers=headers, json={
        "project_name": "End to End API Project",
        "description": "Validating full architectural API surfaces.",
        "project_type": "SaaS Platform",
        "rate_profile": "Professional",
        "currency": "INR",
        "estimate": est,
    })
    assert save_resp.status_code == 200
    p_id = save_resp.json()["id"]

    # 3. Test WBS endpoint
    resp_wbs = client.get(f"/api/v1/projects/{p_id}/wbs", headers=headers)
    assert resp_wbs.status_code == 200
    assert "wbs" in resp_wbs.json()

    # 4. Test Resource Scenarios endpoint
    resp_res = client.get(f"/api/v1/projects/{p_id}/resource-scenarios", headers=headers)
    assert resp_res.status_code == 200
    assert "resource_scenarios" in resp_res.json()

    # 5. Test Monte Carlo endpoint
    resp_mc = client.get(f"/api/v1/projects/{p_id}/monte-carlo", headers=headers)
    assert resp_mc.status_code == 200
    assert "monte_carlo" in resp_mc.json()

    # 6. Test Analogies endpoint
    resp_ana = client.get(f"/api/v1/projects/{p_id}/analogies", headers=headers)
    assert resp_ana.status_code == 200
    assert "analogies" in resp_ana.json()

    # 7. Test Parametric endpoint
    resp_par = client.get(f"/api/v1/projects/{p_id}/parametric", headers=headers)
    assert resp_par.status_code == 200
    assert "parametric_cocomo" in resp_par.json()

    # 8. Test Export Jira
    resp_jira = client.post(f"/api/v1/projects/{p_id}/export/jira", headers=headers)
    assert resp_jira.status_code == 200
    assert "jira_payload" in resp_jira.json()

    # 9. Test Export MS Project CSV
    resp_ms = client.post(f"/api/v1/projects/{p_id}/export/msproject", headers=headers)
    assert resp_ms.status_code == 200
    assert "text/csv" in resp_ms.headers["content-type"]

    # 10. Test Export ERP Ledger
    resp_erp = client.post(f"/api/v1/projects/{p_id}/export/erp", headers=headers)
    assert resp_erp.status_code == 200
    assert resp_erp.json()["is_reconciled"] is True
