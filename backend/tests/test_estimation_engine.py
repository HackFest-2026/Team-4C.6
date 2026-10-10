import pytest
from app.services.estimation.engine import estimation_engine
from app.services.estimation.feature_effort import feature_effort_engine


def test_scenario_1_simple_crud_website():
    """Mandatory test 1: Simple CRUD website."""
    res = estimation_engine.estimate_project({
        "name": "Personal Blog & CRUD",
        "project_type": "Blog_CMS",
        "overall_complexity": "Low",
        "features": [
            {"name": "Blog Post CRUD", "category": "CRUD/data module", "complexity": "Low"},
            {"name": "Comments", "category": "CRUD/data module", "complexity": "Low"},
        ]
    })
    assert res["effort"]["total_expected_effort_hours"] > 0
    assert res["budget"]["final_build_budget_inr"] > 0
    assert res["risk"]["risk_level"] in ("Low", "Medium")


def test_scenario_2_food_delivery_platform():
    """Mandatory test 2: Food delivery platform."""
    res = estimation_engine.estimate_project({
        "name": "Food Delivery App",
        "project_type": "Booking Platform",
        "overall_complexity": "High",
        "features": [
            {"name": "Auth", "category": "Authentication", "complexity": "Medium"},
            {"name": "Restaurant Menus", "category": "CRUD/data module", "complexity": "Medium"},
            {"name": "Cart & Checkout", "category": "CRUD/data module", "complexity": "Medium"},
            {"name": "Payment Gateway", "category": "Payment integration", "complexity": "High"},
            {"name": "Live Driver GPS Map", "category": "Real-time features", "complexity": "Very High"},
        ]
    })
    assert res["effort"]["total_expected_effort_hours"] > 100
    assert res["budget"]["final_build_budget_inr"] > 100000


def test_scenario_3_dashboard_application():
    """Mandatory test 3: Dashboard application."""
    res = estimation_engine.estimate_project({
        "name": "Internal Admin Dashboard",
        "project_type": "Internal Admin Tool",
        "overall_complexity": "Medium",
        "features": [
            {"name": "Admin Dashboard", "category": "Admin dashboard", "complexity": "Medium"},
            {"name": "Analytics & Charts", "category": "Analytics/reporting", "complexity": "Medium"},
        ]
    })
    assert res["effort"]["total_expected_effort_hours"] > 0


def test_scenario_4_fintech_application():
    """Mandatory test 4: FinTech application with high security requirements."""
    res = estimation_engine.estimate_project({
        "name": "FinTech Banking Portal",
        "project_type": "Fintech Application",
        "overall_complexity": "Very High",
        "quality_requirement": "Regulated",
        "features": [
            {"name": "KYC Verification", "category": "Security/compliance", "complexity": "Very High"},
            {"name": "MFA Auth", "category": "Authentication", "complexity": "High"},
            {"name": "Double Entry Ledger", "category": "CRUD/data module", "complexity": "Very High"},
            {"name": "IMPS/NEFT Transfers", "category": "Payment integration", "complexity": "Very High"},
            {"name": "Audit Logging", "category": "Audit logs", "complexity": "High"},
        ]
    })
    assert res["risk"]["risk_level"] in ("High", "Critical")
    assert res["budget"]["final_build_budget_inr"] > res["budget"]["labour_cost_inr"]


def test_scenario_5_complex_multi_platform():
    """Mandatory test 5: Complex multi-platform application."""
    res_web = estimation_engine.estimate_project({
        "name": "Single Platform Web",
        "hosting_platform": "Web",
        "features": [{"name": "Core Module", "category": "CRUD/data module", "complexity": "Medium"}]
    })
    res_multi = estimation_engine.estimate_project({
        "name": "Multi Platform Web + Native iOS + Android",
        "hosting_platform": "Web + Native iOS + Native Android",
        "features": [{"name": "Core Module", "category": "CRUD/data module", "complexity": "Medium"}]
    })
    # Multi-platform should require more total effort than single web platform
    assert res_multi["effort"]["total_expected_effort_hours"] > res_web["effort"]["total_expected_effort_hours"]


def test_scenario_6_unknown_feature_category():
    """Mandatory test 6: Unknown feature category falls back gracefully."""
    res = estimation_engine.estimate_project({
        "name": "Alien Tech App",
        "features": [
            {"name": "Teleportation Subsystem", "category": "Quantum_Hyperdrive", "complexity": "High"}
        ]
    })
    feat = res["features"][0]
    assert feat["estimation_method"] in ("generic_fallback", "rule_based_fallback")
    assert feat["expected_effort_hours"] > 0
    assert feat["needs_user_review"] is True


def test_scenario_7_missing_project_description():
    """Mandatory test 7: Missing project description is handled gracefully."""
    res = estimation_engine.estimate_project({
        "name": "No Desc Project",
        "description": "",
        "features": [{"name": "Login", "category": "Authentication", "complexity": "Low"}]
    })
    assert res["confidence"]["confidence_score_pct"] > 0


