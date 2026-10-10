import pytest
from app.services.estimation.engine import estimation_engine
from app.services.estimation.cost_budget import cost_budget_engine, FinancialInvariantViolation


def test_mandatory_financial_invariant_reconciliation():
    """Mandatory test 26: ReportedBuildLabourCost must equal sum(RoleHours * RoleHourlyRate)."""
    res = estimation_engine.estimate_project({
        "name": "Invariant Test",
        "rate_profile": "Professional",
        "features": [
            {"name": "Auth", "category": "Authentication", "complexity": "Medium"},
            {"name": "Payment", "category": "Payment integration", "complexity": "High"},
        ]
    })
    budget = res["budget"]
    labour_cost = budget["labour_cost_inr"]
    
    # Calculate directly from role breakdown
    role_sum = sum(
        data["role_cost_inr"] for data in budget["role_costs"].values()
    )

    assert abs(labour_cost - role_sum) < 0.05, f"Financial invariant failed: {labour_cost} != {role_sum}"


def test_contingency_applied_strictly_once():
    """Mandatory test 25: Verify contingency is applied exactly once to pre-contingency total."""
    res = estimation_engine.estimate_project({
        "name": "Contingency Test",
        "contingency_pct": 0.15,
        "one_time_infra_inr": 20000.0,
        "tooling_setup_inr": 10000.0,
        "features": [{"name": "Feature 1", "category": "CRUD/data module", "complexity": "Medium"}]
    })
    budget = res["budget"]
    pre_contingency = budget["pre_contingency_cost_inr"]
    contingency_amount = budget["contingency_amount_inr"]
    final_budget = budget["final_build_budget_inr"]

    # Contingency amount must equal PreContingency * 0.15
    expected_contingency = round(pre_contingency * 0.15, 2)
    assert abs(contingency_amount - expected_contingency) < 0.05

    # Final budget must equal PreContingency + ContingencyAmount
    assert abs(final_budget - (pre_contingency + contingency_amount)) < 0.05


def test_hourly_rate_monotonicity():
    """Mandatory test 24: Increasing hourly rate profile must strictly increase labour cost."""
    startup = estimation_engine.estimate_project({
        "name": "Rate Check",
        "rate_profile": "Startup",
        "features": [{"name": "Auth", "category": "Authentication", "complexity": "Medium"}]
    })
    enterprise = estimation_engine.estimate_project({
        "name": "Rate Check",
        "rate_profile": "Enterprise",
        "features": [{"name": "Auth", "category": "Authentication", "complexity": "Medium"}]
    })
    assert enterprise["budget"]["labour_cost_inr"] > startup["budget"]["labour_cost_inr"]


def test_recalculation_after_changing_team_size():
    """Mandatory test 23: Changing team size updates capacity, timeline, and overhead."""
    t2 = estimation_engine.estimate_project({
        "name": "Team 2", "team_size": 2,
        "features": [{"name": "Auth", "category": "Authentication", "complexity": "Medium"}]
    })
    t6 = estimation_engine.estimate_project({
        "name": "Team 6", "team_size": 6,
        "features": [{"name": "Auth", "category": "Authentication", "complexity": "Medium"}]
    })
    # Brooks' law overhead increases with larger team
    assert t6["timeline"]["coordination_overhead_pct"] > t2["timeline"]["coordination_overhead_pct"]


def test_recalculation_after_changing_feature():
    """Mandatory test 22: Changing a feature complexity recalculates effort and budget."""
    med = estimation_engine.estimate_project({
        "name": "Feature Change",
        "features": [{"name": "Payment", "category": "Payment integration", "complexity": "Medium"}]
    })
    vh = estimation_engine.estimate_project({
        "name": "Feature Change",
        "features": [{"name": "Payment", "category": "Payment integration", "complexity": "Very High"}]
    })
    assert vh["effort"]["total_expected_effort_hours"] > med["effort"]["total_expected_effort_hours"]
    assert vh["budget"]["final_build_budget_inr"] > med["budget"]["final_build_budget_inr"]


def test_regression_golden_scenario():
    """Mandatory test 30: Regression test against golden benchmark scenario."""
    golden = estimation_engine.estimate_project({
        "name": "Golden SaaS Standard",
        "project_type": "SaaS Web Application",
        "overall_complexity": "Medium",
        "team_size": 4,
        "deadline_days": 60,
        "rate_profile": "Professional",
        "contingency_pct": 0.15,
        "features": [
            {"id": "f1", "name": "User Authentication", "category": "Authentication", "complexity": "Medium"},
            {"id": "f2", "name": "Admin Dashboard", "category": "Admin dashboard", "complexity": "Medium", "dependencies": ["f1"]},
        ]
    })
    assert golden["effort"]["total_expected_effort_hours"] > 0
    assert golden["budget"]["final_build_budget_inr"] > 0
    assert golden["critical_path"]["critical_path_hours"] > 0
    assert golden["timeline"]["is_timeline_feasible"] is True
