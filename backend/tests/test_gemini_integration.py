"""
CostPilot AI — Comprehensive Verification Suite for Google Gemini LLM Integration
Covers:
  1. Offline mode preserves rule-based behavior
  2. Gemini mode invokes Gemini client
  3. Structured Gemini output maps to ExtractedFeature & Result schema
  4. Distinct project descriptions yield distinct features
  5. Empty/malformed response triggers safe fallback
  6. Normalization of invalid complexity, unknown categories, and duplicates
  7. Missing API key reports unavailability without falsely claiming Gemini
  8. Timeouts and API exceptions trigger fallback
  9. API responses and logs never leak API keys
 10. Gemini-generated features flow into /estimate, WBS, resource optimizer, and costing
 11. Unrecognized AI_PROVIDER emits warning and uses fallback
 12. Optional live integration test (skipped unless real credentials configured)
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services.ai.requirement_extractor import (
    RequirementExtractor,
    GeminiScopeExtractor,
    GeminiScopeExtractionSchema,
    GeminiFeatureSchema,
    requirement_extractor,
)

client = TestClient(app)


# =====================================================================
# HELPER: MOCK GEMINI RAW RESPONSE OBJECT
# =====================================================================
def make_mock_gemini_response(features_data, summary="Decomposed system architecture"):
    """Creates a mock response object mirroring google-genai generate_content response."""
    gf_items = [GeminiFeatureSchema(**f) for f in features_data]
    schema_obj = GeminiScopeExtractionSchema(
        project_summary=summary,
        features=gf_items,
        recommended_tech_stack={"frontend_stack": "React", "backend_stack": "FastAPI_Python", "database": "PostgreSQL", "hosting_platform": "GCP"},
        missing_requirements=["Payment gateway compliance (PCI-DSS) details pending."],
        clarification_questions=["What is the expected peak concurrent user load?"],
        assumptions=["Cloud native microservices architecture deployed to Kubernetes."]
    )
    mock_resp = MagicMock()
    mock_resp.parsed = schema_obj
    mock_resp.text = schema_obj.model_dump_json()
    return mock_resp


# =====================================================================
# TEST 1: OFFLINE MODE PRESERVES RULE-BASED BEHAVIOR
# =====================================================================
def test_offline_mode_preserves_rule_based_behavior(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "offline")
    
    res = requirement_extractor.extract(
        project_name="CarePulse Telehealth",
        domain="healthcare",
        description="Doctor consultation and appointment scheduling system.",
        overall_complexity="High",
        target_platforms=["Web Application", "iOS Application"]
    )
    
    assert res.is_ai_generated is False
    assert res.provider_used == "rule_based_offline"
    assert "Profile Rules Engine" in res.model_provenance
    assert len(res.features) > 0
    assert any("Doctor" in f.name or "Patient" in f.name for f in res.features)


# =====================================================================
# TEST 2: GEMINI MODE INVOKES GEMINI CLIENT
# =====================================================================
def test_gemini_mode_invokes_gemini_client(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_API_KEY", "test-dummy-api-key-12345")
    
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = make_mock_gemini_response([
        {
            "name": "Biometric Multi-Factor Authentication",
            "category": "Authentication",
            "complexity": "High",
            "description": "FIDO2 WebAuthn biometric login with fallback SMS OTP.",
            "relevance_reason": "Ensures zero-trust security compliance.",
            "priority": "Must-Have",
            "dependencies": [],
            "integration_requirements": ["WebAuthn API"],
            "acceptance_criteria": ["Users can authenticate via fingerprint or FaceID in under 500ms."],
            "suggested_tasks": ["Implement WebAuthn credentials registration", "Build challenge-response verifier"],
            "required_roles": ["Security Specialist", "Backend Developer"],
            "risk_factors": ["Hardware token compatibility on legacy devices"]
        },
        {
            "name": "Live Realtime Video Teleconsultation",
            "category": "Real-time features",
            "complexity": "Very High",
            "description": "Encrypted WebRTC peer-to-peer audio/video streaming room.",
            "relevance_reason": "Core clinical encounter channel between physician and patient.",
            "priority": "Must-Have",
            "dependencies": ["Biometric Multi-Factor Authentication"],
            "integration_requirements": ["LiveKit / Agora WebRTC API"],
            "acceptance_criteria": ["High-definition 1080p stream with end-to-end SRTP encryption."],
            "suggested_tasks": ["Set up SFU streaming relay", "Integrate client video controls"],
            "required_roles": ["Frontend Developer", "Backend Developer"],
            "risk_factors": ["Bandwidth degradation on mobile cellular networks"]
        }
    ])
    
    gemini_ext = GeminiScopeExtractor(client=mock_client)
    custom_extractor = RequirementExtractor(gemini_extractor=gemini_ext)
    
    res = custom_extractor.extract(
        project_name="CarePulse Telehealth",
        domain="healthcare",
        description="Doctor consultation and appointment scheduling system.",
        overall_complexity="High"
    )
    
    assert mock_client.models.generate_content.called
    assert res.is_ai_generated is True
    assert res.provider_used == "gemini"
    assert "Google Gemini" in res.model_provenance
    assert len(res.features) == 2
    assert res.features[0].name == "Biometric Multi-Factor Authentication"
    assert res.features[1].name == "Live Realtime Video Teleconsultation"


# =====================================================================
# TEST 3: STRUCTURED OUTPUT MAPS ACCURATELY TO SCHEMA
# =====================================================================
def test_valid_structured_gemini_output_maps_to_response_schema(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_API_KEY", "test-dummy-api-key-12345")
    
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = make_mock_gemini_response([
        {
            "name": "Electronic Health Record Vault",
            "category": "CRUD/data module",
            "complexity": "High",
            "description": "FHIR-compliant medical history store with column-level encryption.",
            "relevance_reason": "Stores vital clinical charts and lab results.",
            "priority": "Must-Have",
            "dependencies": [],
            "integration_requirements": ["AWS KMS Encryption"],
            "acceptance_criteria": ["All records encrypted at rest using AES-256."],
            "suggested_tasks": ["Design FHIR schema tables", "Build audit logging middleware"],
            "required_roles": ["Backend Developer", "Security Specialist"],
            "risk_factors": ["HIPAA audit compliance violations if improperly configured"]
        }
    ])
    
    extractor = RequirementExtractor(gemini_extractor=GeminiScopeExtractor(client=mock_client))
    res = extractor.extract(project_name="MedVault", description="Secure EHR storage")
    
    feat = res.features[0]
    assert feat.id == "gemini_rec_1"
    assert feat.name == "Electronic Health Record Vault"
    assert feat.category == "CRUD/data module"
    assert feat.complexity == "High"
    assert feat.is_provisional is True
    assert feat.estimated_effort_hours > 0.0
    assert len(feat.acceptance_criteria) > 0
    assert len(feat.suggested_tasks) > 0
    assert "Backend Developer" in feat.required_roles
    assert len(feat.risk_factors) > 0


# =====================================================================
# TEST 4: TWO DIFFERENT DESCRIPTIONS PRODUCE APPROPRIATELY DIFFERENT FEATURES
# =====================================================================
def test_two_different_descriptions_produce_different_gemini_features(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_API_KEY", "test-dummy-api-key-12345")
    
    mock_client = MagicMock()
    
    # Project 1: Healthcare
    resp_health = make_mock_gemini_response([
        {"name": "Patient Clinical Appointment Booking", "category": "Booking/scheduling", "complexity": "Medium", "description": "Consultation booking.", "relevance_reason": "Health care.", "priority": "Must-Have"},
        {"name": "EHR Prescription Dispatch", "category": "CRUD/data module", "complexity": "Medium", "description": "Digital prescriptions.", "relevance_reason": "Health care.", "priority": "Must-Have"}
    ])
    
    # Project 2: Fleet Logistics
    resp_logistics = make_mock_gemini_response([
        {"name": "Real-Time GPS Fleet Vehicle Telemetry", "category": "Real-time features", "complexity": "Very High", "description": "Live GPS coordinates.", "relevance_reason": "Logistics.", "priority": "Must-Have"},
        {"name": "Warehouse Cargo Barcode Ingestion", "category": "CRUD/data module", "complexity": "Medium", "description": "Scans pallet barcodes.", "relevance_reason": "Logistics.", "priority": "Must-Have"}
    ])
    
    mock_client.models.generate_content.side_effect = [resp_health, resp_logistics]
    extractor = RequirementExtractor(gemini_extractor=GeminiScopeExtractor(client=mock_client))
    
    res1 = extractor.extract(project_name="CarePulse", domain="healthcare", description="Doctor appointments and prescriptions")
    res2 = extractor.extract(project_name="FleetTrack", domain="logistics", description="GPS truck tracking and barcode scanning")
    
    names1 = [f.name for f in res1.features]
    names2 = [f.name for f in res2.features]
    
    assert names1 != names2
    assert "Patient Clinical Appointment Booking" in names1
    assert "Real-Time GPS Fleet Vehicle Telemetry" in names2
    assert not any(n in names2 for n in names1)


# =====================================================================
# TEST 5: EMPTY OR MALFORMED OUTPUT TRIGGERS SAFE FALLBACK
# =====================================================================
def test_empty_or_malformed_output_triggers_fallback(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_API_KEY", "test-dummy-api-key-12345")
    
    mock_client = MagicMock()
    # Mock returning an empty list of features
    empty_resp = MagicMock()
    empty_resp.parsed = GeminiScopeExtractionSchema(
        project_summary="Empty project",
        features=[],
        recommended_tech_stack={},
        missing_requirements=[],
        clarification_questions=[],
        assumptions=[]
    )
    empty_resp.text = empty_resp.parsed.model_dump_json()
    mock_client.models.generate_content.return_value = empty_resp
    
    extractor = RequirementExtractor(gemini_extractor=GeminiScopeExtractor(client=mock_client))
    res = extractor.extract(
        project_name="FinTech Ledger",
        domain="fintech",
        description="Double entry bank ledger platform."
    )
    
    # Should safely fall back to rule-based catalog
    assert res.is_ai_generated is False
    assert res.provider_used == "rule_based_offline"
    assert res.fallback_reason is not None
    assert "Gemini returned zero features" in res.fallback_reason
    assert len(res.features) > 0


# =====================================================================
# TEST 6: NORMALIZATION OF COMPLEXITY, CATEGORIES AND DUPLICATES
# =====================================================================
def test_invalid_complexity_negative_effort_duplicate_features_sanitized(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_API_KEY", "test-dummy-api-key-12345")
    
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = make_mock_gemini_response([
        {
            "name": "Audit Logging",
            "category": "UnknownWeirdCategory",
            "complexity": "UltraExtremeComplexity",
            "description": "Log records.",
            "relevance_reason": "Compliance.",
            "priority": "Must-Have"
        },
        {
            "name": "Audit Logging",  # Duplicate name
            "category": "Audit logs",
            "complexity": "Low",
            "description": "Duplicate should be dropped.",
            "relevance_reason": "Compliance.",
            "priority": "Must-Have"
        },
        {
            "name": "User Identity Management",
            "category": "Authentication",
            "complexity": "High",
            "description": "User login.",
            "relevance_reason": "Security.",
            "priority": "Must-Have"
        }
    ])
    
    extractor = RequirementExtractor(gemini_extractor=GeminiScopeExtractor(client=mock_client))
    res = extractor.extract(project_name="SecApp", description="App with audit logging")
    
    # Duplicate 'Audit Logging' should be deduplicated to 1 item
    assert len(res.features) == 2
    
    f1 = res.features[0]
    # Complexity should be normalized to Medium or project default
    assert f1.complexity in ["Low", "Medium", "High", "Very High"]
    # Category should be normalized to recognized valid set
    assert f1.category in GeminiScopeExtractor.VALID_CATEGORIES
    # Effort must be strictly positive finite number
    assert f1.estimated_effort_hours > 0.0


# =====================================================================
# TEST 7: MISSING API KEY DOES NOT FALSELY CLAIM GEMINI RESULT
# =====================================================================
def test_missing_api_key_does_not_falsely_report_gemini(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    
    # Use standard singleton which creates client from settings
    res = requirement_extractor.extract(
        project_name="Ecommerce Shop",
        domain="ecommerce",
        description="Online storefront with product catalog and shopping cart."
    )
    
    assert res.is_ai_generated is False
    assert res.provider_used == "rule_based_offline"
    assert res.fallback_reason is not None
    assert "API key is not configured" in res.fallback_reason
    assert "Profile Rules Engine" in res.model_provenance


# =====================================================================
# TEST 8: TIMEOUTS AND API ERRORS TRIGGER FALLBACK SAFELY
# =====================================================================
def test_timeouts_and_api_errors_trigger_fallback(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_API_KEY", "test-dummy-api-key-12345")
    
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TimeoutError("Deadline exceeded: connection timed out")
    
    extractor = RequirementExtractor(gemini_extractor=GeminiScopeExtractor(client=mock_client))
    res = extractor.extract(
        project_name="Logistics App",
        domain="logistics",
        description="Cargo dispatch management system."
    )
    
    assert res.is_ai_generated is False
    assert res.provider_used == "rule_based_offline"
    assert res.fallback_reason is not None
    assert "TimeoutError" in res.fallback_reason
    assert len(res.features) > 0


# =====================================================================
# TEST 9: API RESPONSES NEVER LEAK SENSITIVE SECRETS OR KEYS
# =====================================================================
def test_api_responses_never_contain_api_key(monkeypatch):
    secret_key = "AIzaSySecretNeverLeakMe998877"
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_API_KEY", secret_key)
    
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = make_mock_gemini_response([
        {"name": "Secure Vault", "category": "Security/compliance", "complexity": "High", "description": "Safe storage.", "relevance_reason": "Security.", "priority": "Must-Have"}
    ])
    
    extractor = RequirementExtractor(gemini_extractor=GeminiScopeExtractor(client=mock_client))
    res = extractor.extract(project_name="SecVault", description="Secure data vault")
    
    res_dump = res.model_dump_json()
    assert secret_key not in res_dump
    assert secret_key not in str(res.model_dump())


# =====================================================================
# TEST 10: ACCEPTED GEMINI FEATURES FLOW INTO ESTIMATE & WBS
# =====================================================================
def test_accepted_gemini_features_flow_into_estimate_and_wbs(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_API_KEY", "test-dummy-api-key-12345")
    
    # 1. Simulate scope extraction via mock
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = make_mock_gemini_response([
        {
            "name": "Custom Drone Telemetry Service",
            "category": "Real-time features",
            "complexity": "Very High",
            "description": "High frequency flight path streaming.",
            "relevance_reason": "Autonomous tracking.",
            "priority": "Must-Have",
            "dependencies": [],
            "integration_requirements": ["MAVLink Protocol"],
            "acceptance_criteria": ["Telemetry packets delivered with under 50ms latency."],
            "suggested_tasks": ["Implement UDP ingestion pipeline", "Build WebGL 3D flight visualizer"],
            "required_roles": ["Backend Developer", "Frontend Developer"],
            "risk_factors": ["Packet loss over satellite links"]
        },
        {
            "name": "Mission Dispatch Management",
            "category": "CRUD/data module",
            "complexity": "High",
            "description": "Mission waypoint planning.",
            "relevance_reason": "Flight planning.",
            "priority": "Must-Have",
            "dependencies": ["Custom Drone Telemetry Service"],
            "integration_requirements": [],
            "acceptance_criteria": ["Waypoints validated against no-fly zone geojson."],
            "suggested_tasks": ["Waypoint coordinate database schema", "GeoJSON boundary collision validator"],
            "required_roles": ["Full-Stack Developer"],
            "risk_factors": ["Outdated airspace geometry updates"]
        }
    ])
    
    # Patch the singleton's gemini_extractor client
    with patch.object(requirement_extractor.gemini_extractor, "get_client", return_value=(mock_client, None)):
        scope_resp = client.post("/api/v1/scope/analyze", json={
            "project_name": "SkyWatch Drones",
            "project_type": "Logistics",
            "domain": "logistics",
            "description": "Autonomous drone surveillance and parcel delivery management.",
            "overall_complexity": "High"
        })
        assert scope_resp.status_code == 200
        scope_data = scope_resp.json()
        assert scope_data["is_ai_generated"] is True
        assert len(scope_data["features"]) == 2
        
        extracted_feats = scope_data["features"]
        
        # 2. Feed extracted features into /estimate endpoint
        est_resp = client.post("/api/v1/estimate", json={
            "project_name": "SkyWatch Drones",
            "project_type": "Logistics",
            "overall_complexity": "High",
            "hosting_platform": "Web Application",
            "team_size": 4,
            "currency": "USD",
            "features": extracted_feats
        })
        
        assert est_resp.status_code == 200
        est_data = est_resp.json()
        
        # Verify features generated bottom-up effort & cost
        assert est_data["effort"]["total_expected_effort_hours"] > 0.0
        assert est_data["budget"]["final_build_budget_converted"] > 0.0
        
        # Verify WBS generation contains the Gemini features
        wbs = est_data.get("wbs", {})
        assert wbs.get("total_tasks_count", 0) > 0
        wbs_names = [t.get("task_name", "") + " " + t.get("feature_name", "") for t in wbs.get("flat_tasks", [])]
        assert any("Custom Drone Telemetry Service" in t_str for t_str in wbs_names)
        
        # Verify Resource Scenarios were generated
        scenarios = est_data.get("resource_scenarios", {})
        scenario_keys = [s.get("scenario_key") for s in scenarios.get("scenarios", [])]
        assert "budget_focused" in scenario_keys
        assert "balanced" in scenario_keys
        assert "deadline_focused" in scenario_keys


# =====================================================================
# TEST 11: UNRECOGNIZED AI_PROVIDER PRODUCES WARNING & FALLBACK
# =====================================================================
def test_unrecognized_ai_provider_warns_and_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "unsupported_llm_vendor")
    
    res = requirement_extractor.extract(
        project_name="Inventory Hub",
        domain="ecommerce",
        description="Retail inventory and warehouse scanner."
    )
    
    assert res.is_ai_generated is False
    assert res.provider_used == "rule_based_offline"
    assert res.warning is not None
    assert "unsupported_llm_vendor" in res.warning
    assert "Profile Rules Engine" in res.model_provenance


# =====================================================================
# TEST 12: OPTIONAL LIVE INTEGRATION TEST (SKIPPED WITHOUT REAL KEY)
# =====================================================================
@pytest.mark.skipif(
    not (
        os.getenv("AI_PROVIDER", "").lower() == "gemini"
        and bool(os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY"))
    ),
    reason="Live Gemini API key not provided. Set AI_PROVIDER=gemini and AI_API_KEY to execute live test."
)
def test_live_gemini_integration_optional():
    """Real live integration test against Google Gemini API."""
    res = requirement_extractor.extract(
        project_name="QuantumCloud IDE",
        description="Web-based development environment for quantum circuit simulation and Python algorithm execution.",
        overall_complexity="Very High",
        target_platforms=["Web Application"]
    )
    
    assert res.is_ai_generated is True
    assert res.provider_used == "gemini"
    assert "Google Gemini" in res.model_provenance
    assert len(res.features) >= 3