def test_scenario_8_zero_features():
    """Mandatory test 8: Zero features provides default core module without crashing."""
    res = estimation_engine.estimate_project({
        "name": "Empty Project",
        "features": []
    })
    assert len(res["features"]) >= 1
    assert res["effort"]["total_expected_effort_hours"] > 0


def test_scenario_9_one_feature():
    """Mandatory test 9: Single feature estimate."""
    res = estimation_engine.estimate_project({
        "name": "Single Feature App",
        "features": [{"name": "Simple Contact Form", "category": "CRUD/data module", "complexity": "Low"}]
    })
    assert len(res["features"]) == 1
    assert res["effort"]["total_expected_effort_hours"] > 0


def test_scenario_10_many_features():
    """Mandatory test 10: Many features (20+ features)."""
    feats = [{"name": f"Module {i}", "category": "CRUD/data module", "complexity": "Medium"} for i in range(25)]
    res = estimation_engine.estimate_project({
        "name": "Enterprise Suite",
        "features": feats
    })
    assert len(res["features"]) == 25
    assert res["effort"]["total_expected_effort_hours"] > 200


def test_scenario_11_very_high_complexity():
    """Mandatory test 11: Very high complexity scales effort and budget appropriately."""
    res_low = estimation_engine.estimate_project({
        "name": "Low App", "overall_complexity": "Low",
        "features": [{"name": "Auth", "category": "Authentication", "complexity": "Low"}]
    })
    res_vh = estimation_engine.estimate_project({
        "name": "VH App", "overall_complexity": "Very High",
        "features": [{"name": "Auth", "category": "Authentication", "complexity": "Very High"}]
    })
    assert res_vh["effort"]["total_expected_effort_hours"] > res_low["effort"]["total_expected_effort_hours"]
    assert res_vh["budget"]["final_build_budget_inr"] > res_low["budget"]["final_build_budget_inr"]


def test_scenario_12_extreme_deadline():
    """Mandatory test 12: Extreme infeasible deadline is detected and reported as infeasible."""
    res = estimation_engine.estimate_project({
        "name": "Impossible Deadline Project",
        "team_size": 2,
        "deadline_days": 3,  # Only 3 calendar days for 5 complex features!
        "features": [
            {"name": f"Complex Feature {i}", "category": "Payment integration", "complexity": "High"}
            for i in range(5)
        ]
    })
    assert res["timeline"]["is_timeline_feasible"] is False
    assert "Infeasible" in res["timeline"]["feasibility_status"]
    assert res["timeline"]["feasibility_warning"] is not None


def test_scenario_13_missing_technology_stack():
    """Mandatory test 13: Missing tech stack uses documented defaults."""
    res = estimation_engine.estimate_project({
        "name": "No Stack Project",
        # frontend_stack, backend_stack, database omitted
        "features": [{"name": "Feature 1", "category": "CRUD/data module", "complexity": "Medium"}]
    })
    assert res["effort"]["total_expected_effort_hours"] > 0


def test_scenario_14_missing_feature_effort():
    """Mandatory test 14: Missing explicit feature effort is derived from catalog priors."""
    feat = feature_effort_engine.estimate_feature(
        name="Authentication",
        category="Authentication",
        complexity="High"
    )
    assert feat["most_likely_effort_hours"] > 0
    assert feat["expected_effort_hours"] > 0
    assert feat["optimistic_effort_hours"] < feat["pessimistic_effort_hours"]


def test_scenario_16_no_negative_hours_or_costs():
    """Mandatory test 16: All efforts, rates, and costs must be strictly non-negative."""
    res = estimation_engine.estimate_project({
        "name": "Check Non Negativity",
        "features": [{"name": "Feature", "category": "CRUD/data module", "complexity": "Low"}]
    })
    assert res["effort"]["total_expected_effort_hours"] >= 0
    assert res["effort"]["optimistic_effort_hours"] >= 0
    assert res["effort"]["pessimistic_effort_hours"] >= 0
    assert res["budget"]["final_build_budget_inr"] >= 0
    assert res["budget"]["labour_cost_inr"] >= 0


def test_monotonic_feature_addition():
    """Adding a feature must never reduce total estimated effort."""
    base = estimation_engine.estimate_project({
        "name": "Base",
        "features": [{"name": "F1", "category": "Authentication", "complexity": "Medium"}]
    })
    augmented = estimation_engine.estimate_project({
        "name": "Augmented",
        "features": [
            {"name": "F1", "category": "Authentication", "complexity": "Medium"},
            {"name": "F2", "category": "Payment integration", "complexity": "High"},
        ]
    })
    assert augmented["effort"]["total_expected_effort_hours"] >= base["effort"]["total_expected_effort_hours"]
