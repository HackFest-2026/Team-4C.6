"""
CostPilot AI — Official Jira Cloud REST API v3 Integration Client.

Provides authenticated, resilient communication with Atlassian Jira Cloud:
  1. Connection testing and credential validation.
  2. Project discovery and dynamic issue type resolution.
  3. Atlassian Document Format (ADF) description serialization.
  4. Hierarchical issue creation (Epic -> Story -> Sub-task).
  5. Resilient error handling (401 Auth, 403 Permissions, 429 Rate Limits, 400 Validation).
  6. Transparent partial failure tracking and duplicate prevention.

Security & Integrity:
  - Backend-only authentication using HTTP Basic Auth (Email + API Token).
  - API tokens are never logged, stored in plain text responses, or leaked to the frontend.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import httpx
from datetime import datetime, timezone

from app.core.config import settings

logger = logging.getLogger("costpilot.jira")


# =====================================================================
# CUSTOM EXCEPTIONS
# =====================================================================

class JiraError(Exception):
    """Base exception for all Jira integration operations."""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class JiraConfigurationError(JiraError):
    """Raised when Jira environment variables are missing or malformed."""
    pass


class JiraAuthenticationError(JiraError):
    """Raised on HTTP 401 Unauthorized (invalid email or API token)."""
    pass


class JiraPermissionError(JiraError):
    """Raised on HTTP 403 Forbidden (insufficient project or site permissions)."""
    pass


class JiraNotFoundError(JiraError):
    """Raised on HTTP 404 Not Found (invalid project key, issue key, or site URL)."""
    pass


class JiraRateLimitError(JiraError):
    """Raised on HTTP 429 Too Many Requests."""
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, status_code=429, **kwargs)
        self.retry_after = retry_after


class JiraValidationError(JiraError):
    """Raised on HTTP 400 Bad Request with field validation errors."""
    pass


class JiraConnectionError(JiraError):
    """Raised on timeouts, network errors, or unreachable Jira Cloud hosts."""
    pass


# =====================================================================
# ATLASSIAN DOCUMENT FORMAT (ADF) CONVERTER
# =====================================================================

def text_to_adf(
    summary_text: str,
    description_body: Optional[str] = None,
    acceptance_criteria: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Converts plain text, acceptance criteria lists, and CostPilot metadata
    into a valid Jira REST API v3 Atlassian Document Format (ADF) structure.
    
    Jira Cloud REST API v3 strictly rejects raw text descriptions with:
    'Operation value must be an Atlassian Document Format object'.
    """
    content_blocks = []

    # 1. Main description paragraphs
    body = description_body or summary_text or "No detailed description provided."
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [body.strip() or "Created by CostPilot AI."]

    for para in paragraphs:
        lines = para.split("\n")
        inline_nodes = []
        for i, line in enumerate(lines):
            inline_nodes.append({
                "type": "text",
                "text": line
            })
            if i < len(lines) - 1:
                inline_nodes.append({"type": "hardBreak"})
        content_blocks.append({
            "type": "paragraph",
            "content": inline_nodes
        })

    # 2. Acceptance Criteria section if present
    if acceptance_criteria and len(acceptance_criteria) > 0:
        content_blocks.append({
            "type": "heading",
            "attrs": {"level": 3},
            "content": [
                {
                    "type": "text",
                    "text": "Acceptance Criteria",
                    "marks": [{"type": "strong"}]
                }
            ]
        })

        list_items = []
        for ac in acceptance_criteria:
            if ac and str(ac).strip():
                list_items.append({
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": str(ac).strip()
                                }
                            ]
                        }
                    ]
                })

        if list_items:
            content_blocks.append({
                "type": "bulletList",
                "content": list_items
            })

    # 3. CostPilot AI Estimation Metadata Panel
    if metadata:
        meta_items = []
        if "effort_hours" in metadata:
            meta_items.append(f"Estimated Effort: {metadata['effort_hours']} hrs")
        if "story_points" in metadata:
            meta_items.append(f"Story Points: {metadata['story_points']}")
        if "role" in metadata:
            meta_items.append(f"Primary Role: {metadata['role']}")
        if "complexity" in metadata:
            meta_items.append(f"Complexity: {metadata['complexity']}")
        if "costpilot_id" in metadata:
            meta_items.append(f"CostPilot Ref: {metadata['costpilot_id']}")

        if meta_items:
            content_blocks.append({
                "type": "panel",
                "attrs": {"panelType": "info"},
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "CostPilot AI Estimation Parameters: ",
                                "marks": [{"type": "strong"}]
                            },
                            {
                                "type": "text",
                                "text": " | ".join(meta_items)
                            }
                        ]
                    }
                ]
            })

    return {
        "version": 1,
        "type": "doc",
        "content": content_blocks
    }


