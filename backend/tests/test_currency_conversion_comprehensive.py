import pytest
from app.services.estimation.currency_converter import currency_converter, CurrencyConversionError
from app.services.estimation.cost_budget import cost_budget_engine
from app.core.config import settings
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_1_base_inr_to_usd_conversion():
    """8,35,000 INR at 83.50 must convert to exactly 10,000.00 USD."""
    res = currency_converter.convert_amount(835000.0, "USD", custom_rate=83.50)
    assert res["target_amount"] == 10000.00
    assert res["converted_amount"] == 10000.00
    assert res["target_currency"] == "USD"
    assert res["exchange_rate"] == 83.50
    assert res["canonical_currency"] == "INR"
    assert res["canonical_amount_inr"] == 835000.0


def test_2_roundtrip_conversion_reversibility():
    """INR -> USD -> INR roundtrip must preserve economic value within tolerance <= 0.05 units of target currency."""
    test_amounts = [50000.0, 125430.50, 835000.0, 2500000.0]
    rate = 83.50

    for inr_val in test_amounts:
        usd_res = currency_converter.convert_amount(inr_val, "USD", custom_rate=rate)
        usd_amount = usd_res["target_amount"]
        back_inr = round(usd_amount * rate, 2)
        diff_inr = abs(inr_val - back_inr)
        diff_target = round(diff_inr / rate, 4)
        assert diff_target <= 0.05, f"Roundtrip discrepancy for {inr_val}: diff_target={diff_target}"
        assert usd_res["is_reversible"] is True


def test_3_repeated_currency_switching_stability():
    """Switching INR -> USD -> EUR -> GBP -> INR must not cause cumulative rounding drift."""
    original_inr = 1500000.00
    currencies = ["USD", "EUR", "GBP", "AUD", "CAD", "SGD", "AED", "INR"]

    # Each conversion is grounded in canonical INR ground truth
    converted_history = {}
    for c in currencies:
        conv = currency_converter.convert_amount(original_inr, c)
        converted_history[c] = conv["target_amount"]
        # Ground truth must be invariant
        assert conv["canonical_amount_inr"] == original_inr

    final_inr = currency_converter.convert_amount(original_inr, "INR")["target_amount"]
    assert final_inr == original_inr


def test_4_exchange_rate_direction_verification():
    """Strictly enforce: 1 Target Unit = R Base INR Units (Target Amount = round(Base INR / R, 2))."""
    usd_rate = settings.SUPPORTED_CURRENCIES["USD"]["rate_to_inr"]
    assert usd_rate == 83.50

    inr_val = 167000.0
    res = currency_converter.convert_amount(inr_val, "USD")
    expected = round(inr_val / usd_rate, 2)
    assert res["target_amount"] == expected
    assert res["reciprocal_rate"] == round(1.0 / usd_rate, 6)


def test_5_conversion_extreme_values():
    """Small (₹5,000) and very large (₹500,000,000) budgets maintain precision without failure."""
    small_inr = 5000.0
    large_inr = 500000000.0

    res_small = currency_converter.convert_amount(small_inr, "USD", custom_rate=83.50)
    assert res_small["target_amount"] == 59.88

    res_large = currency_converter.convert_amount(large_inr, "USD", custom_rate=83.50)
    assert res_large["target_amount"] == 5988023.95


def test_6_financial_component_breakdown_reconciliation():
    """
    Component reconciliation invariant:
    Labour Cost + Additional Direct Costs + Single-Pass Contingency == Final Build Budget (tolerance <= 0.05).
    """
    raw_budget = {
        "final_build_budget_inr": 1150000.00,
        "labour_cost_inr": 800000.00,
        "one_time_infrastructure_setup_inr": 120000.00,
        "software_tooling_setup_inr": 80000.00,
        "other_direct_costs_inr": 0.0,
        "total_additional_costs_inr": 200000.00,
        "pre_contingency_cost_inr": 1000000.00,
        "contingency_amount_inr": 150000.00,
        "contingency_pct": 15.0,
        "budget_range": {
            "low_inr": 977500.00,
            "likely_inr": 1150000.00,
            "high_inr": 1322500.00,
        },
        "role_costs": {
            "Frontend Developer": {"allocated_hours": 100, "hourly_rate_inr": 1200.0, "role_cost_inr": 120000.0},
            "Backend Developer": {"allocated_hours": 200, "hourly_rate_inr": 1400.0, "role_cost_inr": 280000.0},
            "UI/UX Designer": {"allocated_hours": 50, "hourly_rate_inr": 1100.0, "role_cost_inr": 55000.0},
            "QA/Test Engineer": {"allocated_hours": 100, "hourly_rate_inr": 900.0, "role_cost_inr": 90000.0},
            "DevOps/Cloud Engineer": {"allocated_hours": 70, "hourly_rate_inr": 1500.0, "role_cost_inr": 105000.0},
            "Project Manager": {"allocated_hours": 100, "hourly_rate_inr": 1500.0, "role_cost_inr": 150000.0},
        }
    }

    # Verify reconciliation across multiple currencies
    for curr in ["USD", "EUR", "GBP", "AUD", "INR"]:
        converted = currency_converter.convert_budget_components(raw_budget, target_currency=curr)
        assert converted["is_reconciled"] is True
        assert converted["reconciliation_discrepancy"] <= 0.05

        labour = converted["labour_cost_converted"]
        additional = converted["total_additional_costs_converted"]
        contingency = converted["contingency_amount_converted"]
        final_budget = converted["final_build_budget_converted"]

        calc_sum = round(labour + additional + contingency, 2)
        assert abs(final_budget - calc_sum) <= 0.05


