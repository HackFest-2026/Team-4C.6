import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ml.metrics import calculate_relative_error_metrics, calculate_individual_accuracy
from app.services.estimation.currency_converter import currency_converter
from app.services.ai.requirement_extractor import requirement_extractor
from app.services.estimation.engine import estimation_engine
from app.db.session import get_db_connection
from app.core.security import hash_password, verify_password

client = TestClient(app)


# =====================================================================
# PRIORITY 1: MMRE, MdMRE, PRED(25) MATHEMATICAL CORRECTNESS & TIERS
# =====================================================================

def test_priority1_exact_prompt_metric_example():
    """
    Exact example from Master Bug Fixing prompt:
    Actual values: [100, 200, 400, 800]
    Predicted values: [90, 220, 300, 1000]
    Relative errors:
      100: |100-90|/100 = 10%
      200: |200-220|/200 = 10%
      400: |400-300|/400 = 25%
      800: |800-1000|/800 = 25%
    Expected results:
      MMRE = 17.5%
      MdMRE = 17.5%
      PRED(25) = 100.0%
    """
    actuals = [100.0, 200.0, 400.0, 800.0]
    preds = [90.0, 220.0, 300.0, 1000.0]

    metrics = calculate_relative_error_metrics(actuals, preds)

    assert metrics["eligible_count"] == 4
    assert metrics["excluded_count"] == 0
    assert pytest.approx(metrics["mmre"], 0.01) == 17.5
    assert pytest.approx(metrics["mdmre"], 0.01) == 17.5
    assert pytest.approx(metrics["pred25"], 0.01) == 100.0


def test_priority1_changed_values_alter_metrics_accordingly():
    """
    Proves that a changed actual or predicted value alters MMRE, MdMRE, and PRED(25).
    """
    actuals = [100.0, 200.0, 400.0, 800.0]
    preds_worse = [50.0, 400.0, 800.0, 2000.0]  # Errors: 50%, 100%, 100%, 150%

    metrics = calculate_relative_error_metrics(actuals, preds_worse)

    assert metrics["eligible_count"] == 4
    # MMRE = (0.50 + 1.00 + 1.00 + 1.50) / 4 = 1.00 -> 100%
    assert pytest.approx(metrics["mmre"], 0.01) == 100.0
    # MdMRE = median(0.50, 1.00, 1.00, 1.50) = 1.00 -> 100%
    assert pytest.approx(metrics["mdmre"], 0.01) == 100.0
    # PRED(25) = 0% because all errors > 25%
    assert metrics["pred25"] == 0.0


def test_priority1_zero_negative_and_missing_actuals_safely_excluded():
    """
    Ensures missing, non-finite, or <= 0 actuals are excluded safely without crashing.
    """
    actuals = [100.0, 0.0, -50.0, None, float("nan"), 200.0]
    preds = [90.0, 10.0, 20.0, 100.0, 100.0, 220.0]

    metrics = calculate_relative_error_metrics(actuals, preds)

    assert metrics["eligible_count"] == 2  # Only 100 and 200 are eligible
    assert metrics["excluded_count"] == 4
    assert len(metrics["exclusion_reasons"]) > 0
    assert pytest.approx(metrics["mmre"], 0.01) == 10.0


def test_priority1_empty_evaluation_dataset_handling():
    """
    Empty dataset must return 0.0 with clear exclusion metadata, never throwing ZeroDivisionError.
    """
    metrics = calculate_relative_error_metrics([], [])
    assert metrics["eligible_count"] == 0
    assert metrics["excluded_count"] == 0
    assert metrics["mmre"] == 0.0
    assert metrics["mdmre"] == 0.0
    assert metrics["pred25"] == 0.0


def test_priority1_individual_estimate_accuracy():
    """
    Tests individual accuracy calculation for verified project outcome:
    Actual = 200, Pred = 220 -> error = 20, relative error = 10%, within PRED(25) = True.
    """
    res = calculate_individual_accuracy(actual=200.0, predicted=220.0)
    assert res["is_eligible"] is True
    assert pytest.approx(res["absolute_error"], 0.01) == 20.0
    assert pytest.approx(res["mre_pct"], 0.01) == 10.0
    assert res["is_within_pred25"] is True


