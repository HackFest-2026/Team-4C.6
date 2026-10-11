import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Header, Body, status

from app.core.config import settings
from app.core.security import get_current_user_optional
from app.schemas.estimation import (
    EstimateRequest,
    ScopeAnalyzeRequest,
    BatchFeatureEffortRequest,
    RecalculateRequest,
    CompareRequest,
    ProjectSaveRequest,
    TechStackRecommendRequest,
    RoleRecommendRequest,
    InfraRecommendRequest,
    ProjectReconciliationRequest,
    CurrencyConvertRequest,
)
from app.services.estimation.engine import estimation_engine
from app.services.estimation.feature_effort import feature_effort_engine
from app.services.estimation.currency_converter import currency_converter, CurrencyConversionError
from app.services.ai.requirement_extractor import requirement_extractor
from app.services.ai.tech_stack_recommender import tech_stack_recommender
from app.services.ai.role_recommender import role_recommender
from app.services.ai.infra_recommender import infra_recommender
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
    desc = (req.description or "").strip()
    name = (req.project_name or "").strip()
    if len(desc) < 5 and len(name) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Project description or project name must be provided (at least 5 characters for description, or a project name).",
        )
    result = requirement_extractor.extract(
        description=desc,
        project_type=req.project_type,
        project_name=name,
        overall_complexity=req.complexity or req.overall_complexity,
        target_platforms=req.target_platforms,
        user_scale=req.user_scale,
        tech_stack=req.tech_stack,
        existing_features=req.existing_features,
        client_region=req.client_region,
        quality_requirement=req.quality_requirement,
        realtime_requirement=req.realtime_requirement,
        security_compliance=req.security_compliance,
        deadline_days=req.deadline_days,
        budget_constraint=req.budget_constraint,
        additional_notes=req.additional_notes,
    )
    return result.model_dump()


