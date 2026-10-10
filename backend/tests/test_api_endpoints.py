import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["currency"] == "INR"


def test_api_model_status():
    resp = client.get("/model/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert "target_estimated_cost_inr" in data["models"]


def test_api_model_metrics():
    resp = client.get("/model/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert "target_estimated_cost_inr" in data["models"]


def test_api_scope_analyze():
    resp = client.post("/scope/analyze", json={
        "description": "On-demand food delivery app with restaurant menus, Stripe checkout, and live GPS map tracking."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["features"]) > 0
    assert data["is_ai_generated"] is False  # Explicitly discloses offline/rule-based fallback when offline


def test_api_features_batch_estimate():
    resp = client.post("/features/estimate-effort", json={
        "features": [
            {"name": "Auth", "category": "Authentication", "complexity": "Medium"},
            {"name": "Payment", "category": "Payment integration", "complexity": "High"},
        ]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["expected_effort_hours"] > 0


def test_api_create_estimate_and_whatif_recalculate():
    # 1. Create Estimate
    est_resp = client.post("/estimate", json={
        "project_name": "API Test Project",
        "project_type": "SaaS Web Application",
        "overall_complexity": "Medium",
        "team_size": 4,
        "deadline_days": 60,
        "features": [
            {"id": "f1", "name": "Auth", "category": "Authentication", "complexity": "Medium"},
            {"id": "f2", "name": "Dashboard", "category": "Admin dashboard", "complexity": "Medium", "dependencies": ["f1"]},
        ]
    })
    assert est_resp.status_code == 200
    estimate = est_resp.json()
    assert estimate["budget"]["final_build_budget_inr"] > 0

    # 2. What-If Recalculate
    recalc_resp = client.post("/estimate/recalculate", json={
        "base_estimate": estimate,
        "overrides": {
            "team_size": 6,
            "contingency_pct": 0.20
        }
    })
    assert recalc_resp.status_code == 200
    recalc_data = recalc_resp.json()
    assert "recalculated_estimate" in recalc_data
    assert "deltas" in recalc_data


def test_api_projects_crud_flow():
    # Create estimate to save
    est_resp = client.post("/estimate", json={
        "project_name": "Persistence Test Project",
        "features": [{"name": "Feature 1", "category": "CRUD/data module", "complexity": "Low"}]
    })
    estimate = est_resp.json()

    # Save project
    save_resp = client.post("/projects", json={
        "project_name": "Persistence Test Project",
        "description": "Test description",
        "estimate": estimate
    })
    assert save_resp.status_code == 200
    save_data = save_resp.json()
    proj_id = save_data["project_id"]

    # List projects
    list_resp = client.get("/projects")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["count"] > 0

    # Get single project
    get_resp = client.get(f"/projects/{proj_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["name"] == "Persistence Test Project"

    # Delete project
    del_resp = client.delete(f"/projects/{proj_id}")
    assert del_resp.status_code == 200


def test_api_analytics_and_settings():
    ana_resp = client.get("/analytics")
    assert ana_resp.status_code == 200

    set_resp = client.get("/settings")
    assert set_resp.status_code == 200
    assert set_resp.json()["currency"] == "INR"
