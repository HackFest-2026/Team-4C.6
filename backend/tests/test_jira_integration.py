"""
Unit and integration tests for CostPilot AI Jira Cloud REST API v3 Integration.
All tests use mocked HTTP responses using unittest.mock / httpx mocking.
Zero live outbound network calls are made. Zero real credentials required.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.estimation.jira_client import (
    JiraCloudClient,
    text_to_adf,
    JiraConfigurationError,
    JiraAuthenticationError,
    JiraPermissionError,
    JiraRateLimitError,
    JiraNotFoundError,
    JiraValidationError,
    JiraConnectionError,
)
from app.services.estimation.integrations import integration_service

client = TestClient(app)


# Sample Mock WBS Data
SAMPLE_WBS = {
    "project_name": "E-Commerce Cloud Engine",
    "total_effort_hours": 96.0,
    "modules": [
        {
            "module_id": "MOD-01",
            "name": "User Identity & Authentication",
            "description": "User registration, login, and token session management.",
            "total_module_hours": 32.0,
            "features": [
                {
                    "id": "FEAT-01",
                    "feature_name": "JWT Authentication & Role RBAC",
                    "category": "Security",
                    "complexity": "Medium",
                    "total_effort_hours": 32.0,
                    "tasks": [
                        {
                            "task_id": "TSK-01",
                            "task_name": "Implement JWT Middleware",
                            "description": "Configure token issuance, verification, and revocation.",
                            "effort_hours": {"likely": 16.0},
                            "required_role": "Backend Developer",
                            "acceptance_criteria": [
                                "Validate RS256 signed JWT tokens",
                                "Handle expired token refresh"
                            ]
                        },
                        {
                            "task_id": "TSK-02",
                            "task_name": "Create RBAC Permission Guards",
                            "description": "Add role-based authorization decorator.",
                            "effort_hours": {"likely": 16.0},
                            "required_role": "Backend Developer",
                            "acceptance_criteria": [
                                "Enforce Admin, Editor, and Viewer roles"
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}


# =====================================================================
# 1. ADF CONVERTER TESTS
# =====================================================================

def test_text_to_adf_structure():
    """Verifies that plain text and criteria are correctly converted to Atlassian Document Format v1."""
    adf = text_to_adf(
        summary_text="Build checkout cart",
        description_body="Paragraph 1 description.\n\nParagraph 2 details.",
        acceptance_criteria=["Must support Stripe", "Must validate VAT tax"],
        metadata={"effort_hours": 24.0, "role": "Full-Stack Developer", "complexity": "High"}
    )

    assert adf["version"] == 1
    assert adf["type"] == "doc"
    assert isinstance(adf["content"], list)
    assert len(adf["content"]) >= 4

    # Paragraphs check
    paras = [c for c in adf["content"] if c["type"] == "paragraph"]
    assert len(paras) >= 2

    # Heading and bullet list check
    headings = [c for c in adf["content"] if c["type"] == "heading"]
    assert len(headings) >= 1
    assert headings[0]["attrs"]["level"] == 3

    lists = [c for c in adf["content"] if c["type"] == "bulletList"]
    assert len(lists) >= 1
    assert len(lists[0]["content"]) == 2

    # Panel check
    panels = [c for c in adf["content"] if c["type"] == "panel"]
    assert len(panels) >= 1
    assert panels[0]["attrs"]["panelType"] == "info"


# =====================================================================
# 2. CLIENT CONFIGURATION & SECURITY TESTS
# =====================================================================

def test_client_configuration_missing():
    """Verifies that JiraCloudClient properly detects unconfigured state and raises JiraConfigurationError."""
    unconfigured_client = JiraCloudClient(
        base_url="",
        email="",
        api_token="",
        default_project_key=""
    )

    assert unconfigured_client.is_configured is False
    status = unconfigured_client.get_status()
    assert status["configured"] is False
    assert status["email_configured"] is False
    assert status["api_token_configured"] is False
    # Crucial security check: api_token must NOT be present in status
    assert "api_token" not in status

    with pytest.raises(JiraConfigurationError) as exc_info:
        unconfigured_client.test_connection()
    assert "Missing environment variable" in str(exc_info.value)


def test_status_endpoint_never_leaks_secrets():
    """Verifies GET /api/v1/integrations/jira/status never exposes secrets."""
    res = client.get("/api/v1/integrations/jira/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    jira_info = data["jira"]

    # Security check: Token value must never appear
    assert "api_token" not in jira_info
    assert "token" not in jira_info
    assert "api_token_configured" in jira_info
    assert "configured" in jira_info


# =====================================================================
# 3. HTTP ERROR HANDLING TESTS (401, 403, 404, 429)
# =====================================================================

def test_test_connection_success():
    """Verifies test_connection() parses successful Jira user identity."""
    test_c = JiraCloudClient(
        base_url="https://costpilot.atlassian.net",
        email="developer@costpilot.ai",
        api_token="test-secret-token",
        default_project_key="CP"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "accountId": "5b10ac8d82e05b22cc7d4ef5",
        "displayName": "CostPilot Lead Developer",
        "emailAddress": "developer@costpilot.ai",
        "active": True,
        "timeZone": "UTC",
        "accountType": "atlassian"
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        res = test_c.test_connection()
        assert res["success"] is True
        assert res["connected"] is True
        assert res["display_name"] == "CostPilot Lead Developer"
        assert res["email_address"] == "developer@costpilot.ai"
        assert res["site_url"] == "https://costpilot.atlassian.net"


def test_test_connection_401_unauthorized():
    """Verifies HTTP 401 returns informative JiraAuthenticationError without leaking token."""
    test_c = JiraCloudClient(
        base_url="https://costpilot.atlassian.net",
        email="developer@costpilot.ai",
        api_token="invalid-token"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.json.return_value = {"errorMessages": ["Unauthorized"]}
    mock_resp.text = '{"errorMessages": ["Unauthorized"]}'

    with patch("httpx.Client.get", return_value=mock_resp):
        with pytest.raises(JiraAuthenticationError) as exc_info:
            test_c.test_connection()
        assert "Jira authentication failed" in str(exc_info.value)
        assert "invalid-token" not in str(exc_info.value)


def test_create_issue_403_forbidden():
    """Verifies HTTP 403 returns JiraPermissionError."""
    test_c = JiraCloudClient(
        base_url="https://costpilot.atlassian.net",
        email="dev@example.com",
        api_token="valid-token"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.json.return_value = {"errorMessages": ["User does not have permission to create issues in project 'CP'."]}

    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(JiraPermissionError) as exc_info:
            test_c.create_issue(
                project_key="CP",
                summary="Test Issue",
                issue_type_name="Task"
            )
        assert "Permission denied" in str(exc_info.value)


def test_create_issue_429_rate_limit():
    """Verifies HTTP 429 returns JiraRateLimitError with Retry-After header."""
    test_c = JiraCloudClient(
        base_url="https://costpilot.atlassian.net",
        email="dev@example.com",
        api_token="valid-token"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"Retry-After": "45"}
    mock_resp.json.return_value = {"errorMessages": ["Rate limit exceeded"]}

    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(JiraRateLimitError) as exc_info:
            test_c.create_issue(
                project_key="CP",
                summary="Rate Limited Task",
                issue_type_name="Task"
            )
        assert exc_info.value.retry_after == 45
        assert "rate limit exceeded" in str(exc_info.value).lower()


# =====================================================================
# 4. HIERARCHICAL ISSUE CREATION & PARENT-CHILD LINKING
# =====================================================================

def test_sync_wbs_to_jira_hierarchical_success():
    """
    Verifies full 3-level hierarchy creation:
      MOD-01 (Epic) -> FEAT-01 (Story, parented to Epic) -> TSK-01/02 (Sub-tasks, parented to Story).
    """
    test_c = JiraCloudClient(
        base_url="https://costpilot.atlassian.net",
        email="lead@costpilot.ai",
        api_token="mock-token",
        default_project_key="CP"
    )

    # Mock project issue types resolution
    mock_project_types_resp = MagicMock()
    mock_project_types_resp.status_code = 200
    mock_project_types_resp.json.return_value = {
        "issueTypes": [
            {"id": "10000", "name": "Epic", "subtask": False, "hierarchyLevel": 1},
            {"id": "10001", "name": "Story", "subtask": False, "hierarchyLevel": 0},
            {"id": "10002", "name": "Sub-task", "subtask": True, "hierarchyLevel": -1},
        ]
    }

    created_counter = {"val": 100}
    recorded_calls = []

    def mock_post(url, *args, **kwargs):
        created_counter["val"] += 1
        new_key = f"CP-{created_counter['val']}"
        payload = kwargs.get("json", {})
        recorded_calls.append({"url": url, "payload": payload, "key": new_key})

        resp = MagicMock()
        resp.status_code = 201
        resp.json.return_value = {
            "id": str(created_counter["val"]),
            "key": new_key,
            "self": f"https://costpilot.atlassian.net/rest/api/3/issue/{new_key}"
        }
        return resp

    with patch("httpx.Client.get", return_value=mock_project_types_resp), \
         patch("httpx.Client.post", side_effect=mock_post):

        result = test_c.sync_wbs_to_jira(
            project={"name": "E-Commerce Cloud Engine"},
            wbs=SAMPLE_WBS,
            target_project_key="CP"
        )

        assert result["status"] == "completed"
        assert result["total_attempted"] == 4
        assert result["total_created"] == 4
        assert result["epics_created"] == 1
        assert result["stories_created"] == 1
        assert result["subtasks_created"] == 2
        assert len(result["errors"]) == 0

        # Verify parent relationships:
        # Call 0: Epic CP-101
        # Call 1: Story CP-102 with parent: {key: CP-101}
        # Call 2: Sub-task CP-103 with parent: {key: CP-102}
        # Call 3: Sub-task CP-104 with parent: {key: CP-102}
        assert recorded_calls[0]["payload"]["fields"]["issuetype"]["name"] == "Epic"
        assert "parent" not in recorded_calls[0]["payload"]["fields"]

        assert recorded_calls[1]["payload"]["fields"]["issuetype"]["name"] == "Story"
        assert recorded_calls[1]["payload"]["fields"]["parent"]["key"] == "CP-101"

        assert recorded_calls[2]["payload"]["fields"]["issuetype"]["name"] == "Sub-task"
        assert recorded_calls[2]["payload"]["fields"]["parent"]["key"] == "CP-102"

        assert recorded_calls[3]["payload"]["fields"]["issuetype"]["name"] == "Sub-task"
        assert recorded_calls[3]["payload"]["fields"]["parent"]["key"] == "CP-102"


def test_sync_wbs_to_jira_partial_failure_recovery():
    """
    Verifies that if one task fails, the sync does not crash,
    reports partial_success, lists created issues, and captures error details.
    """
    test_c = JiraCloudClient(
        base_url="https://costpilot.atlassian.net",
        email="lead@costpilot.ai",
        api_token="mock-token",
        default_project_key="CP"
    )

    mock_types = MagicMock()
    mock_types.status_code = 200
    mock_types.json.return_value = {
        "issueTypes": [
            {"id": "1", "name": "Epic", "subtask": False},
            {"id": "2", "name": "Story", "subtask": False},
            {"id": "3", "name": "Sub-task", "subtask": True},
        ]
    }

    call_index = [0]
    def mock_post_with_partial_fail(url, *args, **kwargs):
        call_index[0] += 1
        # Make call 3 (second subtask) fail with 400
        if call_index[0] == 4:
            resp = MagicMock()
            resp.status_code = 400
            resp.json.return_value = {"errorMessages": ["Custom field validation failed"]}
            return resp

        resp = MagicMock()
        resp.status_code = 201
        resp.json.return_value = {"id": f"10{call_index[0]}", "key": f"CP-10{call_index[0]}"}
        return resp

    with patch("httpx.Client.get", return_value=mock_types), \
         patch("httpx.Client.post", side_effect=mock_post_with_partial_fail):

        result = test_c.sync_wbs_to_jira(
            project={"name": "E-Commerce Cloud Engine"},
            wbs=SAMPLE_WBS,
            target_project_key="CP"
        )

        assert result["status"] == "partial_success"
        assert result["total_created"] == 3
        assert len(result["errors"]) == 1
        assert result["errors"][0]["costpilot_id"] == "TSK-02"


# =====================================================================
# 5. FASTAPI REST ROUTE ENDPOINT TESTS
# =====================================================================

def test_api_test_connection_endpoint():
    """Tests POST /api/v1/integrations/jira/test endpoint with mock client."""
    mock_identity = {
        "success": True,
        "connected": True,
        "site_url": "https://company.atlassian.net",
        "account_id": "acc-1234",
        "display_name": "QA Specialist",
        "email_address": "qa@company.com",
        "active": True,
        "time_zone": "Asia/Kolkata",
        "account_type": "atlassian",
        "verified_at": "2026-10-11T12:00:00Z"
    }

    with patch("app.services.estimation.jira_client.jira_cloud_client.test_connection", return_value=mock_identity):
        res = client.post("/api/v1/integrations/jira/test")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["result"]["display_name"] == "QA Specialist"


def test_api_get_projects_endpoint():
    """Tests GET /api/v1/integrations/jira/projects."""
    mock_projects = [
        {"id": "10001", "key": "CP", "name": "CostPilot Core", "project_type_key": "software", "is_default": True},
        {"id": "10002", "key": "AI", "name": "AI Models", "project_type_key": "software", "is_default": False}
    ]

    with patch("app.services.estimation.jira_client.jira_cloud_client.get_accessible_projects", return_value=mock_projects):
        res = client.get("/api/v1/integrations/jira/projects")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert len(data["projects"]) == 2
        assert data["projects"][0]["key"] == "CP"


def test_api_direct_sync_malformed_wbs():
    """Tests POST /api/v1/integrations/jira/create-issues rejects malformed WBS."""
    res = client.post("/api/v1/integrations/jira/create-issues", json={
        "project_name": "Test App",
        "target_project_key": "CP",
        "wbs": {}  # Missing modules
    })
    assert res.status_code == 400
    assert "Invalid WBS payload" in res.json()["detail"]


def test_api_direct_sync_success():
    """Tests POST /api/v1/integrations/jira/create-issues successfully triggers sync."""
    mock_sync_result = {
        "status": "completed",
        "project_name": "Test App",
        "jira_project_key": "CP",
        "site_url": "https://test.atlassian.net",
        "total_attempted": 3,
        "total_created": 3,
        "epics_created": 1,
        "stories_created": 1,
        "subtasks_created": 1,
        "created_issues": [
            {"costpilot_id": "MOD-01", "type": "Epic", "jira_key": "CP-1", "browse_url": "https://test.atlassian.net/browse/CP-1"},
            {"costpilot_id": "FEAT-01", "type": "Story", "jira_key": "CP-2", "browse_url": "https://test.atlassian.net/browse/CP-2"},
            {"costpilot_id": "TSK-01", "type": "Sub-task", "jira_key": "CP-3", "browse_url": "https://test.atlassian.net/browse/CP-3"}
        ],
        "errors": []
    }

    with patch("app.services.estimation.jira_client.jira_cloud_client.sync_wbs_to_jira", return_value=mock_sync_result):
        res = client.post("/api/v1/integrations/jira/create-issues", json={
            "project_name": "Test App",
            "target_project_key": "CP",
            "wbs": SAMPLE_WBS
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["sync_result"]["total_created"] == 3


def test_existing_offline_jira_json_export_preserved():
    """Verifies that the existing client/backend Jira standard JSON exporter remains 100% operational."""
    project = {"name": "Preserved Project"}
    exported = integration_service.export_to_jira_json(project, SAMPLE_WBS)

    assert exported["exporter"] == "CostPilot AI Jira Integration v2.0"
    assert "jira_payload" in exported
    assert "projects" in exported["jira_payload"]
    issues = exported["jira_payload"]["projects"][0]["issues"]
    assert len(issues) >= 3  # 1 Epic + 1 Story + 2 Sub-tasks = 4 issues
    assert issues[0]["issueType"] == "Epic"
    assert issues[1]["issueType"] == "Story"
    assert issues[2]["issueType"] == "Sub-task"
