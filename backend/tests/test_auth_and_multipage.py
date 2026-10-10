import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_auth_registration_and_duplicate_handling():
    unique_email = f"user_{uuid.uuid4().hex[:8]}@costpilot.ai"

    # 1. Valid registration
    reg_resp = client.post("/api/v1/auth/register", json={
        "full_name": "Test Engineer",
        "email": unique_email,
        "phone": "+1 (555) 012-3456",
        "password": "StrongPassword@123",
        "confirm_password": "StrongPassword@123",
    })
    assert reg_resp.status_code == 200, f"Registration failed: {reg_resp.text}"
    data = reg_resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == unique_email
    assert data["user"]["full_name"] == "Test Engineer"

    # 2. Duplicate registration rejection
    dup_resp = client.post("/api/v1/auth/register", json={
        "full_name": "Duplicate User",
        "email": unique_email,
        "password": "StrongPassword@123",
        "confirm_password": "StrongPassword@123",
    })
    assert dup_resp.status_code == 400
    assert "already exists" in dup_resp.json()["detail"]


def test_auth_login_success_and_failure():
    email = f"login_test_{uuid.uuid4().hex[:8]}@costpilot.ai"
    password = "CorrectPassword@123"

    # Register user
    reg = client.post("/api/v1/auth/register", json={
        "full_name": "Login Tester",
        "email": email,
        "password": password,
        "confirm_password": password,
    })
    assert reg.status_code == 200

    # Successful login
    login_resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    assert len(token) > 20

    # Bad password rejection
    bad_resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "WrongPassword@123",
    })
    assert bad_resp.status_code == 401


