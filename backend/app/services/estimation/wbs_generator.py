"""
CostPilot AI — Work Breakdown Structure (WBS) Generation Service.
Converts extracted project features and architectural specifications into
a defensible, hierarchical Work Breakdown Structure (Project -> Module -> Feature -> Task).

Guarantees:
  1. Unique hierarchical task IDs (e.g. WBS-1.1.1).
  2. Acceptance criteria and required role per task.
  3. Shared work isolation (prevents double-counting shared cross-cutting concerns).
  4. Explicit dependency tracking and parallelizability flags.
  5. Exact effort reconciliation (sum of task hours matches feature and project totals).
"""

from typing import Dict, Any, List, Optional
import math


class WBSGenerator:
    """
    Generates a hierarchical Work Breakdown Structure (WBS)
    from reviewed project features and technical inputs.
    """

    ROLE_CAPABILITY_MAP = {
        "Authentication": "Backend Developer",
        "Frontend": "Frontend Developer",
        "Backend": "Backend Developer",
        "Database": "Backend Developer",
        "UI/UX": "UI/UX Designer",
        "DevOps": "DevOps Engineer",
        "QA/Testing": "QA Engineer",
        "CRUD/data module": "Full-Stack Developer",
        "Payments": "Backend Developer",
        "Integrations": "Backend Developer",
        "Analytics": "Frontend Developer",
        "Security": "DevOps Engineer",
        "AI/ML": "Backend Developer",
    }

    def generate_wbs(
        self,
        project_name: str,
        project_type: str,
        features: List[Dict[str, Any]],
        overall_complexity: str = "Medium",
        platform: str = "Web Application",
    ) -> Dict[str, Any]:
        """
        Builds the hierarchical WBS tree with modules, features, and granular tasks.
        """
        modules_map: Dict[str, Dict[str, Any]] = {
            "MOD-01": {
                "module_id": "MOD-01",
                "name": "Foundational Architecture & Shared Infrastructure",
                "description": "Core frameworks, shared middlewares, deployment scaffolding, and database foundations.",
                "is_cross_cutting": True,
                "features": [],
            },
            "MOD-02": {
                "module_id": "MOD-02",
                "name": "Identity, Access & Security Governance",
                "description": "User authentication, credential handling, session management, and RBAC permissions.",
                "is_cross_cutting": False,
                "features": [],
            },
            "MOD-03": {
                "module_id": "MOD-03",
                "name": "Core Business Capabilities & Domain Workflows",
                "description": "Primary user journeys, transactional screens, catalog views, and operational processing.",
                "is_cross_cutting": False,
                "features": [],
            },
            "MOD-04": {
                "module_id": "MOD-04",
                "name": "External Integrations, APIs & Notifications",
                "description": "Third-party APIs, webhooks, payment gateways, messaging, and push notifications.",
                "is_cross_cutting": False,
                "features": [],
            },
            "MOD-05": {
                "module_id": "MOD-05",
                "name": "Administration, Governance & Reporting",
                "description": "Administrative portals, operational telemetry, metrics dashboards, and audit logs.",
                "is_cross_cutting": False,
                "features": [],
            },
            "MOD-06": {
                "module_id": "MOD-06",
                "name": "Quality Assurance, Hardening & Staging Release",
                "description": "End-to-end integration testing, security scans, load benchmarking, and production cutover.",
                "is_cross_cutting": True,
                "features": [],
            },
        }

        all_tasks: List[Dict[str, Any]] = []
        task_counter = 1
        feature_index = 1

        # Classify and map features into appropriate modules
        for feat in features:
            f_name = feat.get("name") or feat.get("feature_name") or f"Feature {feature_index}"
            f_cat = feat.get("category", "CRUD/data module")
            f_comp = feat.get("complexity", overall_complexity)
            f_effort = float(feat.get("expected_effort_hours", feat.get("estimated_effort_hours", 24.0)))
            f_opt = float(feat.get("optimistic_effort_hours", round(f_effort * 0.75, 1)))
            f_pess = float(feat.get("pessimistic_effort_hours", round(f_effort * 1.45, 1)))
            f_deps = feat.get("dependencies", [])

            # Route to appropriate module
            cat_lower = f_cat.lower()
            name_lower = f_name.lower()
            if any(k in name_lower or k in cat_lower for k in ["auth", "login", "role", "permission", "rbac"]):
                target_mod_id = "MOD-02"
            elif any(k in name_lower or k in cat_lower for k in ["payment", "gateway", "api", "integration", "sms", "webhook", "email"]):
                target_mod_id = "MOD-04"
            elif any(k in name_lower or k in cat_lower for k in ["admin", "dashboard", "analytics", "report", "audit"]):
                target_mod_id = "MOD-05"
            elif any(k in name_lower or k in cat_lower for k in ["infra", "devops", "setup", "foundation", "scaffolding"]):
                target_mod_id = "MOD-01"
            elif any(k in name_lower or k in cat_lower for k in ["qa", "test", "hardening", "benchmark"]):
                target_mod_id = "MOD-06"
            else:
                target_mod_id = "MOD-03"

            # Decompose feature into 3 concrete technical tasks:
            # 1. Architecture / Data Model & Contract
            # 2. Implementation / UI & Core Business Logic
            # 3. Automated Tests & Integration Verification
            t1_hours = round(f_effort * 0.25, 1)
            t2_hours = round(f_effort * 0.55, 1)
            t3_hours = round(f_effort - t1_hours - t2_hours, 1)

            t1_id = f"WBS-{target_mod_id[-2:]}.{feature_index}.1"
            t2_id = f"WBS-{target_mod_id[-2:]}.{feature_index}.2"
            t3_id = f"WBS-{target_mod_id[-2:]}.{feature_index}.3"

            t1_role = "Backend Developer" if "UI" not in f_cat else "UI/UX Designer"
            t2_role = self.ROLE_CAPABILITY_MAP.get(f_cat, "Full-Stack Developer")
            t3_role = "QA Engineer"

            task1 = {
                "task_id": t1_id,
                "module_id": target_mod_id,
                "feature_name": f_name,
                "task_name": f"{f_name} — Data Contracts & Schema Definition",
                "description": f"Design database migrations, API schemas, and validation contracts for {f_name}.",
                "acceptance_criteria": [
                    f"Schema and foreign-key constraints for {f_name} verified without circular locks.",
                    f"OpenAPI/REST contracts drafted and validated with type-safe schema.",
                ],
                "required_role": t1_role,
                "effort_hours": {
                    "optimistic": round(t1_hours * 0.8, 1),
                    "likely": t1_hours,
                    "pessimistic": round(t1_hours * 1.3, 1),
                },
                "dependencies": f_deps,
                "is_parallelizable": True,
                "complexity": "Low" if f_comp == "Low" else "Medium",
                "risk_level": "Low",
                "is_shared_component": target_mod_id == "MOD-01",
            }

            task2 = {
                "task_id": t2_id,
                "module_id": target_mod_id,
                "feature_name": f_name,
                "task_name": f"{f_name} — Core Implementation & Interface",
                "description": f"Implement user interaction, state orchestration, and backend endpoints for {f_name}.",
                "acceptance_criteria": [
                    f"Primary workflow for {f_name} executed end-to-end with valid payloads.",
                    f"Error handling and boundary validation returns defensive HTTP status codes.",
                    f"Responsive component rendered cleanly on {platform}.",
                ],
                "required_role": t2_role,
                "effort_hours": {
                    "optimistic": round(t2_hours * 0.8, 1),
                    "likely": t2_hours,
                    "pessimistic": round(t2_hours * 1.4, 1),
                },
                "dependencies": [t1_id],
                "is_parallelizable": False,
                "complexity": f_comp,
                "risk_level": "Medium" if f_comp in ["Medium", "High"] else "Low",
                "is_shared_component": False,
            }

            task3 = {
                "task_id": t3_id,
                "module_id": target_mod_id,
                "feature_name": f_name,
                "task_name": f"{f_name} — Unit, Integration & Regression Tests",
                "description": f"Automated test coverage, positive/negative assertions, and edge-case validation for {f_name}.",
                "acceptance_criteria": [
                    f"Unit and integration test suites for {f_name} pass in CI pipeline with >= 80% coverage.",
                    f"Regression assertions verify no unintended mutations on adjacent components.",
                ],
                "required_role": t3_role,
                "effort_hours": {
                    "optimistic": round(t3_hours * 0.8, 1),
                    "likely": t3_hours,
                    "pessimistic": round(t3_hours * 1.3, 1),
                },
                "dependencies": [t2_id],
                "is_parallelizable": False,
                "complexity": "Low",
                "risk_level": "Low",
                "is_shared_component": False,
            }

            feature_node = {
                "feature_index": feature_index,
                "feature_name": f_name,
                "category": f_cat,
                "complexity": f_comp,
                "total_effort_hours": f_effort,
                "effort_range": f"{f_opt} - {f_pess} hrs",
                "tasks": [task1, task2, task3],
            }

            modules_map[target_mod_id]["features"].append(feature_node)
            all_tasks.extend([task1, task2, task3])
            feature_index += 1

        # Prune empty modules and compute module rollups
        active_modules = []
        total_wbs_hours = 0.0
        role_hours_rollup: Dict[str, float] = {}

        for mod_id, mod_data in modules_map.items():
            if not mod_data["features"]:
                continue
            mod_effort = sum(f["total_effort_hours"] for f in mod_data["features"])
            mod_tasks_count = sum(len(f["tasks"]) for f in mod_data["features"])
            mod_data["total_module_hours"] = round(mod_effort, 1)
            mod_data["task_count"] = mod_tasks_count
            active_modules.append(mod_data)
            total_wbs_hours += mod_effort

        for t in all_tasks:
            r = t["required_role"]
            role_hours_rollup[r] = round(role_hours_rollup.get(r, 0.0) + t["effort_hours"]["likely"], 1)

        parallelizable_count = sum(1 for t in all_tasks if t["is_parallelizable"])
        sequential_count = len(all_tasks) - parallelizable_count

        return {
            "project_name": project_name,
            "project_type": project_type,
            "platform": platform,
            "wbs_version": "2.0.0",
            "total_modules_count": len(active_modules),
            "total_features_count": len(features),
            "total_tasks_count": len(all_tasks),
            "total_effort_hours": round(total_wbs_hours, 1),
            "parallelizable_tasks_count": parallelizable_count,
            "sequential_tasks_count": sequential_count,
            "parallelization_ratio_pct": round((parallelizable_count / max(1, len(all_tasks))) * 100.0, 1),
            "role_effort_distribution": role_hours_rollup,
            "modules": active_modules,
            "flat_tasks": all_tasks,
            "deduplication_policy": "Cross-cutting foundation and CI/CD tasks centralized in MOD-01 to avoid duplicate accounting.",
        }


wbs_generator = WBSGenerator()