def test_priority1_cumulative_outcomes_endpoint():
    """
    Tests the GET /api/v1/projects/outcomes/metrics endpoint.
    """
    resp = client.get("/api/v1/projects/outcomes/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "cost_metrics" in data
    assert "effort_metrics" in data
    assert "duration_metrics" in data
    assert "total_completed_projects" in data


# =====================================================================
# PRIORITY 2: CURRENCY CONVERSION & FINANCIAL INVARIANTS
# =====================================================================

def test_priority2_exact_prompt_currency_example():
    """
    Prompt requirement:
    If canonical amount is ₹100 and configured conversion rate is 0.01 USD per INR,
    the displayed amount should be $1.00.
    Converting back using inverse rate should restore ₹100 within rounding tolerance.
    """
    canonical_inr = 100.0
    rate_target_per_inr = 0.01  # USD per INR

    # Converted = canonical * exchange_rate
    conv = currency_converter.convert_amount(canonical_inr, target_currency="USD", custom_rate=rate_target_per_inr)
    usd_amount = conv["converted_amount"]
    assert pytest.approx(usd_amount, 0.001) == 1.00

    # Converting back using inverse rate
    rev = currency_converter.reverse_convert_to_inr(usd_amount, target_currency="USD", custom_rate=rate_target_per_inr)
    restored_inr = rev["reversed_inr"]
    assert pytest.approx(restored_inr, 0.01) == 100.0


def test_priority2_all_components_converted_consistently():
    """
    Verifies that all budget components (labour, UI/UX, dev, qa, devops, infra, tooling, contingency, bounds)
    are converted using the same rate convention.
    """
    sample_budget = {
        "final_budget": 1000000.0,
        "final_build_budget_inr": 1000000.0,
        "total_labour_cost": 800000.0,
        "labour_cost_inr": 800000.0,
        "uiux_cost": 100000.0,
        "frontend_cost": 250000.0,
        "backend_cost": 300000.0,
        "qa_cost": 80000.0,
        "devops_cost": 70000.0,
        "total_infrastructure_cost": 100000.0,
        "one_time_infrastructure_setup_inr": 100000.0,
        "tooling_cost": 50000.0,
        "software_tooling_setup_inr": 50000.0,
        "other_direct_costs": 0.0,
        "other_direct_costs_inr": 0.0,
        "pre_contingency_subtotal": 950000.0,
        "pre_contingency_cost_inr": 950000.0,
        "contingency_cost": 50000.0,
        "contingency_amount_inr": 50000.0,
        "contingency_pct": 5.0,
        "lower_bound_pessimistic_cost": 850000.0,
        "upper_bound_optimistic_cost": 1200000.0,
        "role_breakdown": {
            "Frontend Developer": {"role_cost": 250000.0, "hourly_rate": 1200.0, "hours": 208.3},
        },
    }

    # Convert to USD using rate 83.50 INR per USD (0.011976 USD per INR)
    converted = currency_converter.convert_budget_components(sample_budget, "USD")

    rate_usd = 1.0 / 83.50
    assert pytest.approx(converted["final_budget"], 0.5) == sample_budget["final_budget"] * rate_usd
    assert pytest.approx(converted["total_labour_cost"], 0.5) == sample_budget["total_labour_cost"] * rate_usd
    assert pytest.approx(converted["total_infrastructure_cost"], 0.5) == sample_budget["total_infrastructure_cost"] * rate_usd
    assert pytest.approx(converted["contingency_cost"], 0.5) == sample_budget["contingency_cost"] * rate_usd
    assert pytest.approx(converted["lower_bound_pessimistic_cost"], 0.5) == sample_budget["lower_bound_pessimistic_cost"] * rate_usd
    assert pytest.approx(converted["upper_bound_optimistic_cost"], 0.5) == sample_budget["upper_bound_optimistic_cost"] * rate_usd


def test_priority2_non_monetary_invariants_preserved():
    """
    Changing display currency must NOT change:
    - Engineering effort hours
    - Team size
    - Delivery duration days
    - Risk scores
    """
    est_inr = estimation_engine.estimate(
        project_name="Currency Invariant Test",
        project_type="SaaS Platform",
        currency="INR",
        team_size=4,
    )
    est_usd = estimation_engine.estimate(
        project_name="Currency Invariant Test",
        project_type="SaaS Platform",
        currency="USD",
        team_size=4,
    )

    # Invariants
    assert est_inr["effort"]["total_expected_effort_hours"] == est_usd["effort"]["total_expected_effort_hours"]
    assert est_inr["timeline"]["likely_calendar_days"] == est_usd["timeline"]["likely_calendar_days"]
    assert est_inr["risk"]["risk_score"] == est_usd["risk"]["risk_score"]
    assert est_inr["inputs_echo"]["team_size"] == est_usd["inputs_echo"]["team_size"]

    # Only monetary amount changed
    assert est_inr["budget"]["final_budget"] != est_usd["budget"]["final_budget"]
    rate_usd = 1.0 / 83.50
    assert pytest.approx(est_usd["budget"]["final_budget"], 1.0) == est_inr["budget"]["final_budget"] * rate_usd


# =====================================================================
# PRIORITY 3: STEP 4 HOURLY RATE PROFILE & ROLE RECONCILIATION
# =====================================================================

def test_priority3_rate_profile_changes_cost_while_effort_remains_invariant():
    """
    Changing hourly rate profile (Startup vs Enterprise) must change role rates and total labour cost,
    while engineering effort hours remain invariant.
    """
    est_startup = estimation_engine.estimate(
        project_name="Rate Profile Test",
        rate_profile="Startup",
        currency="INR",
    )
    est_enterprise = estimation_engine.estimate(
        project_name="Rate Profile Test",
        rate_profile="Enterprise",
        currency="INR",
    )

    # Effort remains identical
    assert est_startup["effort"]["total_expected_effort_hours"] == est_enterprise["effort"]["total_expected_effort_hours"]

    # Enterprise labour cost must be strictly higher than Startup
    assert est_enterprise["budget"]["total_labour_cost"] > est_startup["budget"]["total_labour_cost"]
    assert est_enterprise["budget"]["final_budget"] > est_startup["budget"]["final_budget"]


def test_priority3_role_cost_reconciliation_formula():
    """
    Role Cost = Allocated Role Hours * Role Hourly Rate
    Total Labour Cost = Sum of All Active Role Costs
    """
    est = estimation_engine.estimate(project_name="Formula Reconciliation", currency="INR")
    budget = est["budget"]
    roles = budget["role_breakdown"]

    sum_role_costs = 0.0
    for role_name, role_data in roles.items():
        expected_role_cost = role_data["allocated_hours"] * role_data["hourly_rate_inr"]
        assert pytest.approx(role_data["role_cost_inr"], 0.5) == expected_role_cost
        sum_role_costs += role_data["role_cost_inr"]

    assert pytest.approx(budget["total_labour_cost"], 0.5) == sum_role_costs


# =====================================================================
# PRIORITY 4: PROFILE PASSWORD CHANGE — 7 REGRESSION TESTS
# =====================================================================

def test_priority4_password_change_regression_suite():
    """
    Executes the 7 exact regression tests specified in Priority 4:
    1. Correct current password + valid new password: success.
    2. Incorrect current password: rejected.
    3. Mismatched new password and confirmation: rejected.
    4. Empty required fields: rejected.
    5. Login using the new password: success.
    6. Login using the old password after a successful change: rejected.
    7. Another user's password remains unchanged.
    """
    unique_suffix = uuid.uuid4().hex[:8]
    user1_email = f"user1_{unique_suffix}@costpilot.ai"
    user2_email = f"user2_{unique_suffix}@costpilot.ai"
    initial_pwd = "InitialPassword@123"
    updated_pwd = "NewSecurePassword@456"

    # Register User 1
    reg1 = client.post("/api/v1/auth/register", json={
        "full_name": "Test User 1",
        "email": user1_email,
        "password": initial_pwd,
        "confirm_password": initial_pwd,
    })
    assert reg1.status_code == 200, reg1.text
    token1 = reg1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Register User 2
    reg2 = client.post("/api/v1/auth/register", json={
        "full_name": "Test User 2",
        "email": user2_email,
        "password": initial_pwd,
        "confirm_password": initial_pwd,
    })
    assert reg2.status_code == 200, reg2.text

    # REGRESSION TEST 2: Incorrect current password -> rejected (HTTP 400)
    bad_curr = client.post("/api/v1/auth/change-password", headers=headers1, json={
        "current_password": "WrongPassword@999",
        "new_password": updated_pwd,
        "confirm_new_password": updated_pwd,
    })
    assert bad_curr.status_code == 400
    assert "Current password is incorrect" in bad_curr.json()["detail"]

    # REGRESSION TEST 3: Mismatched new password and confirmation -> rejected (HTTP 422)
    mismatch = client.post("/api/v1/auth/change-password", headers=headers1, json={
        "current_password": initial_pwd,
        "new_password": updated_pwd,
        "confirm_new_password": "DifferentPassword@789",
    })
    assert mismatch.status_code == 422

    # REGRESSION TEST 4: Empty required fields -> rejected (HTTP 422)
    empty_req = client.post("/api/v1/auth/change-password", headers=headers1, json={
        "current_password": "",
        "new_password": "",
        "confirm_new_password": "",
    })
    assert empty_req.status_code == 422

    # REGRESSION TEST 1: Correct current password + valid new password -> success
    good_change = client.post("/api/v1/auth/change-password", headers=headers1, json={
        "current_password": initial_pwd,
        "new_password": updated_pwd,
        "confirm_new_password": updated_pwd,
    })
    assert good_change.status_code == 200
    assert good_change.json()["status"] == "success"

    # REGRESSION TEST 5: Login using the new password -> success
    login_new = client.post("/api/v1/auth/login", json={
        "email": user1_email,
        "password": updated_pwd,
    })
    assert login_new.status_code == 200
    assert "access_token" in login_new.json()

    # REGRESSION TEST 6: Login using the old password after successful change -> rejected (HTTP 401)
    login_old = client.post("/api/v1/auth/login", json={
        "email": user1_email,
        "password": initial_pwd,
    })
    assert login_old.status_code == 401

    # REGRESSION TEST 7: Another user's password remains unchanged -> User 2 logs in with initial_pwd
    login_user2 = client.post("/api/v1/auth/login", json={
        "email": user2_email,
        "password": initial_pwd,
    })
    assert login_user2.status_code == 200
    assert "access_token" in login_user2.json()


# =====================================================================
# PRIORITY 5: AI SCOPE EXTRACTION ACROSS 6 SPECIFIED DOMAINS
# =====================================================================

@pytest.mark.parametrize("domain_title,proj_name,proj_desc,expected_domain_key,key_feature_tokens", [
    (
        "Food delivery platform",
        "BiteSprint",
        "Food delivery platform connecting diners with local restaurants and delivery drivers",
        "Food Delivery Platform",
        ["restaurant", "menu", "cart", "order", "driver", "gps"],
    ),
    (
        "E-commerce marketplace",
        "GlobalBazaar",
        "E-commerce multi-vendor marketplace with cart, checkout, payments and reviews",
        "E-commerce",
        ["catalog", "cart", "checkout", "payment", "review"],
    ),
    (
        "College management system",
        "Apex Campus LMS",
        "College management system for students, faculty, syllabus, exams and fees",
        "Learning Management System",
        ["student", "course", "attendance", "grade", "fee"],
    ),
    (
        "Hospital appointment and patient management system",
        "MedPulse Care",
        "Hospital appointment and patient management system with EHR and doctor scheduling",
        "Healthcare Portal",
        ["patient", "doctor", "appointment", "ehr", "prescription"],
    ),
    (
        "AI-powered document analysis SaaS",
        "DocuSense AI",
        "AI-powered document analysis SaaS using OCR and LLMs for summarization and extraction",
        "AI Document Analysis SaaS",
        ["ocr", "extraction", "vector", "summary", "api key"],
    ),
    (
        "Basic portfolio website",
        "DevFolio Personal",
        "Basic portfolio website showcasing web developer projects, skills and contact form",
        "Portfolio Website",
        ["hero", "project", "skill", "contact", "responsive"],
    ),
])
def test_priority5_six_domain_archetypes_and_feature_extraction(
    domain_title, proj_name, proj_desc, expected_domain_key, key_feature_tokens
):
    """
    Verifies that all 6 required domains produce appropriate, distinct, non-canned features
    with catalog-derived effort and accurate explicit/inferred tagging.
    """
    res = requirement_extractor.extract(project_name=proj_name, description=proj_desc)

    assert res.project_type == expected_domain_key
    assert len(res.features) >= 5

    feature_names_lower = " ".join([f.name.lower() for f in res.features])

    # Check that domain-relevant features are present
    matched_tokens = [tok for tok in key_feature_tokens if tok in feature_names_lower]
    assert len(matched_tokens) >= 3, f"Features for {domain_title} missing key terms. Found: {feature_names_lower}"

    # Verify that each feature has catalog-derived effort and range
    for f in res.features:
        assert f.estimated_effort_hours > 0.0
        assert "hrs" in f.effort_range
        assert f.status == "recommended"
        assert isinstance(f.is_explicit, bool)
        assert isinstance(f.is_inferred, bool)


def test_priority5_portfolio_website_does_not_contain_irrelevant_enterprise_features():
    """
    Ensures a basic portfolio website does not recommend irrelevant enterprise features
    such as multi-tenant workspace isolation or payment gateways.
    """
    res = requirement_extractor.extract(
        project_name="John Doe Portfolio",
        description="Basic portfolio website showcasing web developer projects and skills.",
    )
    feature_names = [f.name.lower() for f in res.features]

    assert not any("multi-tenant" in n for n in feature_names)
    assert not any("payment gateway" in n for n in feature_names)
    assert any("contact form" in n or "hero" in n for n in feature_names)


# =====================================================================
# PRIORITY 6: END-TO-END ESTIMATION & SAVED PROJECT RESTORATION
# =====================================================================

def test_priority6_end_to_end_formula_consistency():
    """
    Verifies the end-to-end mathematical formulas:
      Pre-Contingency Cost = Total Labour + Infrastructure + Tooling + Other Direct Costs
      Contingency Cost = Pre-Contingency Cost * Contingency Rate
      Final Budget = Pre-Contingency Cost + Contingency Cost
    """
    est = estimation_engine.estimate(
        project_name="E2E Consistency Project",
        currency="INR",
        contingency_rate=10.0,
    )
    budget = est["budget"]

    pre_contingency = (
        budget["total_labour_cost"]
        + budget["total_infrastructure_cost"]
        + budget["tooling_cost"]
        + budget["other_direct_costs"]
    )
    assert pytest.approx(budget["pre_contingency_subtotal"], 0.5) == pre_contingency

    expected_contingency = pre_contingency * 0.10
    assert pytest.approx(budget["contingency_cost"], 0.5) == expected_contingency

    expected_final = pre_contingency + expected_contingency
    assert pytest.approx(budget["final_budget"], 0.5) == expected_final


def test_priority6_save_and_reload_project_preserves_configuration():
    """
    Saves an estimate to SQLite and verifies reloading restores currency, rate profile,
    and financial values accurately.
    """
    unique_suffix = uuid.uuid4().hex[:8]
    user_email = f"e2e_user_{unique_suffix}@test.com"
    pwd = "TestPassword@123"

    reg = client.post("/api/v1/auth/register", json={
        "full_name": "E2E User",
        "email": user_email,
        "password": pwd,
        "confirm_password": pwd,
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Generate estimate
    est = estimation_engine.estimate(
        project_name="Persisted Architecture Project",
        rate_profile="Enterprise",
        currency="INR",
    )

    # Save project
    save_resp = client.post("/api/v1/projects", headers=headers, json={
        "project_name": "Persisted Architecture Project",
        "description": "Full-stack project saved to test state restoration.",
        "project_type": "SaaS Platform",
        "rate_profile": "Enterprise",
        "currency": "INR",
        "estimate": est,
    })
    assert save_resp.status_code == 200, save_resp.text
    saved_project_id = save_resp.json()["id"]

    # Reload project
    get_resp = client.get(f"/api/v1/projects/{saved_project_id}", headers=headers)
    assert get_resp.status_code == 200
    loaded = get_resp.json()

    assert loaded["name"] == "Persisted Architecture Project"
    assert loaded["rate_profile"] == "Enterprise"
    assert loaded["latest_estimate"] is not None
    assert pytest.approx(loaded["latest_estimate"]["budget"]["final_budget"], 1.0) == est["budget"]["final_budget"]
    assert pytest.approx(loaded["final_budget_inr"], 1.0) == est["budget"]["final_build_budget_inr"]