def test_auth_profile_and_password_change():
    email = f"profile_test_{uuid.uuid4().hex[:8]}@costpilot.ai"
    password = "InitialPassword@123"

    # Register
    reg = client.post("/api/v1/auth/register", json={
        "full_name": "Profile Tester",
        "email": email,
        "phone": "+1 555-1111",
        "password": password,
        "confirm_password": password,
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch profile
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    # Update profile
    upd_resp = client.put("/api/v1/auth/profile", json={
        "full_name": "Updated Profile Name",
        "phone": "+1 555-9999",
    }, headers=headers)
    assert upd_resp.status_code == 200
    assert upd_resp.json()["full_name"] == "Updated Profile Name"
    assert upd_resp.json()["phone"] == "+1 555-9999"

    # Change password
    new_password = "BrandNewPassword@456"
    chg_resp = client.post("/api/v1/auth/change-password", json={
        "current_password": password,
        "new_password": new_password,
        "confirm_new_password": new_password,
    }, headers=headers)
    assert chg_resp.status_code == 200

    # Verify old password no longer works
    old_login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert old_login.status_code == 401

    # Verify new password works
    new_login = client.post("/api/v1/auth/login", json={"email": email, "password": new_password})
    assert new_login.status_code == 200


def test_complexity_monotonicity_strict():
    """
    Validates that identical projects with identical features strictly satisfy:
    Budget(Low) < Budget(Medium) < Budget(High) < Budget(Very High)
    and
    Effort(Low) < Effort(Medium) < Effort(High) < Effort(Very High)
    """
    complexities = ["Low", "Medium", "High", "Very High"]
    results = {}

    for comp in complexities:
        resp = client.post("/api/v1/estimate", json={
            "project_name": f"Monotonicity {comp}",
            "project_type": "SaaS Web Application",
            "overall_complexity": comp,
            "hosting_platform": "Web Application",
            "team_size": 4,
            "rate_profile": "Professional",
            "contingency_pct": 0.15,
            "features": [
                {"name": "Auth", "category": "Authentication", "complexity": "Auto"},
                {"name": "Catalog", "category": "CRUD/data module", "complexity": "Auto"},
                {"name": "Checkout", "category": "Payment integration", "complexity": "Auto"},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        results[comp] = {
            "budget": data["budget"]["final_build_budget_inr"],
            "effort": data["effort"]["total_expected_effort_hours"],
        }

    budgets = [results[c]["budget"] for c in complexities]
    efforts = [results[c]["effort"] for c in complexities]

    assert budgets[0] < budgets[1] < budgets[2] < budgets[3], f"Budget monotonicity failed: {budgets}"
    assert efforts[0] < efforts[1] < efforts[2] < efforts[3], f"Effort monotonicity failed: {efforts}"


def test_project_user_isolation_and_delete_authorization():
    # User 1
    u1_email = f"u1_{uuid.uuid4().hex[:6]}@costpilot.ai"
    u1_reg = client.post("/api/v1/auth/register", json={
        "full_name": "User One", "email": u1_email, "password": "Password@123", "confirm_password": "Password@123"
    })
    u1_token = u1_reg.json()["access_token"]
    u1_headers = {"Authorization": f"Bearer {u1_token}"}

    # User 2
    u2_email = f"u2_{uuid.uuid4().hex[:6]}@costpilot.ai"
    u2_reg = client.post("/api/v1/auth/register", json={
        "full_name": "User Two", "email": u2_email, "password": "Password@123", "confirm_password": "Password@123"
    })
    u2_token = u2_reg.json()["access_token"]
    u2_headers = {"Authorization": f"Bearer {u2_token}"}

    # Calculate estimate
    est = client.post("/api/v1/estimate", json={
        "project_name": "User 1 Secret Project",
        "features": [{"name": "Auth", "category": "Authentication", "complexity": "Medium"}]
    }).json()

    # User 1 saves project
    save = client.post("/api/v1/projects", json={
        "project_name": "User 1 Secret Project",
        "estimate": est,
    }, headers=u1_headers)
    assert save.status_code == 200
    p_id = save.json()["project_id"]

    # User 2 attempts to delete User 1's project -> Should be 403 Forbidden
    del_attempt = client.delete(f"/api/v1/projects/{p_id}", headers=u2_headers)
    assert del_attempt.status_code == 403

    # User 1 deletes their own project -> Should succeed with 200
    del_success = client.delete(f"/api/v1/projects/{p_id}", headers=u1_headers)
    assert del_success.status_code == 200
    assert del_success.json()["status"] == "deleted"

    # Verification: project is gone
    get_del = client.get(f"/api/v1/projects/{p_id}")
    assert get_del.status_code == 404


def test_expanded_domains_and_platforms():
    domains = [
        "Business Website", "Portfolio Website", "E-commerce", "Online Marketplace", "SaaS Platform",
        "Food Delivery", "Grocery Delivery", "Ride Booking", "Travel Booking", "Education / E-learning",
        "Healthcare", "FinTech", "Banking", "Insurance", "Real Estate", "Logistics",
        "CRM", "ERP", "HR Management", "Social Networking", "AI/ML Application"
    ]
    platforms = [
        "Web Application", "Responsive Website", "Progressive Web App (PWA)", "Android Application",
        "iOS Application", "Cross-Platform Mobile Application", "Desktop Application", "Web + Mobile"
    ]

    for d in domains:
        resp = client.post("/api/v1/estimate", json={
            "project_name": f"Domain {d}",
            "project_type": d,
            "overall_complexity": "Medium",
            "features": [{"name": "Core", "category": "CRUD/data module", "complexity": "Medium"}]
        })
        assert resp.status_code == 200
        assert resp.json()["project_type"] == d
        assert resp.json()["budget"]["final_build_budget_inr"] > 0

    for p in platforms:
        resp = client.post("/api/v1/estimate", json={
            "project_name": f"Platform {p}",
            "project_type": "SaaS Platform",
            "overall_complexity": "Medium",
            "hosting_platform": p,
            "features": [{"name": "Core", "category": "CRUD/data module", "complexity": "Medium"}]
        })
        assert resp.status_code == 200
        assert resp.json()["platform"] == p
        assert resp.json()["budget"]["final_build_budget_inr"] > 0
