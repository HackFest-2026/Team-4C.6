import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Header, status

from app.core.config import settings
from app.core.security import get_current_user_optional
from app.schemas.estimation import (
    EstimateRequest,
    ScopeAnalyzeRequest,
    BatchFeatureEffortRequest,
    RecalculateRequest,
    CompareRequest,
    ProjectSaveRequest,
)
from app.services.estimation.engine import estimation_engine
from app.services.estimation.feature_effort import feature_effort_engine
from app.services.ai.requirement_extractor import requirement_extractor
from app.services.ml.model_registry import model_registry
from app.db.session import get_db_connection
from app.api.auth import router as auth_router

router = APIRouter()
router.include_router(auth_router)


@router.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "currency": settings.DEFAULT_CURRENCY,
    }


@router.get("/model/status", tags=["Machine Learning"])
def get_model_status():
    return model_registry.get_status()


@router.get("/model/metrics", tags=["Machine Learning"])
def get_model_metrics():
    metrics_file = Path(settings.REPORTS_DIR) / "model_metrics.json"
    if not metrics_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model metrics report not found. Please run model training first.",
        )
    with open(metrics_file, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post("/scope/analyze", tags=["Scope Analysis"])
def analyze_scope(req: ScopeAnalyzeRequest):
    if not req.description or len(req.description.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Project description must be at least 5 characters.",
        )
    result = requirement_extractor.extract(req.description, req.project_type)
    return result.model_dump()


@router.post("/features/estimate-effort", tags=["Features"])
def estimate_features_effort(req: BatchFeatureEffortRequest):
    features_in = [f.model_dump() for f in req.features]
    return feature_effort_engine.estimate_features_list(features_in)


@router.post("/estimate", tags=["Estimation"])
def create_estimate(req: EstimateRequest):
    try:
        req_dict = req.model_dump()
        estimate = estimation_engine.estimate_project(req_dict)
        return estimate
    except Exception as e:
        logger_msg = f"Estimation error: {str(e)}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/estimate/recalculate", tags=["Estimation"])
