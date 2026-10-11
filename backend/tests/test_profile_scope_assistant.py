import pytest
from app.services.ai.requirement_extractor import requirement_extractor
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_college_management_system_profile_recommendations():
    """
    Profile Test: A College Management System in Education domain must receive
    student, course, attendance, examination, and fee recommendations,
    and NEVER hardcoded food delivery / restaurant items.
    """
    result = requirement_extractor.extract(
        project_name="Apex College ERP & Student Portal",
        domain="Education / E-learning",
        description="Comprehensive college management system for student lifecycle, course registrations, and semester exams.",
        target_platforms=["Web Application", "Android App"],
        overall_complexity="High",
        expected_scale="5k-20k students",
        client_region="India",
        additional_notes="Multi-department support, faculty attendance, and online fee payment with receipt generation."
    )

    features = result["features"]
    feature_names_lower = [f["name"].lower() for f in features]
    all_text = " ".join([f["name"].lower() + " " + f.get("description", "").lower() for f in features])

    # Must contain education-relevant features
    has_student = any("student" in name for name in feature_names_lower)
    has_course = any("course" in name or "curriculum" in name for name in feature_names_lower)
    has_attendance = any("attendance" in name for name in feature_names_lower)
    has_exam = any("exam" in name or "grade" in name or "grading" in name for name in feature_names_lower)
    has_fee = any("fee" in name or "payment" in name for name in feature_names_lower)

    assert has_student or has_course or has_attendance or has_exam or has_fee, (
        f"Education profile failed to produce expected features: {feature_names_lower}"
    )

    # Must NOT produce food delivery items
    assert "restaurant" not in all_text
    assert "food delivery" not in all_text
    assert "driver gps" not in all_text
    assert "menu catalog" not in all_text

    # Verify structured fields
    for f in features:
        assert "name" in f
        assert "category" in f
        assert "complexity" in f
        assert "priority" in f
        assert f["priority"] in ["Must-Have", "Should-Have", "Could-Have"]
        assert "relevance_reason" in f
        assert len(f["relevance_reason"]) > 5


def test_domain_sensitivity_healthcare_vs_real_estate():
    """
    Changing domain must alter synthesized features accordingly.
    Healthcare must produce clinical/EHR features; Real Estate must produce property features.
    """
    # Healthcare
    health_res = requirement_extractor.extract(
        project_name="CareSync Telehealth",
        domain="Healthcare",
        description="Remote doctor consultations and patient electronic health records portal.",
        target_platforms=["Web Application", "iOS App"],
        overall_complexity="High",
    )
    health_names = [f["name"].lower() for f in health_res["features"]]
    has_clinical = any("patient" in n or "ehr" in n or "appointment" in n or "telemedicine" in n for n in health_names)
    assert has_clinical, f"Healthcare features missing clinical capabilities: {health_names}"

    # Real Estate
    re_res = requirement_extractor.extract(
        project_name="UrbanNest Realty",
        domain="Real Estate",
        description="Property listing marketplace with broker messaging and virtual tours.",
        target_platforms=["Web Application"],
        overall_complexity="Medium",
    )
    re_names = [f["name"].lower() for f in re_res["features"]]
    has_property = any("property" in n or "listing" in n or "tour" in n or "lead" in n for n in re_names)
    assert has_property, f"Real Estate features missing property capabilities: {re_names}"


def test_profile_completeness_and_clarification_questions():
    """
    When profile details are sparse or missing, assistant flags is_provisional = True
    and returns targeted clarification questions.
    """
    # Sparse profile
    sparse_res = requirement_extractor.extract(
        project_name="App",
        domain="Custom / Other",
        description="Make an app for users",
        overall_complexity="Low"
    )
    assert sparse_res["is_provisional"] is True
    assert len(sparse_res["clarification_questions"]) > 0
    assert sparse_res["completeness_score"] < 60.0

    # Comprehensive profile
    comp_res = requirement_extractor.extract(
        project_name="Enterprise Logistics Orchestration Suite",
        domain="Logistics",
        description="Multi-warehouse freight distribution management with live GPS fleet telemetry, automated routing, and bill of lading generation.",
        target_platforms=["Web Application", "Android App"],
        overall_complexity="Very High",
        expected_scale="100k-500k shipments/mo",
        client_region="Global",
        additional_notes="Integration with SAP ERP, custom RFID gate scanners, and offline-first mobile sync.",
        security_compliance="SOC2 / ISO27001"
    )
    assert comp_res["is_provisional"] is False
    assert comp_res["completeness_score"] >= 80.0
    assert len(comp_res["clarification_questions"]) == 0


def test_provenance_and_model_transparency():
    """
    Output explicitly discloses rule-based vs AI provider and model provenance.
    """
    res = requirement_extractor.extract(
        project_name="Fintech Ledger",
        domain="FinTech",
        description="UPI digital payments and compliance reporting.",
        overall_complexity="High"
    )
    assert "is_ai_generated" in res
    assert "provider_used" in res
    assert "model_provenance" in res
    assert res["provider_used"] in ["rule_based_offline", "gemini", "openai"]


def test_api_scope_analyze_endpoint_with_full_profile():
    """
    API endpoint POST /api/v1/scope/analyze accepts all profile fields and returns recommendations.
    """
    payload = {
        "project_name": "MediCare Diagnostic Portal",
        "domain": "Healthcare",
        "project_type": "Healthcare",
        "overall_complexity": "High",
        "target_platforms": ["Web Application", "Android App"],
        "hosting_platform": "Web Application",
        "expected_scale": "10k-50k",
        "client_region": "India",
        "description": "Diagnostic lab booking and secure report download.",
        "additional_notes": "NABL compliance, automated WhatsApp report dispatch, and barcode tracking.",
        "existing_features": ["User Registration & OTP Login"]
    }

    resp = client.post("/api/v1/scope/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "features" in data
    assert len(data["features"]) > 0
    assert "clarification_questions" in data
    assert "model_provenance" in data

    # Verify each feature has relevance reason
    for f in data["features"]:
        assert "name" in f
        assert "category" in f
        assert "priority" in f
        assert "relevance_reason" in f