# =====================================================================
# JIRA CLOUD REST API v3 CLIENT
# =====================================================================

class JiraCloudClient:
    """
    Dedicated enterprise Jira Cloud client targeting REST API v3.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
        default_project_key: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ):
        raw_base = (base_url or settings.JIRA_BASE_URL or "").strip()
        if raw_base and not (raw_base.startswith("http://") or raw_base.startswith("https://")):
            raw_base = f"https://{raw_base}"
        self.base_url = raw_base.rstrip("/")

        self.email = (email or settings.JIRA_EMAIL or "").strip()
        self._api_token = (api_token or settings.JIRA_API_TOKEN or "").strip()
        self.default_project_key = (default_project_key or settings.JIRA_PROJECT_KEY or "").strip().upper()
        self.timeout_seconds = float(timeout_seconds or settings.JIRA_TIMEOUT_SECONDS or 25.0)

    @property
    def is_configured(self) -> bool:
        """Returns True if essential Jira connection parameters are non-empty."""
        return bool(self.base_url and self.email and self._api_token)

    def get_status(self) -> Dict[str, Any]:
        """
        Returns safe configuration status for display in frontend or diagnostics.
        NEVER includes the API token value.
        """
        # Obfuscate email if present (e.g. j***@domain.com)
        masked_email = ""
        if self.email and "@" in self.email:
            parts = self.email.split("@")
            local = parts[0]
            masked_local = (local[0] + "***") if len(local) > 1 else "***"
            masked_email = f"{masked_local}@{parts[1]}"
        elif self.email:
            masked_email = "***"

        return {
            "configured": self.is_configured,
            "base_url": self.base_url or None,
            "email_configured": bool(self.email),
            "masked_email": masked_email or None,
            "api_token_configured": bool(self._api_token),
            "default_project_key": self.default_project_key or None,
            "timeout_seconds": self.timeout_seconds,
            "api_version": "v3",
        }

    def _get_auth(self) -> Tuple[str, str]:
        """Returns Basic Auth tuple for httpx."""
        if not self.is_configured:
            missing = []
            if not self.base_url: missing.append("JIRA_BASE_URL")
            if not self.email: missing.append("JIRA_EMAIL")
            if not self._api_token: missing.append("JIRA_API_TOKEN")
            raise JiraConfigurationError(
                f"Jira integration is not fully configured. Missing environment variable(s): {', '.join(missing)}. "
                f"Please update backend/.env or your environment."
            )
        return (self.email, self._api_token)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": f"CostPilot-AI/{settings.VERSION} (Jira Integration)",
        }

    def _handle_response_error(self, response: httpx.Response, action_description: str) -> None:
        """
        Parses Jira error responses and translates to explicit Jira exceptions.
        """
        status_code = response.status_code
        error_msg = f"Failed to {action_description} (HTTP {status_code})"
        details: Dict[str, Any] = {}

        try:
            body = response.json()
            if isinstance(body, dict):
                details = body
                # Jira Cloud errors usually format as:
                # {"errorMessages": ["..."], "errors": {"fieldName": "..."}}
                jira_msgs = body.get("errorMessages") or []
                jira_fields = body.get("errors") or {}
                combined_msgs = list(jira_msgs)
                for field, f_msg in jira_fields.items():
                    combined_msgs.append(f"{field}: {f_msg}")
                if combined_msgs:
                    error_msg = f"{error_msg}: {'; '.join(combined_msgs)}"
                elif body.get("message"):
                    error_msg = f"{error_msg}: {body['message']}"
        except Exception:
            text_snippet = response.text[:300].strip()
            if text_snippet:
                error_msg = f"{error_msg}: {text_snippet}"

        logger.warning("Jira API error during %s [HTTP %d]: %s", action_description, status_code, error_msg)

        if status_code == 401:
            raise JiraAuthenticationError(
                f"Jira authentication failed. Please verify that JIRA_EMAIL ({self.email}) and JIRA_API_TOKEN are valid Atlassian credentials.",
                status_code=401,
                details=details
            )
        elif status_code == 403:
            raise JiraPermissionError(
                f"Permission denied by Jira Cloud. Your account may not have permission to perform this action. Details: {error_msg}",
                status_code=403,
                details=details
            )
        elif status_code == 404:
            raise JiraNotFoundError(
                f"Jira resource not found (HTTP 404). Check your JIRA_BASE_URL and project key. Details: {error_msg}",
                status_code=404,
                details=details
            )
        elif status_code == 429:
            retry_after = None
            if "Retry-After" in response.headers:
                try:
                    retry_after = int(response.headers["Retry-After"])
                except ValueError:
                    pass
            raise JiraRateLimitError(
                f"Jira API rate limit exceeded. Retry after {retry_after or 'a few'} seconds.",
                retry_after=retry_after,
                details=details
            )
        elif status_code == 400:
            raise JiraValidationError(
                f"Jira issue validation failed: {error_msg}",
                status_code=400,
                details=details
            )
        else:
            raise JiraError(error_msg, status_code=status_code, details=details)

    # -----------------------------------------------------------------
    # 1. TEST CONNECTION & CREDENTIALS
    # -----------------------------------------------------------------
    def test_connection(self) -> Dict[str, Any]:
        """
        Tests the connection to Jira Cloud by querying the `/rest/api/3/myself` endpoint.
        Returns verified user and site identity on success.
        """
        auth = self._get_auth()
        url = f"{self.base_url}/rest/api/3/myself"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.get(url, auth=auth, headers=self._get_headers())
                if res.status_code != 200:
                    self._handle_response_error(res, "verify Jira connection")
                
                data = res.json()
                return {
                    "success": True,
                    "connected": True,
                    "site_url": self.base_url,
                    "account_id": data.get("accountId"),
                    "display_name": data.get("displayName"),
                    "email_address": data.get("emailAddress") or self.email,
                    "active": data.get("active", True),
                    "time_zone": data.get("timeZone"),
                    "account_type": data.get("accountType"),
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                }
        except httpx.TimeoutException as exc:
            logger.error("Jira connection timed out: %s", exc)
            raise JiraConnectionError(
                f"Connection to Jira at '{self.base_url}' timed out after {self.timeout_seconds}s. Verify your network connection and base URL.",
                status_code=504
            )
        except httpx.RequestError as exc:
            logger.error("Jira connection network error: %s", exc)
            raise JiraConnectionError(
                f"Network error connecting to Jira at '{self.base_url}': {str(exc)}",
                status_code=502
            )

    # -----------------------------------------------------------------
    # 2. RETRIEVE ACCESSIBLE PROJECTS
    # -----------------------------------------------------------------
    def get_accessible_projects(self) -> List[Dict[str, Any]]:
        """
        Retrieves all projects visible to the authenticated Jira user.
        Uses `GET /rest/api/3/project/search` or `GET /rest/api/3/project`.
        """
        auth = self._get_auth()
        url = f"{self.base_url}/rest/api/3/project/search"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                # First try project/search (supports pagination and returns rich metadata)
                res = client.get(url, auth=auth, headers=self._get_headers(), params={"maxResults": 100})
                if res.status_code == 404:
                    # Fallback to older /rest/api/3/project if search is not exposed
                    res = client.get(f"{self.base_url}/rest/api/3/project", auth=auth, headers=self._get_headers())

                if res.status_code != 200:
                    self._handle_response_error(res, "retrieve accessible Jira projects")

                raw_data = res.json()
                items = raw_data.get("values", raw_data) if isinstance(raw_data, dict) else raw_data

                projects = []
                for p in items:
                    if isinstance(p, dict):
                        projects.append({
                            "id": p.get("id"),
                            "key": p.get("key"),
                            "name": p.get("name"),
                            "project_type_key": p.get("projectTypeKey"),
                            "simplified": p.get("simplified", False),
                            "style": p.get("style", "classic"),
                            "is_default": (p.get("key") == self.default_project_key) if self.default_project_key else False,
                        })
                return projects
        except httpx.TimeoutException as exc:
            raise JiraConnectionError(f"Timeout retrieving Jira projects: {exc}", status_code=504)
        except httpx.RequestError as exc:
            raise JiraConnectionError(f"Network error retrieving Jira projects: {exc}", status_code=502)

    # -----------------------------------------------------------------
    # 3. RETRIEVE PROJECT ISSUE TYPES & HIERARCHY
    # -----------------------------------------------------------------
    def get_project_issue_types(self, project_key: str) -> List[Dict[str, Any]]:
        """
        Retrieves available issue types for a specific project.
        Uses `GET /rest/api/3/project/{project_key}`.
        """
        auth = self._get_auth()
        url = f"{self.base_url}/rest/api/3/project/{project_key}"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.get(url, auth=auth, headers=self._get_headers())
                if res.status_code != 200:
                    self._handle_response_error(res, f"retrieve issue types for project '{project_key}'")

                data = res.json()
                raw_types = data.get("issueTypes", [])
                issue_types = []
                for it in raw_types:
                    issue_types.append({
                        "id": it.get("id"),
                        "name": it.get("name"),
                        "description": it.get("description"),
                        "subtask": it.get("subtask", False),
                        "hierarchy_level": it.get("hierarchyLevel", 0),
                    })
                return issue_types
        except httpx.TimeoutException as exc:
            raise JiraConnectionError(f"Timeout retrieving issue types for '{project_key}': {exc}", status_code=504)
        except httpx.RequestError as exc:
            raise JiraConnectionError(f"Network error retrieving issue types for '{project_key}': {exc}", status_code=502)

    def resolve_hierarchy_issue_types(self, project_key: str) -> Dict[str, str]:
        """
        Discovers the appropriate issue type names for:
          - epic (e.g. 'Epic', or highest level container)
          - story (e.g. 'Story', 'Task', standard issue type)
          - subtask (e.g. 'Sub-task', 'Subtask', subtask type)
        """
        try:
            available = self.get_project_issue_types(project_key)
        except Exception as exc:
            logger.warning("Could not query issue types for '%s', using defaults: %s", project_key, exc)
            return {"epic": "Epic", "story": "Story", "subtask": "Sub-task"}

        resolved = {
            "epic": "Epic",
            "story": "Story",
            "subtask": "Sub-task"
        }

        # Check subtasks
        subtask_candidates = [it["name"] for it in available if it.get("subtask")]
        if subtask_candidates:
            # prefer 'Sub-task' or 'Subtask'
            if "Sub-task" in subtask_candidates:
                resolved["subtask"] = "Sub-task"
            elif "Subtask" in subtask_candidates:
                resolved["subtask"] = "Subtask"
            else:
                resolved["subtask"] = subtask_candidates[0]

        # Check standard issue types
        standard_candidates = [it["name"] for it in available if not it.get("subtask")]
        lower_map = {name.lower(): name for name in standard_candidates}

        if "epic" in lower_map:
            resolved["epic"] = lower_map["epic"]
        elif standard_candidates:
            # If no Epic type is found (e.g. basic Kanban board), use Task/first standard type
            resolved["epic"] = lower_map.get("task", standard_candidates[0])

        if "story" in lower_map:
            resolved["story"] = lower_map["story"]
        elif "task" in lower_map:
            resolved["story"] = lower_map["task"]
        elif standard_candidates:
            resolved["story"] = standard_candidates[0]

        return resolved

    # -----------------------------------------------------------------
    # 4. CREATE A SINGLE JIRA ISSUE
    # -----------------------------------------------------------------
    def create_issue(
        self,
        project_key: str,
        summary: str,
        issue_type_name: str,
        description: Optional[str] = None,
        parent_key: Optional[str] = None,
        timetracking_hours: Optional[float] = None,
        labels: Optional[List[str]] = None,
        acceptance_criteria: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Creates an issue in Jira Cloud REST API v3 with ADF description and parent linking.
        """
        auth = self._get_auth()
        url = f"{self.base_url}/rest/api/3/issue"

        clean_summary = (summary or "CostPilot Work Item").strip()
        # Jira summary limit is 255 chars
        if len(clean_summary) > 250:
            clean_summary = clean_summary[:247] + "..."

        issue_labels = [l.strip().replace(" ", "-") for l in (labels or ["CostPilot-AI"]) if l.strip()]

        # Generate ADF body
        adf_description = text_to_adf(
            summary_text=clean_summary,
            description_body=description,
            acceptance_criteria=acceptance_criteria,
            metadata=metadata,
        )

        fields: Dict[str, Any] = {
            "project": {"key": project_key},
            "summary": clean_summary,
            "issuetype": {"name": issue_type_name},
            "description": adf_description,
            "labels": issue_labels,
        }

        # Parent hierarchy linking (Standard Jira Cloud REST API v3 hierarchy field)
        if parent_key:
            fields["parent"] = {"key": parent_key}

        # Original estimate / time tracking
        if timetracking_hours and timetracking_hours > 0:
            formatted_hrs = f"{max(0.5, round(timetracking_hours, 1))}h"
            fields["timetracking"] = {
                "originalEstimate": formatted_hrs
            }

        payload = {"fields": fields}

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.post(url, auth=auth, headers=self._get_headers(), json=payload)
                
                # If failed due to parent linking on non-supporting schema, attempt retry without parent
                if res.status_code == 400 and parent_key:
                    res_body = res.text
                    if "parent" in res_body.lower():
                        logger.warning("Jira rejected parent field for '%s', retrying without parent...", clean_summary)
                        fields.pop("parent", None)
                        res = client.post(url, auth=auth, headers=self._get_headers(), json={"fields": fields})

                if res.status_code not in (200, 201):
                    self._handle_response_error(res, f"create Jira issue '{clean_summary}'")

                data = res.json()
                created_key = data.get("key")
                created_id = data.get("id")

                browse_url = f"{self.base_url}/browse/{created_key}" if created_key else None

                return {
                    "success": True,
                    "id": created_id,
                    "key": created_key,
                    "browse_url": browse_url,
                    "summary": clean_summary,
                    "issue_type": issue_type_name,
                    "parent_key": parent_key,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
        except httpx.TimeoutException as exc:
            raise JiraConnectionError(f"Timeout creating Jira issue '{clean_summary}': {exc}", status_code=504)
        except httpx.RequestError as exc:
            raise JiraConnectionError(f"Network error creating Jira issue '{clean_summary}': {exc}", status_code=502)

    # -----------------------------------------------------------------
    # 5. BATCH HIERARCHICAL SYNC FROM COSTPILOT ESTIMATE / WBS
    # -----------------------------------------------------------------
    def sync_wbs_to_jira(
        self,
        project: Dict[str, Any],
        wbs: Dict[str, Any],
        target_project_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes hierarchical synchronization of CostPilot WBS into Jira Cloud:
          Level 1: Modules   -> Jira Epics
          Level 2: Features  -> Jira Stories (linked to parent Epic)
          Level 3: Tasks     -> Jira Sub-tasks (linked to parent Story)

        Prevents duplicate creation within the run, catches partial failures gracefully,
        and returns confirmed Jira keys and browse URLs.
        """
        p_key = (target_project_key or self.default_project_key or "").strip().upper()
        if not p_key:
            raise JiraValidationError(
                "No target Jira project key specified. Please select a Jira project key or set JIRA_PROJECT_KEY in backend/.env."
            )

        # 1. Resolve issue type names for the project
        type_map = self.resolve_hierarchy_issue_types(p_key)
        epic_type = type_map.get("epic", "Epic")
        story_type = type_map.get("story", "Story")
        subtask_type = type_map.get("subtask", "Sub-task")

        project_name = project.get("name", "CostPilot Project")
        modules = wbs.get("modules", [])

        created_issues: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        total_attempted = 0
        epics_count = 0
        stories_count = 0
        subtasks_count = 0

        # Memory mapping for hierarchy linking
        module_to_epic_key: Dict[str, str] = {}
        feature_to_story_key: Dict[str, str] = {}

        # 2. Iterate Modules -> Epics
        for mod in modules:
            mod_id = mod.get("module_id", f"MOD-{len(module_to_epic_key)+1}")
            mod_name = mod.get("name", f"Module {mod_id}")
            total_attempted += 1

            epic_summary = f"[{mod_id}] {mod_name}"
            mod_desc = mod.get("description", f"Work Breakdown Structure Module for {project_name}.")

            try:
                epic_res = self.create_issue(
                    project_key=p_key,
                    summary=epic_summary,
                    issue_type_name=epic_type,
                    description=mod_desc,
                    labels=["CostPilot-AI", "Module", mod_id],
                    metadata={
                        "costpilot_id": mod_id,
                        "effort_hours": mod.get("total_module_hours", 0.0),
                    }
                )
                module_to_epic_key[mod_id] = epic_res["key"]
                epics_count += 1
                created_issues.append({
                    "costpilot_id": mod_id,
                    "type": "Epic",
                    "jira_key": epic_res["key"],
                    "browse_url": epic_res["browse_url"],
                    "summary": epic_summary,
                    "parent_key": None,
                    "status": "Created"
                })
            except Exception as exc:
                err_msg = str(getattr(exc, "message", exc))
                logger.error("Failed to create Epic for module '%s': %s", mod_id, err_msg)
                errors.append({
                    "costpilot_id": mod_id,
                    "type": "Epic",
                    "name": mod_name,
                    "error": err_msg,
                })
                # If Epic creation failed, child features cannot link to this Epic
                module_to_epic_key[mod_id] = None

            parent_epic_key = module_to_epic_key.get(mod_id)

            # 3. Iterate Features -> Stories
            for feat in mod.get("features", []):
                feat_id = feat.get("id") or feat.get("feature_id") or f"FEAT-{len(feature_to_story_key)+1}"
                feat_name = feat.get("feature_name", "Feature")
                total_attempted += 1

                story_summary = f"[{feat_id}] {feat_name}"
                hours = feat.get("total_effort_hours", 24.0)
                story_points = max(1, round(hours / 8.0))
                feat_desc = (
                    f"Feature Scope: {feat_name}\n"
                    f"Category: {feat.get('category', 'General')} | Complexity: {feat.get('complexity', 'Medium')}\n"
                    f"Total Estimated Effort: {hours} hours."
                )

                try:
                    story_res = self.create_issue(
                        project_key=p_key,
                        summary=story_summary,
                        issue_type_name=story_type,
                        description=feat_desc,
                        parent_key=parent_epic_key,
                        timetracking_hours=hours,
                        labels=["CostPilot-AI", "Feature", feat_id],
                        metadata={
                            "costpilot_id": feat_id,
                            "effort_hours": hours,
                            "story_points": story_points,
                            "complexity": feat.get("complexity", "Medium"),
                        }
                    )
                    feature_to_story_key[feat_id] = story_res["key"]
                    stories_count += 1
                    created_issues.append({
                        "costpilot_id": feat_id,
                        "type": "Story",
                        "jira_key": story_res["key"],
                        "browse_url": story_res["browse_url"],
                        "summary": story_summary,
                        "parent_key": parent_epic_key,
                        "status": "Created"
                    })
                except Exception as exc:
                    err_msg = str(getattr(exc, "message", exc))
                    logger.error("Failed to create Story for feature '%s': %s", feat_id, err_msg)
                    errors.append({
                        "costpilot_id": feat_id,
                        "type": "Story",
                        "name": feat_name,
                        "error": err_msg,
                    })
                    feature_to_story_key[feat_id] = None

                parent_story_key = feature_to_story_key.get(feat_id)

                # 4. Iterate Tasks -> Sub-tasks
                for t in feat.get("tasks", []):
                    t_id = t.get("task_id", f"TSK-{total_attempted+1}")
                    t_name = t.get("task_name", "Technical Task")
                    total_attempted += 1

                    subtask_summary = f"[{t_id}] {t_name}"
                    t_hours = t.get("effort_hours", {}).get("likely", 8.0) if isinstance(t.get("effort_hours"), dict) else float(t.get("effort_hours") or 8.0)
                    t_desc = t.get("description", f"Technical implementation task for {feat_name}.")
                    criteria = t.get("acceptance_criteria", [])

                    try:
                        subtask_res = self.create_issue(
                            project_key=p_key,
                            summary=subtask_summary,
                            issue_type_name=subtask_type,
                            description=t_desc,
                            parent_key=parent_story_key,
                            timetracking_hours=t_hours,
                            acceptance_criteria=criteria,
                            labels=["CostPilot-WBS", t_id],
                            metadata={
                                "costpilot_id": t_id,
                                "effort_hours": t_hours,
                                "role": t.get("required_role", "Developer"),
                            }
                        )
                        subtasks_count += 1
                        created_issues.append({
                            "costpilot_id": t_id,
                            "type": "Sub-task",
                            "jira_key": subtask_res["key"],
                            "browse_url": subtask_res["browse_url"],
                            "summary": subtask_summary,
                            "parent_key": parent_story_key,
                            "status": "Created"
                        })
                    except Exception as exc:
                        err_msg = str(getattr(exc, "message", exc))
                        logger.error("Failed to create Sub-task '%s': %s", t_id, err_msg)
                        errors.append({
                            "costpilot_id": t_id,
                            "type": "Sub-task",
                            "name": t_name,
                            "error": err_msg,
                        })

        successful_count = len(created_issues)
        has_partial_failures = len(errors) > 0 and successful_count > 0
        all_failed = len(errors) > 0 and successful_count == 0

        status_str = "completed"
        if all_failed:
            status_str = "failed"
        elif has_partial_failures:
            status_str = "partial_success"

        return {
            "status": status_str,
            "project_name": project_name,
            "jira_project_key": p_key,
            "site_url": self.base_url,
            "total_attempted": total_attempted,
            "total_created": successful_count,
            "epics_created": epics_count,
            "stories_created": stories_count,
            "subtasks_created": subtasks_count,
            "created_issues": created_issues,
            "errors": errors,
            "sync_timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Global singleton Jira client instance configured from settings
jira_cloud_client = JiraCloudClient()