def test_7_consistency_across_simulated_refresh():
    """Database persistence preserves canonical currency and amount along with conversion metadata."""
    # 1. Run estimate in USD
    est_resp = client.post("/api/v1/estimate", json={
        "project_name": "Multi-Currency Refresh Simulation",
        "project_type": "SaaS Platform",
        "overall_complexity": "Medium",
        "hosting_platform": "Web Application",
        "currency": "USD",
        "currency_exchange_rate": 83.50,
        "team_size": 4,
        "features": [{"name": "Auth Module", "category": "Authentication", "complexity": "Medium"}]
    })
    assert est_resp.status_code == 200
    est_data = est_resp.json()

    # 2. Save project to database
    save_resp = client.post("/api/v1/projects", json={
        "project_name": "Multi-Currency Refresh Simulation",
        "description": "Simulating database persistence across refresh",
        "currency": "USD",
        "currency_code": "USD",
        "estimate": est_data
    })
    assert save_resp.status_code == 200
    saved_data = save_resp.json()
    proj_id = saved_data["id"]

    # 3. Simulate page reload / fetch project from database
    get_resp = client.get(f"/api/v1/projects/{proj_id}")
    assert get_resp.status_code == 200
    proj_detail = get_resp.json()

    assert proj_detail["currency"] == "USD"
    assert proj_detail["canonical_currency"] == "INR"
    assert proj_detail["canonical_amount_inr"] > 0
    assert proj_detail["exchange_rate"] == 83.50
    assert proj_detail["final_budget_converted"] > 0
    assert proj_detail["exchange_rate_source"] is not None

    # Cleanup
    client.delete(f"/api/v1/projects/{proj_id}")


def test_8_handling_unsupported_currency():
    """Unsupported currency must raise CurrencyConversionError and reject conversion."""
    with pytest.raises(CurrencyConversionError):
        currency_converter.convert_amount(50000.0, "XYZ_NON_EXISTENT")


def test_9_negative_or_zero_rate_error_handling():
    """Negative or zero exchange rate must raise CurrencyConversionError."""
    with pytest.raises(CurrencyConversionError):
        currency_converter.convert_amount(50000.0, "USD", custom_rate=0.0)

    with pytest.raises(CurrencyConversionError):
        currency_converter.convert_amount(50000.0, "USD", custom_rate=-83.5)


def test_10_custom_exchange_rate_override():
    """Custom user exchange rate (e.g., 85.0) overrides benchmark and converts accurately."""
    res = currency_converter.convert_amount(850000.0, "USD", custom_rate=85.00)
    assert res["target_amount"] == 10000.00
    assert res["exchange_rate"] == 85.00
    assert res["is_manually_configured"] is True


def test_11_non_monetary_invariance():
    """
    Changing currency must NOT modify total effort hours, duration days, or team size.
    """
    role_allocs = {
        "Frontend Developer": {"allocated_hours": 120.0, "headcount": 1},
        "Backend Developer": {"allocated_hours": 160.0, "headcount": 1},
    }
    role_rates = {"Frontend Developer": 1200.0, "Backend Developer": 1400.0}

    # Run budget calculation in INR
    b_inr = cost_budget_engine.calculate_budget(
        total_effort_hours=280.0,
        optimistic_hours=240.0,
        pessimistic_hours=340.0,
        role_allocations=role_allocs,
        role_rates=role_rates,
        currency="INR"
    )

    # Run budget calculation in USD
    b_usd = cost_budget_engine.calculate_budget(
        total_effort_hours=280.0,
        optimistic_hours=240.0,
        pessimistic_hours=340.0,
        role_allocations=role_allocs,
        role_rates=role_rates,
        currency="USD"
    )

    # Invariants
    assert b_inr["effort_range"]["expected_hours"] == b_usd["effort_range"]["expected_hours"] == 280.0
    assert b_inr["effort_range"]["optimistic_hours"] == b_usd["effort_range"]["optimistic_hours"] == 240.0
    assert b_inr["effort_range"]["pessimistic_hours"] == b_usd["effort_range"]["pessimistic_hours"] == 340.0
    assert b_inr["canonical_amount_inr"] == b_usd["canonical_amount_inr"]


def test_12_currency_convert_api_endpoint():
    """FastAPI endpoint POST /api/v1/currency/convert converts amounts and budgets with reconciliation."""
    resp = client.post(
        "/api/v1/currency/convert",
        json={"amount": 835000.0, "target_currency": "USD", "custom_rate": 83.50}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_amount"] == 10000.00
    assert data["target_currency"] == "USD"
    assert data["canonical_currency"] == "INR"
    assert data["exchange_rate"] == 83.50
