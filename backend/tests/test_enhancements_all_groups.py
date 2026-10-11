"""
CostPilot AI — Comprehensive Verification Tests for Hackfest 2026 Problem Statement 4C
Covers Test Groups 1 through 8:
Group 1: Authentication & User Account Isolation
Group 2: Multi-Select Target Platforms & Serialization
Group 3: AI Recommendations (Tech Stack, Roles, Infrastructure)
Group 4: Headcount, Dynamic Team Size & Financial Invariants
Group 5: Multi-Currency Formatting, Conversion & Storage
Group 6: Working Calendar (Hours/Day, Days/Week) & Timeline Recalculation
Group 7: MMRE, MdMRE, PRED(25) Statistical Metric Calculations
Group 8: Complete End-to-End Estimation & CRUD Workflow
"""

import pytest
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.services.ml.train_model import calculate_mmre, calculate_mdmre, calculate_pred25
from app.core.config import SUPPORTED_CURRENCIES

client = TestClient(app)


# =====================================================================
# TEST GROUP 1: AUTHENTICATION & ACCOUNT ISOLATION (ISSUE 1)
# =====================================================================
def test_group_1_user_account_isolation():
    # Register User A
    user_a_email = f"user_a_{np.random.randint(10000, 99999)}@test.com"
    resp_a = client.post("/api/v1/auth/register", json={
        "full_name": "Alice Developer",
        "email": user_a_email,
        "phone": "+919876543210",
        "password": "Password@123",
        "confirm_password": "Password@123"
    })
    assert resp_a.status_code == 200
    token_a = resp_a.json()["access_token"]
    user_a_id = resp_a.json()["user"]["id"]

    # Register User B
    user_b_email = f"user_b_{np.random.randint(10000, 99999)}@test.com"
    resp_b = client.post("/api/v1/auth/register", json={
        "full_name": "Bob Architect",
        "email": user_b_email,
        "phone": "+919876543211",
        "password": "Password@123",
        "confirm_password": "Password@123"
    })
    assert resp_b.status_code == 200
    token_b = resp_b.json()["access_token"]

    # User A creates and saves a project
    est_resp = client.post("/api/v1/estimate", json={
        "project_name": "Alice Secret Project",
        "project_type": "FinTech Platform",
        "overall_complexity": "High",
        "hosting_platform": "Web Application",
        "team_size": 4,
        "features": [{"name": "Vault", "category": "Security", "complexity": "High"}]
    })
    assert est_resp.status_code == 200
    estimate_data = est_resp.json()

    save_resp = client.post("/api/v1/projects", json={
        "project_name": "Alice Secret Project",
        "description": "Confidential corporate project",
        "currency_code": "INR",
        "estimate": estimate_data
    }, headers={"Authorization": f"Bearer {token_a}"})
    assert save_resp.status_code == 200
    proj_a_id = save_resp.json()["project_id"]

    # 1. User B cannot view User A's project (Strict 403 Forbidden)
    get_resp = client.get(f"/api/v1/projects/{proj_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert get_resp.status_code == 403

    # 2. User B cannot delete User A's project
    del_resp = client.delete(f"/api/v1/projects/{proj_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert del_resp.status_code == 403

    # 3. User B's project listing does NOT include User A's project
    list_b = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token_b}"})
    assert list_b.status_code == 200
    b_project_ids = [p["id"] for p in list_b.json()["projects"]]
    assert proj_a_id not in b_project_ids

    # 4. User A CAN view and retrieve their own project
    get_a = client.get(f"/api/v1/projects/{proj_a_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert get_a.status_code == 200
    assert get_a.json()["name"] == "Alice Secret Project"


# =====================================================================
# TEST GROUP 2: MULTI-SELECT TARGET PLATFORMS & SERIALIZATION (ISSUE 2)
# =====================================================================
def test_group_2_multi_platform_selection_and_serialization():
    # Single platform estimate
    resp_single = client.post("/api/v1/estimate", json={
        "project_name": "Web Only App",
        "project_type": "SaaS Platform",
        "overall_complexity": "Medium",
        "hosting_platform": "Web Application",
        "target_platforms": ["Web Application"],
        "team_size": 4,
        "features": [{"name": "Dashboard", "category": "CRUD/data module", "complexity": "Medium"}]
    })
    assert resp_single.status_code == 200
    effort_single = resp_single.json()["effort"]["total_expected_effort_hours"]

    # Multi-platform combination: Web + Android + iOS
    resp_multi = client.post("/api/v1/estimate", json={
        "project_name": "Cross Platform App",
        "project_type": "SaaS Platform",
        "overall_complexity": "Medium",
        "hosting_platform": "Web Application",
        "target_platforms": ["Web Application", "Android Application", "iOS Application"],
        "team_size": 4,
        "features": [{"name": "Dashboard", "category": "CRUD/data module", "complexity": "Medium"}]
    })
    assert resp_multi.status_code == 200
    effort_multi = resp_multi.json()["effort"]["total_expected_effort_hours"]

    # Multi-platform effort must reflect cross-platform adaptation overhead
    assert effort_multi > effort_single


# =====================================================================
# TEST GROUP 3: AI RECOMMENDATIONS (ISSUES 3, 4, 7)
# =====================================================================
def test_group_3_ai_recommendations_endpoints():
    # 1. Step 2 AI Technical Stack Recommendation
    tech_resp = client.post("/api/v1/recommend/tech-stack", json={
        "project_name": "QuickBite Delivery",
        "project_type": "Food Delivery",
        "overall_complexity": "High",
        "target_platforms": ["Web Application", "Android Application", "iOS Application"],
        "expected_traffic": "100k-1M"
    })
    assert tech_resp.status_code == 200
    tech_data = tech_resp.json()
    assert "recommendations" in tech_data
    assert "rationale" in tech_data
    assert tech_data["recommendations"]["realtime"] in ["WebSockets", "SSE"]
    assert len(tech_data["recommendations"]["integrations"]) > 0

    # 2. Step 4 AI Roles Recommendation based on Step 3 Features
    roles_resp = client.post("/api/v1/recommend/roles", json={
        "features": [
            {"name": "Native Mobile GPS Tracking", "category": "Real-time features", "complexity": "High"},
            {"name": "Payment Gateway", "category": "Payment integration", "complexity": "High"},
            {"name": "Admin Dashboard", "category": "Admin dashboard", "complexity": "Medium"}
        ],
        "project_type": "Food Delivery",
        "complexity": "High",
        "currency": "INR"
    })
    assert roles_resp.status_code == 200
    roles_data = roles_resp.json()
    assert len(roles_data["roles"]) >= 3
    role_names = [r["role_name"] for r in roles_data["roles"]]
    assert any("Developer" in name for name in role_names)
    assert any("QA" in name for name in role_names)

    # 3. Step 5 AI Infrastructure & Tooling Recommendation
    infra_resp = client.post("/api/v1/recommend/infrastructure", json={
        "project_name": "QuickBite Delivery",
        "project_type": "Food Delivery",
        "overall_complexity": "High",
        "target_platforms": ["Web Application", "Cross-Platform Mobile Application"],
        "expected_traffic": "100k-1M",
        "frontend_stack": "Flutter",
        "backend_stack": "FastAPI_Python",
        "database": "PostgreSQL + Redis",
        "cloud_platform": "AWS",
        "features": [{"name": "GPS", "category": "Real-time", "complexity": "High"}],
        "currency": "INR"
    })
    assert infra_resp.status_code == 200
    infra_data = infra_resp.json()
    assert len(infra_data["items"]) >= 3
    assert any(i["billing_period"] == "Monthly" for i in infra_data["items"])
    assert any(i["billing_period"] == "One-Time" for i in infra_data["items"])


# =====================================================================
# TEST GROUP 4: HEADCOUNT, TOTAL TEAM SIZE & FINANCIAL INVARIANTS (ISSUES 4 & 8)
# =====================================================================
def test_group_4_headcount_and_zero_headcount_filtering():
    # 1. Custom headcounts where DevOps and PM are 0
    role_headcounts = {
        "Frontend Developer": 2,
        "Backend Developer": 2,
        "UI/UX Designer": 1,
        "QA / Test Engineer": 1,
        "DevOps / Cloud Engineer": 0,
        "Project Manager": 0
    }
    # Expected team size = 2 + 2 + 1 + 1 + 0 + 0 = 6
    expected_team_size = 6

    resp = client.post("/api/v1/estimate", json={
        "project_name": "Staffing Invariant Test",
        "project_type": "SaaS Platform",
        "overall_complexity": "Medium",
        "hosting_platform": "Web Application",
        "role_headcounts": role_headcounts,
        "team_size": 10,  # Intentional mismatch to verify engine computes sum of active headcounts
        "features": [{"name": "Module A", "category": "CRUD", "complexity": "Medium"}]
    })
    assert resp.status_code == 200
    data = resp.json()

    # Active team size in engine must equal sum of headcounts (6)
    assert data["timeline"]["team_size"] == expected_team_size

    # Roles with 0 headcount must be completely EXCLUDED from Step 6 role costs
    role_costs = data["budget"]["role_costs"]
    role_names_in_result = [r["role"] for r in role_costs] if isinstance(role_costs, list) else list(role_costs.keys())

    assert "DevOps / Cloud Engineer" not in role_names_in_result
    assert "Project Manager" not in role_names_in_result

    # Strict Financial Invariant: Total Labour = sum(Allocated Hours * Hourly Rate)
    labour_cost = data["budget"]["labour_cost_inr"]
    if isinstance(role_costs, list):
        summed_role_costs = sum(r["role_cost_inr"] for r in role_costs)
    else:
        summed_role_costs = sum(v["role_cost_inr"] for v in role_costs.values())

    assert abs(labour_cost - summed_role_costs) <= 2.0  # within rounding tolerance


# =====================================================================
# TEST GROUP 5: MULTI-CURRENCY CONVERSION & PERSISTENCE (ISSUE 5)
# =====================================================================
def test_group_5_multi_currency_handling():
    # Verify currencies endpoint
    curr_resp = client.get("/api/v1/currencies")
    assert curr_resp.status_code == 200
    currencies = curr_resp.json()["supported_currencies"]
    assert "USD" in currencies
    assert "EUR" in currencies
    assert "GBP" in currencies
    assert "AUD" in currencies
    assert "AED" in currencies

    # Estimate in USD
    usd_rate = SUPPORTED_CURRENCIES["USD"]["rate_to_inr"]  # 84.0
    resp_usd = client.post("/api/v1/estimate", json={
        "project_name": "USD Currency Project",
        "project_type": "SaaS Platform",
        "overall_complexity": "Medium",
        "hosting_platform": "Web Application",
        "currency": "USD",
        "currency_exchange_rate": usd_rate,
        "team_size": 4,
        "features": [{"name": "Core Module", "category": "CRUD", "complexity": "Medium"}]
    })
    assert resp_usd.status_code == 200
    usd_data = resp_usd.json()

    assert usd_data["currency"] == "USD"
    final_budget_inr = usd_data["budget"]["final_build_budget_inr"]
    final_budget_usd = usd_data["budget"]["final_build_budget_converted"]

    # Invariant: Converted Budget = Base INR / Exchange Rate
    expected_usd = round(final_budget_inr / usd_rate, 2)
    assert abs(final_budget_usd - expected_usd) <= 0.5


# =====================================================================
# TEST GROUP 6: WORKING CALENDAR & TIMELINE RECALCULATION (ISSUE 6)
# =====================================================================
def test_group_6_working_calendar_and_timeline():
    base_request = {
        "project_name": "Calendar Timeline Project",
        "project_type": "SaaS Platform",
        "overall_complexity": "Medium",
        "hosting_platform": "Web Application",
        "team_size": 4,
        "features": [
            {"name": "Feature 1", "category": "CRUD", "complexity": "Medium"},
            {"name": "Feature 2", "category": "CRUD", "complexity": "Medium"},
            {"name": "Feature 3", "category": "CRUD", "complexity": "Medium"}
        ]
    }

    # Case A: Standard calendar (8 hours/day, 5 days/week = 40h/week/person)
    req_a = {**base_request, "working_hours_per_day": 8.0, "working_days_per_week": 5.0}
    resp_a = client.post("/api/v1/estimate", json=req_a)
    assert resp_a.status_code == 200
    days_a = resp_a.json()["timeline"]["likely_calendar_days"]
    effort_a = resp_a.json()["effort"]["total_expected_effort_hours"]

    # Case B: Compressed/Short calendar (6 hours/day, 4 days/week = 24h/week/person)
    req_b = {**base_request, "working_hours_per_day": 6.0, "working_days_per_week": 4.0}
    resp_b = client.post("/api/v1/estimate", json=req_b)
    assert resp_b.status_code == 200
    days_b = resp_b.json()["timeline"]["likely_calendar_days"]
    effort_b = resp_b.json()["effort"]["total_expected_effort_hours"]

    # Rule 1: Intrinsic effort does NOT change simply because calendar changed
    assert effort_a == effort_b

    # Rule 2: Elapsed calendar duration increases when daily/weekly capacity decreases
    assert days_b > days_a


# =====================================================================
# TEST GROUP 7: MODEL EVALUATION METRICS (ISSUE 9)
# =====================================================================
def test_group_7_model_evaluation_metrics_statistical_formulas():
    # Test ground-truth statistical metric calculations with synthetic known data
    y_true = np.array([100.0, 200.0, 400.0, 500.0])
    y_pred = np.array([110.0, 180.0, 360.0, 750.0])
    # Relative errors:
    # |100 - 110| / 100 = 0.10 (10%)  <= 25% -> YES
    # |200 - 180| / 200 = 0.10 (10%)  <= 25% -> YES
    # |400 - 360| / 400 = 0.10 (10%)  <= 25% -> YES
    # |500 - 750| / 500 = 0.50 (50%)  > 25%  -> NO

    mmre, _ = calculate_mmre(y_true, y_pred)
    mdmre = calculate_mdmre(y_true, y_pred)
    pred25 = calculate_pred25(y_true, y_pred)

    expected_mmre = (0.10 + 0.10 + 0.10 + 0.50) / 4.0  # 0.20 (20%)
    expected_mdmre = 0.10  # median
    expected_pred25 = 75.0  # 75% percentage

    assert abs(mmre - expected_mmre) < 1e-4
    assert abs(mdmre - expected_mdmre) < 1e-4
    assert abs(pred25 - expected_pred25) < 1e-4

    # Verify that Step 6 estimate results include held-out test evaluation benchmarks
    resp = client.post("/api/v1/estimate", json={
        "project_name": "Metrics Test",
        "project_type": "SaaS Platform",
        "overall_complexity": "Medium",
        "hosting_platform": "Web Application",
        "team_size": 4,
        "features": [{"name": "Test", "category": "CRUD", "complexity": "Medium"}]
    })
    assert resp.status_code == 200
    data = resp.json()

    assert "model_evaluation_metrics" in data
    eval_m = data["model_evaluation_metrics"]
    assert "cost_model" in eval_m
    cost_m = eval_m["cost_model"]
    assert "test_mmre" in cost_m
    assert "test_mdmre" in cost_m
    assert "test_pred25" in cost_m
    assert cost_m["test_sample_count"] == 500
    assert 0.0 < cost_m["test_pred25"] <= 100.0


# =====================================================================
# TEST GROUP 8: END-TO-END REGRESSION (WORKFLOW INTEGRATION)
# =====================================================================
def test_group_8_full_end_to_end_regression():
    # 1. Register user
    email = f"e2e_user_{np.random.randint(10000, 99999)}@test.com"
    auth_resp = client.post("/api/v1/auth/register", json={
        "full_name": "End To End User",
        "email": email,
        "phone": "+919999988888",
        "password": "Password@123",
        "confirm_password": "Password@123"
    })
    assert auth_resp.status_code == 200
    token = auth_resp.json()["access_token"]

    # 2. Generate estimate with custom parameters
    est_resp = client.post("/api/v1/estimate", json={
        "project_name": "E2E Automated SaaS",
        "project_type": "SaaS Platform",
        "overall_complexity": "Medium",
        "hosting_platform": "Web Application",
        "target_platforms": ["Web Application", "Android Application"],
        "team_size": 4,
        "currency": "EUR",
        "currency_exchange_rate": 91.5,
        "working_hours_per_day": 7.5,
        "working_days_per_week": 5.0,
        "role_headcounts": {
            "Frontend Developer": 2,
            "Backend Developer": 2,
            "UI/UX Designer": 1,
            "QA / Test Engineer": 1,
            "DevOps / Cloud Engineer": 0,
            "Project Manager": 0
        },
        "features": [
            {"name": "Auth", "category": "Authentication", "complexity": "Medium"},
            {"name": "Billing", "category": "Payment integration", "complexity": "High"},
            {"name": "Dashboard", "category": "Admin dashboard", "complexity": "Medium"}
        ]
    })
    assert est_resp.status_code == 200
    est = est_resp.json()

    # 3. Save project
    save_resp = client.post("/api/v1/projects", json={
        "project_name": "E2E Automated SaaS",
        "description": "Full regression test project",
        "currency_code": "EUR",
        "estimate": est
    }, headers={"Authorization": f"Bearer {token}"})
    assert save_resp.status_code == 200
    proj_id = save_resp.json()["project_id"]

    # 4. Retrieve project from database
    get_resp = client.get(f"/api/v1/projects/{proj_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == 200
    saved_proj = get_resp.json()
    assert saved_proj["name"] == "E2E Automated SaaS"
    assert saved_proj["currency_code"] == "EUR"
    assert saved_proj["final_budget_converted"] > 0

    # 5. What-if recalculation
    recalc_resp = client.post(f"/api/v1/projects/{proj_id}/recalculate", json={
        "target_platforms": ["Web Application", "Android Application", "iOS Application"],
        "team_size": 6,
        "currency": "EUR",
        "contingency_pct": 0.20
    }, headers={"Authorization": f"Bearer {token}"})
    assert recalc_resp.status_code == 200
    recalc_data = recalc_resp.json()
    assert recalc_data["scenario"]["final_build_budget_inr"] > 0

    # 6. Delete project
    del_resp = client.delete(f"/api/v1/projects/{proj_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_resp.status_code == 200

    # 7. Verify deletion
    verify_resp = client.get(f"/api/v1/projects/{proj_id}", headers={"Authorization": f"Bearer {token}"})
    assert verify_resp.status_code == 404
