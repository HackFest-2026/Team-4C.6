import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)


def test_step2_tech_stack_recommendation_and_inputs():
    """Verify Step 2 AI/rule recommendation receives Step 1 inputs and matches schema."""
    payload = {
        "project_name": "HealthTrack Telemedicine",
        "project_type": "Healthcare / Telemedicine",
        "overall_complexity": "High",
        "description": "HIPAA compliant video consultation and patient EHR system",
        "target_platforms": ["Web Application", "Cross-Platform Mobile Application"],
        "expected_traffic": "100k-1M",
    }
    response = client.post("/api/v1/recommend/tech-stack", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "recommendations" in data
    rec = data["recommendations"]
    
    # Required architecture components
    assert "frontend" in rec
    assert "backend" in rec
    assert "database" in rec
    assert "cloud_platform" in rec
    assert "authentication" in rec
    assert "security" in rec
    assert "integrations" in rec
    assert isinstance(rec["integrations"], list)
    assert len(rec["integrations"]) > 0
    assert "rationale" in data
    assert "provenance" in data or "provider" in data


def test_step4_role_recommendations_from_step3_features():
    """Verify Step 4 team recommendations use Step 3 features, contain headcount/rates, and sync team size."""
    features_payload = {
        "features": [
            {
                "name": "Patient Video Call Consultation",
                "category": "Realtime / WebRTC",
                "complexity": "High",
                "dependencies": [],
                "integration_count": 2,
                "expected_hours": 60.0,
            },
            {
                "name": "EHR Database & Prescription Generation",
                "category": "Database / Reports",
                "complexity": "Medium",
                "dependencies": [],
                "integration_count": 1,
                "expected_hours": 35.0,
            },
            {
                "name": "AI Symptom Checker Assistant",
                "category": "AI / LLM",
                "complexity": "High",
                "dependencies": [],
                "integration_count": 1,
                "expected_hours": 45.0,
            },
        ],
        "project_type": "Healthcare / Telemedicine",
        "complexity": "High",
        "currency": "INR",
    }
    response = client.post("/api/v1/recommend/roles", json=features_payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "roles" in data
    roles = data["roles"]
    assert len(roles) >= 4
    
    # Check that roles provide both headcount and hourly rate
    total_headcount = 0
    for r in roles:
        assert "headcount" in r
        assert "recommended_headcount" in r
        assert r["headcount"] == r["recommended_headcount"]
        assert "hourly_rate" in r
        assert r["hourly_rate"] > 0
        assert "role_name" in r or "role" in r
        total_headcount += r["headcount"]
    
    # Total team size equals sum of role headcounts
    assert data["total_team_size"] == total_headcount
    
    # AI/ML role recommended because AI feature was present
    role_names = [r["role"] for r in roles]
    assert any("ML" in name or "Data" in name for name in role_names)


def test_step6_historical_cohort_benchmark():
    """Verify historical cohort benchmark retrieves empirical 2,500 projects cohort data without fabrication."""
    payload = {
        "project_name": "SaaS Billing System",
        "project_type": "SaaS Platform",
        "overall_complexity": "Medium",
        "features": [
            {"id": "f1", "name": "Stripe Subscriptions", "complexity": "Medium", "integration_count": 1},
            {"id": "f2", "name": "Customer Portal", "complexity": "Medium", "integration_count": 0},
        ],
        "currency": "INR",
    }
    response = client.post("/api/v1/estimate", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    
    assert "ml_benchmark" in data
    ml_bench = data["ml_benchmark"]
    # Cohort benchmark checks
    assert "has_cohort_benchmark" in ml_bench
    assert ml_bench["has_cohort_benchmark"] is True
    assert ml_bench["cohort_sample_size"] > 0
    assert ml_bench["cohort_avg_effort_hours"] > 0
    assert ml_bench["cohort_avg_duration_days"] > 0
    assert ml_bench["cohort_avg_cost_inr"] > 0
    assert "CostPilot_AI_Training_Dataset.xlsx" in ml_bench["dataset_provenance"]
    assert "ml_effort_hours" in ml_bench
    assert "ml_cost_inr" in ml_bench


def test_step6_project_outcome_reconciliation_flow():
    """Verify full reconciliation workflow: save project, record actuals, compute variances with sign convention."""
    # 1. Register a test user
    import uuid
    uid = str(uuid.uuid4())[:8]
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"reconcile_{uid}@example.com",
            "password": "Password@123",
            "confirm_password": "Password@123",
            "full_name": "Auditor",
            "phone": "+919876543210"
        }
    )
    assert reg_res.status_code == 200, reg_res.text
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Save a project with baseline estimate
    est_payload = {
        "project_name": f"Audit Project {uid}",
        "project_type": "E-commerce",
        "overall_complexity": "Medium",
        "features": [
            {"id": "f1", "name": "Product Catalog", "complexity": "Medium", "integration_count": 0},
        ],
        "currency": "INR",
    }
    est_res = client.post("/api/v1/estimate", json=est_payload)
    est_data = est_res.json()
    est_cost = est_data["budget"]["final_build_budget_inr"]
    est_effort = est_data["effort"]["total_expected_effort_hours"]
    est_duration = est_data["timeline"]["likely_calendar_days"]

    save_res = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "project_name": f"Audit Project {uid}",
            "currency_code": "INR",
            "estimate": est_data,
        }
    )
    assert save_res.status_code == 200, save_res.text
    project_id = save_res.json()["id"]

    # 3. Initially, no reconciliation recorded
    rec_init = client.get(f"/api/v1/projects/{project_id}/reconciliation", headers=headers)
    assert rec_init.status_code == 200
    assert rec_init.json()["has_reconciliation"] is False

    # 4. Record actual outcomes
    actual_cost = est_cost - 50000.0  # Completed 50k under budget
    actual_effort = est_effort - 20.0   # Completed 20h under effort
    actual_duration = est_duration + 5  # 5 days delay

    rec_post = client.post(
        f"/api/v1/projects/{project_id}/reconciliation",
        headers=headers,
        json={
            "actual_cost": actual_cost,
            "actual_effort_hours": actual_effort,
            "actual_duration_days": actual_duration,
            "currency_code": "INR",
            "project_status": "Completed",
            "notes": "Fast-tracked checkout API, slight cloud domain delay.",
        }
    )
    assert rec_post.status_code == 200, rec_post.text
    rec_data = rec_post.json()

    # 5. Verify variance formulas and sign convention:
    # Cost Variance = Estimated - Actual (Positive = Under budget)
    assert rec_data["cost_variance"] == pytest.approx(50000.0, rel=1e-2)
    assert rec_data["cost_variance_pct"] > 0
    # Effort Variance = Estimated - Actual (Positive = Effort saved)
    assert rec_data["effort_variance"] == pytest.approx(20.0, rel=1e-2)
    # Duration Variance = Estimated - Actual (Negative = Overrun)
    assert rec_data["duration_variance"] == pytest.approx(-5.0, rel=1e-2)
    assert rec_data["duration_variance_pct"] < 0
    assert "Positive variance" in rec_data["sign_convention"]

    # 6. Verify GET fetches persisted reconciliation record
    rec_get = client.get(f"/api/v1/projects/{project_id}/reconciliation", headers=headers)
    assert rec_get.status_code == 200
    assert rec_get.json()["has_reconciliation"] is True
    assert rec_get.json()["notes"] == "Fast-tracked checkout API, slight cloud domain delay."

    # 7. Authorization: another user cannot access or tamper with this reconciliation
    other_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"other_{uid}@example.com",
            "password": "Password@123",
            "confirm_password": "Password@123",
            "full_name": "Intruder",
            "phone": "+919876543211"
        }
    )
    assert other_reg.status_code == 200, other_reg.text
    other_token = other_reg.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    unauth_res = client.get(f"/api/v1/projects/{project_id}/reconciliation", headers=other_headers)
    assert unauth_res.status_code in (403, 404)