def recalculate_estimate(req: RecalculateRequest):
    """
    Reruns the authoritative engine with overridden parameters (What-if scenario).
    Never uses naive percentage addition!
    """
    try:
        base = req.base_estimate
        overrides = req.overrides

        # Merge base input echo and features with overrides
        merged_input = {
            "name": overrides.get("name", base.get("project_name")),
            "project_type": overrides.get("project_type", base.get("project_type")),
            "overall_complexity": overrides.get("overall_complexity", base.get("overall_complexity")),
            "hosting_platform": overrides.get("hosting_platform", base.get("platform", "Web")),
            "team_size": overrides.get("team_size", base.get("inputs_echo", {}).get("team_size", 4)),
            "deadline_days": overrides.get("deadline_days", base.get("inputs_echo", {}).get("deadline_days")),
            "rate_profile": overrides.get("rate_profile", base.get("inputs_echo", {}).get("rate_profile", "Professional")),
            "custom_rates": overrides.get("custom_rates", base.get("custom_rates", {})),
            "custom_role_allocations": overrides.get("custom_role_allocations", base.get("custom_role_allocations")),
            "contingency_pct": overrides.get("contingency_pct", base.get("inputs_echo", {}).get("contingency_pct", 0.15)),
            "one_time_infra_inr": overrides.get("one_time_infra_inr", base.get("budget", {}).get("one_time_infrastructure_setup_inr", 25000.0)),
            "tooling_setup_inr": overrides.get("tooling_setup_inr", base.get("budget", {}).get("software_tooling_setup_inr", 15000.0)),
            "other_direct_costs_inr": overrides.get("other_direct_costs_inr", base.get("budget", {}).get("other_direct_costs_inr", 0.0)),
            "features": overrides.get("features", base.get("features", [])),
        }

        recalculated = estimation_engine.estimate_project(merged_input)

        # Compute exact deltas
        old_budget = base.get("budget", {}).get("final_build_budget_inr", 0.0)
        new_budget = recalculated.get("budget", {}).get("final_build_budget_inr", 0.0)
        old_effort = base.get("effort", {}).get("total_expected_effort_hours", 0.0)
        new_effort = recalculated.get("effort", {}).get("total_expected_effort_hours", 0.0)
        old_days = base.get("timeline", {}).get("likely_calendar_days", 0)
        new_days = recalculated.get("timeline", {}).get("likely_calendar_days", 0)

        return {
            "recalculated_estimate": recalculated,
            "deltas": {
                "delta_budget_inr": round(new_budget - old_budget, 2),
                "delta_budget_pct": round(((new_budget - old_budget) / max(1.0, old_budget)) * 100, 1),
                "delta_effort_hours": round(new_effort - old_effort, 1),
                "delta_likely_calendar_days": new_days - old_days,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/estimate/compare", tags=["Estimation"])
def compare_estimates(req: CompareRequest):
    if len(req.scenarios) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 scenarios are required for comparison.",
        )
    results = []
    for sc in req.scenarios:
        sc_dict = sc.model_dump()
        est = estimation_engine.estimate_project(sc_dict)
        results.append(est)
    return {"scenarios_count": len(results), "comparisons": results}


@router.post("/projects", tags=["Projects"])
def save_project(req: ProjectSaveRequest, authorization: Optional[str] = Header(None)):
    conn = get_db_connection()
    cursor = conn.cursor()
    proj_id = f"proj_{uuid.uuid4().hex[:10]}"
    est_id = f"est_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()

    current_user = get_current_user_optional(authorization)
    user_id = current_user["id"] if current_user else "usr_demo_001"

    est = req.estimate
    budget = est.get("budget", {})
    effort = est.get("effort", {})
    timeline = est.get("timeline", {})
    risk = est.get("risk", {})
    confidence = est.get("confidence", {})

    cursor.execute(
        """
        INSERT INTO projects (
            id, name, description, project_type, overall_complexity, platform,
            team_size, requested_deadline_days, rate_profile, contingency_pct,
            raw_features_json, user_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            proj_id,
            req.project_name,
            req.description,
            est.get("project_type", "SaaS Web Application"),
            est.get("overall_complexity", "Medium"),
            est.get("platform", "Web Application"),
            est.get("inputs_echo", {}).get("team_size", 4),
            est.get("inputs_echo", {}).get("deadline_days"),
            est.get("inputs_echo", {}).get("rate_profile", "Professional"),
            est.get("inputs_echo", {}).get("contingency_pct", 0.15),
            json.dumps(est.get("features", [])),
            user_id,
            now,
            now,
        ),
    )

    cursor.execute(
        """
        INSERT INTO estimates (
            id, project_id, engine_version, total_effort_hours, optimistic_effort_hours,
            pessimistic_effort_hours, final_budget_inr, labour_cost_inr, additional_costs_inr,
            contingency_amount_inr, budget_range_low_inr, budget_range_high_inr, critical_path_hours,
            min_feasible_days, likely_calendar_days, is_timeline_feasible, risk_score,
            risk_level, confidence_score, confidence_level, full_estimate_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            est_id,
            proj_id,
            est.get("engine_version", "2.0.0"),
            effort.get("total_expected_effort_hours", 0.0),
            effort.get("optimistic_effort_hours", 0.0),
            effort.get("pessimistic_effort_hours", 0.0),
            budget.get("final_build_budget_inr", 0.0),
            budget.get("labour_cost_inr", 0.0),
            budget.get("total_additional_costs_inr", 0.0),
            budget.get("contingency_amount_inr", 0.0),
            budget.get("budget_range", {}).get("low_inr", 0.0),
            budget.get("budget_range", {}).get("high_inr", 0.0),
            timeline.get("critical_path_hours", 0.0),
            timeline.get("min_feasible_calendar_days", 0),
            timeline.get("likely_calendar_days", 0),
            1 if timeline.get("is_timeline_feasible") else 0,
            risk.get("risk_score", 0.0),
            risk.get("risk_level", "Medium"),
            confidence.get("confidence_score_pct", 0.0),
            confidence.get("confidence_level", "Medium"),
            json.dumps(est),
            now,
        ),
    )

    conn.commit()
    conn.close()

    return {"project_id": proj_id, "estimate_id": est_id, "status": "saved", "created_at": now}


@router.get("/projects", tags=["Projects"])
def list_projects(authorization: Optional[str] = Header(None)):
    current_user = get_current_user_optional(authorization)
    conn = get_db_connection()
    cursor = conn.cursor()

    if current_user:
        cursor.execute("""
            SELECT p.*, e.final_budget_inr, e.total_effort_hours, e.likely_calendar_days, e.risk_level
            FROM projects p
            LEFT JOIN estimates e ON p.id = e.project_id
            WHERE p.user_id = ? OR p.user_id IS NULL
            ORDER BY p.created_at DESC
        """, (current_user["id"],))
    else:
        cursor.execute("""
            SELECT p.*, e.final_budget_inr, e.total_effort_hours, e.likely_calendar_days, e.risk_level
            FROM projects p
            LEFT JOIN estimates e ON p.id = e.project_id
            ORDER BY p.created_at DESC
        """)

    rows = cursor.fetchall()
    projects = []
    for r in rows:
        projects.append({
            "id": r["id"],
            "name": r["name"],
            "project_type": r["project_type"],
            "complexity": r["overall_complexity"],
            "platform": r["platform"],
            "team_size": r["team_size"],
            "final_budget_inr": r["final_budget_inr"],
            "total_effort_hours": r["total_effort_hours"],
            "likely_calendar_days": r["likely_calendar_days"],
            "risk_level": r["risk_level"],
            "created_at": r["created_at"],
        })
    conn.close()
    return {"count": len(projects), "projects": projects}


@router.get("/projects/{project_id}", tags=["Projects"])
def get_project(project_id: str, authorization: Optional[str] = Header(None)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    p_row = cursor.fetchone()
    if not p_row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    cursor.execute("SELECT * FROM estimates WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,))
    e_row = cursor.fetchone()
    conn.close()

    full_estimate = json.loads(e_row["full_estimate_json"]) if e_row else None
    return {
        "id": p_row["id"],
        "name": p_row["name"],
        "description": p_row["description"],
        "project_type": p_row["project_type"],
        "created_at": p_row["created_at"],
        "estimate": full_estimate,
    }


@router.delete("/projects/{project_id}", tags=["Projects"])
def delete_project(project_id: str, authorization: Optional[str] = Header(None)):
    current_user = get_current_user_optional(authorization)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM projects WHERE id = ?", (project_id,))
    p_row = cursor.fetchone()
    if not p_row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if current_user and p_row["user_id"] and p_row["user_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to delete this project.")

    cursor.execute("DELETE FROM estimates WHERE project_id = ?", (project_id,))
    cursor.execute("DELETE FROM whatif_scenarios WHERE project_id = ?", (project_id,))
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return {"status": "deleted", "project_id": project_id}


@router.get("/analytics", tags=["Analytics"])
def get_analytics(authorization: Optional[str] = Header(None)):
    current_user = get_current_user_optional(authorization)
    conn = get_db_connection()
    cursor = conn.cursor()

    if current_user:
        cursor.execute("""
            SELECT COUNT(*) as cnt, AVG(e.final_budget_inr) as avg_b, AVG(e.total_effort_hours) as avg_e, AVG(e.likely_calendar_days) as avg_d
            FROM estimates e
            JOIN projects p ON e.project_id = p.id
            WHERE p.user_id = ? OR p.user_id IS NULL
        """, (current_user["id"],))
        row = cursor.fetchone()

        cursor.execute("""
            SELECT p.project_type, COUNT(*) as count, AVG(e.final_budget_inr) as avg_budget
            FROM projects p
            JOIN estimates e ON p.id = e.project_id
            WHERE p.user_id = ? OR p.user_id IS NULL
            GROUP BY p.project_type
        """, (current_user["id"],))
        by_type_rows = cursor.fetchall()

        cursor.execute("""
            SELECT p.overall_complexity, COUNT(*) as count, AVG(e.total_effort_hours) as avg_effort
            FROM projects p
            JOIN estimates e ON p.id = e.project_id
            WHERE p.user_id = ? OR p.user_id IS NULL
            GROUP BY p.overall_complexity
        """, (current_user["id"],))
        by_comp_rows = cursor.fetchall()
    else:
        cursor.execute("""
            SELECT COUNT(*) as cnt, AVG(final_budget_inr) as avg_b, AVG(total_effort_hours) as avg_e, AVG(likely_calendar_days) as avg_d
            FROM estimates
        """)
        row = cursor.fetchone()

        cursor.execute("""
            SELECT p.project_type, COUNT(*) as count, AVG(e.final_budget_inr) as avg_budget
            FROM projects p
            JOIN estimates e ON p.id = e.project_id
            GROUP BY p.project_type
        """)
        by_type_rows = cursor.fetchall()

        cursor.execute("""
            SELECT p.overall_complexity, COUNT(*) as count, AVG(e.total_effort_hours) as avg_effort
            FROM projects p
            JOIN estimates e ON p.id = e.project_id
            GROUP BY p.overall_complexity
        """)
        by_comp_rows = cursor.fetchall()

    db_stats = {
        "saved_projects_count": row["cnt"] if row and row["cnt"] else 0,
        "avg_saved_budget_inr": round(row["avg_b"], 2) if row and row["avg_b"] else 0.0,
        "avg_saved_effort_hours": round(row["avg_e"], 1) if row and row["avg_e"] else 0.0,
        "avg_saved_duration_days": round(row["avg_d"], 1) if row and row["avg_d"] else 0.0,
        "budget_by_project_type": [
            {"project_type": r["project_type"], "count": r["count"], "avg_budget_inr": round(r["avg_budget"], 2)}
            for r in by_type_rows
        ],
        "effort_by_complexity": [
            {"complexity": r["overall_complexity"], "count": r["count"], "avg_effort_hours": round(r["avg_effort"], 1)}
            for r in by_comp_rows
        ],
    }
    conn.close()

    # Load dataset summary report
    data_report_path = Path(settings.REPORTS_DIR) / "data_quality_report.json"
    dataset_summary = {}
    if data_report_path.exists():
        with open(data_report_path, "r", encoding="utf-8") as f:
            d = json.load(f)
            dataset_summary = d.get("summary", {})

    return {
        "database_stats": db_stats,
        "dataset_benchmarks": dataset_summary,
        "provenance_note": "Benchmarks derived from simulated CostPilot AI training dataset.",
    }


@router.get("/settings", tags=["Configuration"])
def get_system_settings():
    return {
        "currency": settings.DEFAULT_CURRENCY,
        "rate_profiles": settings.RATE_PROFILES,
        "role_profiles": settings.ROLE_PROFILES_BY_PROJECT_TYPE,
        "platform_multipliers": settings.PLATFORM_MULTIPLIERS,
        "complexity_weights": settings.COMPLEXITY_FACTOR_WEIGHTS,
        "risk_weights": settings.RISK_FACTOR_WEIGHTS,
        "productive_hours_per_day": settings.PRODUCTIVE_HOURS_PER_DAY,
    }