@router.post("/currency/convert", tags=["Configuration"])
def convert_currency_endpoint(req: CurrencyConvertRequest):
    try:
        if req.budget:
            return currency_converter.convert_budget_components(
                budget=req.budget,
                target_currency=req.target_currency,
                custom_rate=req.custom_rate,
            )
        else:
            amt = req.amount_inr if req.amount_inr is not None else (req.amount if req.amount is not None else 0.0)
            return currency_converter.convert_amount(
                amount_inr=amt,
                target_currency=req.target_currency,
                custom_rate=req.custom_rate,
            )
    except CurrencyConversionError as cce:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(cce))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


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
            "target_platforms": overrides.get("target_platforms", base.get("target_platforms")),
            "team_size": overrides.get("team_size", base.get("inputs_echo", {}).get("team_size", 4)),
            "deadline_days": overrides.get("deadline_days", base.get("inputs_echo", {}).get("deadline_days")),
            "working_hours_per_day": overrides.get("working_hours_per_day", base.get("inputs_echo", {}).get("working_hours_per_day", 8.0)),
            "working_days_per_week": overrides.get("working_days_per_week", base.get("inputs_echo", {}).get("working_days_per_week", 5)),
            "currency": overrides.get("currency", base.get("inputs_echo", {}).get("currency", "INR")),
            "currency_exchange_rate": overrides.get("currency_exchange_rate", base.get("inputs_echo", {}).get("currency_exchange_rate")),
            "rate_profile": overrides.get("rate_profile", base.get("inputs_echo", {}).get("rate_profile", "Professional")),
            "custom_rates": overrides.get("custom_rates", base.get("custom_rates", {})),
            "custom_role_allocations": overrides.get("custom_role_allocations", base.get("custom_role_allocations")),
            "role_headcounts": overrides.get("role_headcounts", base.get("inputs_echo", {}).get("role_headcounts")),
            "contingency_pct": overrides.get("contingency_pct", base.get("inputs_echo", {}).get("contingency_pct", 0.15)),
            "one_time_infra_inr": overrides.get("one_time_infra_inr", base.get("budget", {}).get("one_time_infrastructure_setup_inr", 25000.0)),
            "tooling_setup_inr": overrides.get("tooling_setup_inr", base.get("budget", {}).get("software_tooling_setup_inr", 15000.0)),
            "other_direct_costs_inr": overrides.get("other_direct_costs_inr", base.get("budget", {}).get("other_direct_costs_inr", 0.0)),
            "infrastructure_items": overrides.get("infrastructure_items", base.get("infrastructure_items")),
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

        rate = float(recalculated.get("budget", {}).get("exchange_rate", 1.0))
        curr = recalculated.get("budget", {}).get("currency", "INR")
        delta_budget_conv = round((new_budget - old_budget) / rate, 2)

        return {
            "recalculated_estimate": recalculated,
            "deltas": {
                "delta_budget_inr": round(new_budget - old_budget, 2),
                "delta_budget_converted": delta_budget_conv,
                "currency": curr,
                "exchange_rate": rate,
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
    user_id = current_user["id"] if current_user else None

    est = req.estimate
    budget = est.get("budget", {})
    effort = est.get("effort", {})
    timeline = est.get("timeline", {})
    risk = est.get("risk", {})
    confidence = est.get("confidence", {})

    currency_code = req.currency_code or (req.currency if req.currency and req.currency != "INR" else None) or est.get("currency") or req.currency or "INR"
    exchange_rate = float(budget.get("exchange_rate", 1.0))
    final_budget_converted = budget.get("final_build_budget_converted", budget.get("final_build_budget_inr", 0.0))
    working_hours_per_day = est.get("working_hours_per_day", 8.0)
    working_days_per_week = est.get("working_days_per_week", 5)

    canonical_currency = "INR"
    canonical_amount_inr = float(budget.get("final_build_budget_inr", budget.get("canonical_amount_inr", 0.0)))
    exchange_rate_source = str(budget.get("exchange_rate_source", "CostPilot Treasury Configured Benchmark"))
    exchange_rate_timestamp = str(budget.get("exchange_rate_timestamp", "2026-10-10T12:00:00Z"))

    cursor.execute(
        """
        INSERT INTO projects (
            id, name, description, project_type, overall_complexity, platform,
            team_size, requested_deadline_days, rate_profile, contingency_pct,
            raw_features_json, user_id, currency_code, working_hours_per_day, working_days_per_week,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            currency_code,
            working_hours_per_day,
            working_days_per_week,
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
            risk_level, confidence_score, confidence_level, full_estimate_json,
            currency_code, exchange_rate, final_budget_converted, working_hours_per_day, working_days_per_week,
            canonical_currency, canonical_amount_inr, exchange_rate_source, exchange_rate_timestamp,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            currency_code,
            exchange_rate,
            final_budget_converted,
            working_hours_per_day,
            working_days_per_week,
            canonical_currency,
            canonical_amount_inr,
            exchange_rate_source,
            exchange_rate_timestamp,
            now,
        ),
    )

    conn.commit()
    conn.close()

    return {"id": proj_id, "project_id": proj_id, "estimate_id": est_id, "status": "saved", "created_at": now}


@router.get("/projects", tags=["Projects"])
def list_projects(authorization: Optional[str] = Header(None)):
    current_user = get_current_user_optional(authorization)
    conn = get_db_connection()
    cursor = conn.cursor()

    if current_user:
        # Strict user isolation: only load projects belonging to the active user
        cursor.execute("""
            SELECT p.*, e.final_budget_inr, e.final_budget_converted, e.currency_code as est_currency, e.total_effort_hours, e.likely_calendar_days, e.risk_level
            FROM projects p
            LEFT JOIN estimates e ON p.id = e.project_id
            WHERE p.user_id = ?
            ORDER BY p.created_at DESC
        """, (current_user["id"],))
    else:
        cursor.execute("""
            SELECT p.*, e.final_budget_inr, e.final_budget_converted, e.currency_code as est_currency, e.total_effort_hours, e.likely_calendar_days, e.risk_level
            FROM projects p
            LEFT JOIN estimates e ON p.id = e.project_id
            WHERE p.user_id IS NULL
            ORDER BY p.created_at DESC
        """)

    rows = cursor.fetchall()
    projects = []
    for r in rows:
        cur = r["currency_code"] or r["est_currency"] or "INR"
        cur_info = settings.SUPPORTED_CURRENCIES.get(cur.upper(), settings.SUPPORTED_CURRENCIES["INR"])
        projects.append({
            "id": r["id"],
            "name": r["name"],
            "project_type": r["project_type"],
            "complexity": r["overall_complexity"],
            "platform": r["platform"],
            "team_size": r["team_size"],
            "currency": cur,
            "currency_symbol": cur_info.get("symbol", "₹"),
            "final_budget_inr": r["final_budget_inr"],
            "final_budget_converted": r["final_budget_converted"] if r["final_budget_converted"] is not None else r["final_budget_inr"],
            "total_effort_hours": r["total_effort_hours"],
            "likely_calendar_days": r["likely_calendar_days"],
            "risk_level": r["risk_level"],
            "created_at": r["created_at"],
        })
    conn.close()
    return {"count": len(projects), "projects": projects}


@router.get("/projects/{project_id}", tags=["Projects"])
def get_project(project_id: str, authorization: Optional[str] = Header(None)):
    current_user = get_current_user_optional(authorization)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    p_row = cursor.fetchone()
    if not p_row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Strict authorization check: prevent cross-account project snooping
    if p_row["user_id"]:
        if not current_user:
            conn.close()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required to view this project.")
        if p_row["user_id"] != current_user["id"]:
            conn.close()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to access this project.")

    cursor.execute("SELECT * FROM estimates WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,))
    e_row = cursor.fetchone()
    conn.close()

    full_estimate = json.loads(e_row["full_estimate_json"]) if e_row else None
    cur_code = p_row["currency_code"] or "INR"
    conv_budget = p_row["final_budget_converted"] if "final_budget_converted" in p_row.keys() and p_row["final_budget_converted"] is not None else (e_row["final_budget_converted"] if e_row and "final_budget_converted" in e_row.keys() else (e_row["final_budget_inr"] if e_row else 0.0))
    can_amt = e_row["canonical_amount_inr"] if e_row and "canonical_amount_inr" in e_row.keys() and e_row["canonical_amount_inr"] is not None else (e_row["final_budget_inr"] if e_row else 0.0)
    rate = e_row["exchange_rate"] if e_row and "exchange_rate" in e_row.keys() and e_row["exchange_rate"] is not None else 1.0
    rate_source = e_row["exchange_rate_source"] if e_row and "exchange_rate_source" in e_row.keys() and e_row["exchange_rate_source"] is not None else "CostPilot Treasury Configured Benchmark"
    rate_ts = e_row["exchange_rate_timestamp"] if e_row and "exchange_rate_timestamp" in e_row.keys() and e_row["exchange_rate_timestamp"] is not None else "2026-10-10T12:00:00Z"

    return {
        "id": p_row["id"],
        "name": p_row["name"],
        "description": p_row["description"],
        "project_type": p_row["project_type"],
        "currency": cur_code,
        "currency_code": cur_code,
        "canonical_currency": "INR",
        "canonical_amount_inr": can_amt,
        "final_budget_inr": can_amt,
        "exchange_rate": rate,
        "exchange_rate_source": rate_source,
        "exchange_rate_timestamp": rate_ts,
        "final_budget_converted": conv_budget,
        "created_at": p_row["created_at"],
        "estimate": full_estimate,
    }


@router.post("/projects/{project_id}/recalculate", tags=["Projects"])
def recalculate_saved_project(
    project_id: str,
    overrides: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(None),
):
    current_user = get_current_user_optional(authorization)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    p_row = cursor.fetchone()
    if not p_row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if p_row["user_id"]:
        if not current_user:
            conn.close()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
        if p_row["user_id"] != current_user["id"]:
            conn.close()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access.")

    cursor.execute("SELECT * FROM estimates WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,))
    e_row = cursor.fetchone()
    if not e_row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No estimate found for project.")

    base_estimate = json.loads(e_row["full_estimate_json"])

    target_platforms = overrides.get("target_platforms") or [p_row["platform"]]
    merged_input = {
        "name": overrides.get("name", p_row["name"]),
        "project_type": overrides.get("project_type", p_row["project_type"]),
        "overall_complexity": overrides.get("overall_complexity", p_row["overall_complexity"]),
        "hosting_platform": overrides.get("hosting_platform", p_row["platform"]),
        "target_platforms": target_platforms,
        "team_size": overrides.get("team_size", p_row["team_size"]),
        "deadline_days": overrides.get("deadline_days", p_row["requested_deadline_days"]),
        "working_hours_per_day": overrides.get("working_hours_per_day", p_row["working_hours_per_day"] or 8.0),
        "working_days_per_week": overrides.get("working_days_per_week", p_row["working_days_per_week"] or 5),
        "currency": overrides.get("currency", p_row["currency_code"] or "INR"),
        "currency_exchange_rate": overrides.get("currency_exchange_rate"),
        "rate_profile": overrides.get("rate_profile", p_row["rate_profile"]),
        "custom_rates": overrides.get("custom_rates", base_estimate.get("custom_rates", {})),
        "custom_role_allocations": overrides.get("custom_role_allocations", base_estimate.get("custom_role_allocations")),
        "role_headcounts": overrides.get("role_headcounts", base_estimate.get("inputs_echo", {}).get("role_headcounts")),
        "contingency_pct": overrides.get("contingency_pct", p_row["contingency_pct"] or 0.15),
        "infrastructure_items": overrides.get("infrastructure_items", base_estimate.get("infrastructure_items")),
        "features": overrides.get("features", json.loads(p_row["raw_features_json"] or "[]")),
    }

    recalculated = estimation_engine.estimate_project(merged_input)
    conn.close()

    return {
        "status": "recalculated",
        "project_id": project_id,
        "scenario": recalculated.get("budget", {}),
        "recalculated_estimate": recalculated,
    }


@router.get("/projects/{project_id}/reconciliation", tags=["Projects"])
def get_project_reconciliation(project_id: str, authorization: Optional[str] = Header(None)):
    current_user = get_current_user_optional(authorization)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    p_row = cursor.fetchone()
    if not p_row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if p_row["user_id"]:
        if not current_user:
            conn.close()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
        if p_row["user_id"] != current_user["id"]:
            conn.close()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access.")

    # Get latest estimate
    cursor.execute("SELECT * FROM estimates WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,))
    e_row = cursor.fetchone()
    if not e_row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No estimate found for project.")

    est_budget = e_row["final_budget_converted"] if e_row["final_budget_converted"] is not None else e_row["final_budget_inr"]
    est_effort = e_row["total_effort_hours"]
    est_duration = e_row["likely_calendar_days"]
    currency_code = e_row["currency_code"] or p_row["currency_code"] or "INR"

    cursor.execute("SELECT * FROM project_reconciliations WHERE project_id = ?", (project_id,))
    r_row = cursor.fetchone()
    conn.close()

    if not r_row:
        return {
            "project_id": project_id,
            "project_name": p_row["name"],
            "has_reconciliation": False,
            "has_actual_outcome": False,
            "currency_code": currency_code,
            "estimated": {
                "budget": round(est_budget, 2),
                "effort_hours": round(est_effort, 1),
                "duration_days": est_duration,
            },
            "status": "No verified actual outcomes recorded yet for this project.",
        }

    actual_cost = r_row["actual_cost"]
    actual_effort = r_row["actual_effort_hours"]
    actual_duration = r_row["actual_duration_days"]

    cost_var = round(est_budget - actual_cost, 2)
    cost_var_pct = round(((est_budget - actual_cost) / actual_cost * 100.0), 1) if actual_cost > 0 else 0.0

    effort_var = round(est_effort - actual_effort, 1)
    effort_var_pct = round(((est_effort - actual_effort) / actual_effort * 100.0), 1) if actual_effort > 0 else 0.0

    duration_var = round(est_duration - actual_duration, 1)
    duration_var_pct = round(((est_duration - actual_duration) / actual_duration * 100.0), 1) if actual_duration > 0 else 0.0

    return {
        "project_id": project_id,
        "project_name": p_row["name"],
        "has_reconciliation": True,
        "has_actual_outcome": True,
        "project_status": r_row["project_status"],
        "currency_code": r_row["currency_code"] or currency_code,
        "reconciliation_date": r_row["reconciliation_date"],
        "notes": r_row["notes"],
        "data_provenance": r_row["data_provenance"],
        "estimated_cost": round(est_budget, 2),
        "estimated_effort_hours": round(est_effort, 1),
        "estimated_duration_days": est_duration,
        "actual_cost": round(actual_cost, 2),
        "actual_effort_hours": round(actual_effort, 1),
        "actual_duration_days": round(actual_duration, 1),
        "cost_variance": cost_var,
        "cost_variance_pct": cost_var_pct,
        "effort_variance": effort_var,
        "effort_variance_pct": effort_var_pct,
        "duration_variance": duration_var,
        "duration_variance_pct": duration_var_pct,
        "sign_convention": "Positive variance indicates original estimate was higher than actual result (under-budget / under-time). Negative variance indicates cost or schedule overrun.",
        "estimated": {
            "budget": round(est_budget, 2),
            "effort_hours": round(est_effort, 1),
            "duration_days": est_duration,
        },
        "actual": {
            "cost": round(actual_cost, 2),
            "effort_hours": round(actual_effort, 1),
            "duration_days": round(actual_duration, 1),
        },
        "variances": {
            "cost_variance": cost_var,
            "cost_variance_pct": cost_var_pct,
            "effort_variance": effort_var,
            "effort_variance_pct": effort_var_pct,
            "duration_variance": duration_var,
            "duration_variance_pct": duration_var_pct,
            "sign_convention": "Positive variance indicates original estimate was higher than actual result (under-budget / under-time). Negative variance indicates cost or schedule overrun.",
        },
    }


@router.post("/projects/{project_id}/reconciliation", tags=["Projects"])
def record_project_reconciliation(
    project_id: str,
    req: ProjectReconciliationRequest,
    authorization: Optional[str] = Header(None),
):
    current_user = get_current_user_optional(authorization)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    p_row = cursor.fetchone()
    if not p_row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if p_row["user_id"]:
        if not current_user:
            conn.close()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
        if p_row["user_id"] != current_user["id"]:
            conn.close()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access.")

    # Validate non-negative numbers
    if req.actual_cost < 0 or req.actual_effort_hours < 0 or req.actual_duration_days < 0:
        conn.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Actual costs and hours must be non-negative.")

    now = datetime.now(timezone.utc).isoformat()
    rec_id = f"rec_{uuid.uuid4().hex[:12]}"

    cursor.execute("""
    INSERT INTO project_reconciliations (
        id, project_id, user_id, actual_effort_hours, actual_duration_days, actual_cost,
        currency_code, project_status, notes, reconciliation_date, data_provenance,
        created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(project_id) DO UPDATE SET
        actual_effort_hours = excluded.actual_effort_hours,
        actual_duration_days = excluded.actual_duration_days,
        actual_cost = excluded.actual_cost,
        currency_code = excluded.currency_code,
        project_status = excluded.project_status,
        notes = excluded.notes,
        reconciliation_date = excluded.reconciliation_date,
        updated_at = excluded.updated_at
    """, (
        rec_id,
        project_id,
        current_user["id"] if current_user else None,
        req.actual_effort_hours,
        req.actual_duration_days,
        req.actual_cost,
        req.currency_code or p_row["currency_code"] or "INR",
        req.project_status or "Completed",
        req.notes or "",
        now,
        "User-recorded verified outcome",
        now,
        now,
    ))
    conn.commit()
    conn.close()

    return get_project_reconciliation(project_id=project_id, authorization=authorization)


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

    # Strict authorization check: only owner can delete project
    if p_row["user_id"]:
        if not current_user:
            conn.close()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required to delete this project.")
        if p_row["user_id"] != current_user["id"]:
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


@router.post("/recommend/tech-stack", tags=["AI Recommendations"])
def recommend_tech_stack(req: TechStackRecommendRequest):
    traffic = req.expected_traffic or req.user_scale or "1k-10k"
    complexity = req.complexity or req.overall_complexity or "Medium"
    rec = tech_stack_recommender.recommend(
        project_name=req.project_name or "",
        project_type=req.project_type,
        description=req.description or "",
        overall_complexity=complexity,
        target_platforms=req.target_platforms,
        user_scale=traffic,
        client_region=req.client_region or "India",
    )
    rec_specs = rec.get("recommended_specifications", {})
    rationales = rec.get("rationales", {})
    
    flat_recommendations = {
        "frontend": rec_specs.get("frontend_stack", ["React"])[0] if isinstance(rec_specs.get("frontend_stack"), list) else rec_specs.get("frontend_stack", "React"),
        "backend": rec_specs.get("backend_stack", ["Node.js_Express"])[0] if isinstance(rec_specs.get("backend_stack"), list) else rec_specs.get("backend_stack", "Node.js_Express"),
        "database": rec_specs.get("database", ["PostgreSQL"])[0] if isinstance(rec_specs.get("database"), list) else rec_specs.get("database", "PostgreSQL"),
        "cloud_platform": rec_specs.get("hosting_platform", ["AWS"])[0] if isinstance(rec_specs.get("hosting_platform"), list) else rec_specs.get("hosting_platform", "AWS"),
        "payment": rec_specs.get("payment_integration", "Stripe"),
        "authentication": rec_specs.get("auth_requirements", ["JWT_Sessions"])[0] if isinstance(rec_specs.get("auth_requirements"), list) else rec_specs.get("auth_requirements", "JWT_Sessions"),
        "security": rec_specs.get("security_compliance", "Standard"),
        "realtime": rec_specs.get("realtime_features", "None"),
        "testing_qa": rec_specs.get("quality_testing", "Standard"),
        "integrations": rec_specs.get("external_integrations", []),
    }
    
    return {
        "status": "success",
        "project_name": req.project_name or rec.get("project_name", ""),
        "project_type": req.project_type,
        "overall_complexity": complexity,
        "recommendations": flat_recommendations,
        "recommended_specifications": rec_specs,
        "rationale": rationales,
        "rationales": rationales,
        "is_ai_generated": rec.get("is_ai_generated", False),
        "provider_used": rec.get("provider_used", "Domain Architecture Engine (Rule-based offline)"),
        "provider": rec.get("provider_used", "Domain Architecture Engine (Rule-based offline)"),
    }


@router.post("/recommend/roles", tags=["AI Recommendations"])
def recommend_roles(req: RoleRecommendRequest):
    features_list = [f.model_dump() for f in req.features]
    complexity = req.complexity or req.overall_complexity or "Medium"
    return role_recommender.recommend(
        features=features_list,
        project_type=req.project_type or "SaaS Platform",
        overall_complexity=complexity,
        target_platforms=req.target_platforms,
        rate_profile=req.rate_profile or "Professional",
        currency=req.currency or "INR",
    )


@router.post("/recommend/infrastructure", tags=["AI Recommendations"])
def recommend_infrastructure(req: InfraRecommendRequest):
    features_list = [f.model_dump() for f in req.features] if req.features else []
    complexity = req.complexity or req.overall_complexity or "Medium"
    traffic = req.expected_traffic or req.user_scale or "1k-10k"
    hosting = req.hosting_cloud or req.cloud_platform or []
    def _to_list(v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return [str(v)]

    return infra_recommender.recommend(
        project_name=req.project_name or "",
        project_type=req.project_type or "SaaS Platform",
        overall_complexity=complexity,
        target_platforms=_to_list(req.target_platforms),
        frontend_stack=_to_list(req.frontend_stack),
        backend_stack=_to_list(req.backend_stack),
        database=_to_list(req.database),
        hosting_cloud=_to_list(hosting),
        user_scale=traffic,
        features_count=req.features_count or (len(features_list) if features_list else 4),
        integrations_count=req.integrations_count or 1,
        currency=req.currency or "INR",
    )


@router.get("/currencies", tags=["Configuration"])
def list_currencies():
    return {
        "base_currency": settings.DEFAULT_CURRENCY,
        "default_currency": settings.DEFAULT_CURRENCY,
        "currencies": settings.SUPPORTED_CURRENCIES,
        "supported_currencies": settings.SUPPORTED_CURRENCIES,
        "exchange_rates_timestamp": "2026-10-10T12:00:00Z",
        "provenance": "Configured institutional baseline exchange rates",
    }


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