def test_step6_supervised_model_evaluation_metrics_and_multi_target():
    """Verify supervised evaluation metrics load from reports and include all 3 validated targets."""
    response = client.get("/api/v1/model/metrics")
    assert response.status_code == 200, response.text
    data = response.json()
    assert "models" in data
    models = data["models"]
    
    # 3 regression models
    assert "target_estimated_cost_inr" in models
    assert "total_estimated_effort_hours" in models
    assert "estimated_duration_calendar_days" in models

    cost_m = models["target_estimated_cost_inr"]["metrics"]
    assert cost_m["test_mae"] > 0
    assert cost_m["test_rmse"] > 0
    assert 0.0 < cost_m["test_r2"] < 1.0
    assert 0.0 < cost_m["test_mmre"] < 1.0
    assert 0.0 < cost_m["test_mdmre"] < 1.0
    # PRED(25) percentage
    assert cost_m["test_pred25"] > 1.0  # e.g., 46.6%

    # Check that Step 6 estimate includes consistent model metrics
    est_res = client.post("/api/v1/estimate", json={
        "project_name": "Test Eval Consistency",
        "project_type": "SaaS Platform",
        "overall_complexity": "Medium",
    })
    assert est_res.status_code == 200
    est_metrics = est_res.json()["model_evaluation_metrics"]
    assert est_metrics["cost_model"]["test_r2"] == pytest.approx(cost_m["test_r2"], rel=1e-3)
    assert est_metrics["cost_model"]["test_mmre"] == pytest.approx(cost_m["test_mmre"], rel=1e-3)


def test_step6_currency_conversion_invariants():
    """Verify currency conversion updates monetary costs across all 8 currencies while preserving effort & duration."""
    currencies = ["USD", "EUR", "GBP", "AUD", "CAD", "SGD", "AED"]
    
    # Base INR estimate
    base_res = client.post("/api/v1/estimate", json={
        "project_name": "Currency Test Project",
        "project_type": "SaaS Platform",
        "overall_complexity": "Medium",
        "currency": "INR",
    })
    base_data = base_res.json()
    base_effort = base_data["effort"]["total_expected_effort_hours"]
    base_duration = base_data["timeline"]["likely_calendar_days"]
    base_budget_inr = base_data["budget"]["final_build_budget_inr"]

    for code in currencies:
        cur_info = settings.SUPPORTED_CURRENCIES[code]
        expected_rate = cur_info["rate_to_inr"]
        
        cur_res = client.post("/api/v1/estimate", json={
            "project_name": "Currency Test Project",
            "project_type": "SaaS Platform",
            "overall_complexity": "Medium",
            "currency": code,
        })
        assert cur_res.status_code == 200, cur_res.text
        cur_data = cur_res.json()

        # Invariant 1: Effort (hours) MUST remain identical
        assert cur_data["effort"]["total_expected_effort_hours"] == base_effort
        # Invariant 2: Duration (days) MUST remain identical
        assert cur_data["timeline"]["likely_calendar_days"] == base_duration
        # Invariant 3: Currency code must match
        assert cur_data["currency"] == code
        # Invariant 4: Converted budget must equal Base INR / exchange rate
        converted_budget = cur_data["budget"]["final_build_budget_converted"]
        assert converted_budget == pytest.approx(base_budget_inr / expected_rate, rel=1e-2)
