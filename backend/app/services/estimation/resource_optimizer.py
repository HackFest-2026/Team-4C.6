"""
CostPilot AI — Resource Planning & Staffing Optimization Service.
Evaluates software engineering staffing scenarios under dependency constraints,
role-level rate structures, and Brooks' Law coordination overhead.

Provides 3 Authoritative Scenarios:
  1. Budget-Focused: Lean team size, low coordination overhead, cost minimization.
  2. Balanced: Optimal risk-adjusted delivery balancing timeline, throughput, and cost.
  3. Deadline-Focused (Fast-Track): High-concurrency staffing bounded by the critical path,
     modeling Brooks' Law communication penalties and providing feasibility analysis.
"""

import math
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.services.estimation.cost_budget import cost_budget_engine
from app.services.estimation.currency_converter import currency_converter


class ResourceOptimizer:
    """
    Computes comparative multi-scenario resource optimization plans.
    Guarantees that shortening deadlines models communication overhead
    and does not magically reduce the intrinsic amount of engineering effort.
    """

    def __init__(self):
        self.rate_profiles = settings.RATE_PROFILES
        self.availability_factor = settings.DEFAULT_AVAILABILITY_FACTOR
        self.productive_hours_per_day = settings.PRODUCTIVE_HOURS_PER_DAY

    def optimize_scenarios(
        self,
        total_effort_hours: float,
        critical_path_hours: float,
        project_type: str,
        rate_profile: str = "Professional",
        custom_rates: Optional[Dict[str, float]] = None,
        requested_deadline_days: Optional[int] = None,
        one_time_infra_inr: float = 25000.0,
        tooling_setup_inr: float = 15000.0,
        other_direct_costs_inr: float = 0.0,
        contingency_rate: float = 0.15,
        currency: str = "INR",
        currency_exchange_rate: Optional[float] = None,
        working_hours_per_day: float = 8.0,
        working_days_per_week: int = 5,
    ) -> Dict[str, Any]:
        """
        Calculates and contrasts Budget-Focused, Balanced, and Deadline-Focused scenarios.
        """
        work_hours = max(4.0, min(16.0, float(working_hours_per_day)))
        work_days = max(1, min(7, int(working_days_per_week)))
        daily_person_productive_hours = work_hours * self.availability_factor
        work_to_cal_ratio = 7.0 / work_days

        # Hard physical floor: Critical path cannot be divided across people
        crit_work_days = critical_path_hours / max(1.0, daily_person_productive_hours)
        crit_calendar_days = math.ceil(crit_work_days * work_to_cal_ratio)
        hard_floor_calendar_days = crit_calendar_days + 7  # setup/release buffer

        rates = cost_budget_engine.get_role_rates(rate_profile, custom_rates)

        # -------------------------------------------------------------
        # SCENARIO 1: BUDGET-FOCUSED (Lean Staffing, 2 Developers)
        # -------------------------------------------------------------
        budget_team_size = 2
        budget_coord_factor = 1.0 + (0.05 * (budget_team_size - 1))  # +5%
        budget_effective_effort = round(total_effort_hours * budget_coord_factor, 1)
        budget_daily_team_hours = budget_team_size * daily_person_productive_hours
        budget_effort_cal_days = math.ceil((budget_effective_effort / budget_daily_team_hours) * work_to_cal_ratio)
        budget_calendar_days = max(hard_floor_calendar_days, budget_effort_cal_days + 7)

        budget_headcounts = {
            "Full-Stack Developer": 1,
            "Backend Developer": 1,
            "QA Engineer": 0,
            "UI/UX Designer": 0,
            "DevOps Engineer": 0,
            "Project Manager": 0,
            "Solution Architect": 0,
        }
        # Redistribute effort: 50% Full-Stack, 50% Backend
        budget_allocations = {
            "Full-Stack Developer": {"allocated_hours": round(total_effort_hours * 0.50, 1)},
            "Backend Developer": {"allocated_hours": round(total_effort_hours * 0.50, 1)},
        }
        budget_calc = cost_budget_engine.calculate_budget(
            total_effort_hours=total_effort_hours,
            optimistic_hours=round(total_effort_hours * 0.8, 1),
            pessimistic_hours=round(total_effort_hours * 1.3, 1),
            role_allocations=budget_allocations,
            role_rates=rates,
            one_time_infra_inr=one_time_infra_inr * 0.85,
            tooling_setup_inr=tooling_setup_inr * 0.80,
            other_direct_costs_inr=other_direct_costs_inr,
            contingency_rate=contingency_rate,
            currency=currency,
            currency_exchange_rate=currency_exchange_rate,
            role_headcounts=budget_headcounts,
        )

        scenario_budget = {
            "scenario_key": "budget_focused",
            "name": "Budget-Focused (Lean Team)",
            "team_size": budget_team_size,
            "calendar_days": budget_calendar_days,
            "effective_effort_hours": budget_effective_effort,
            "coordination_overhead_pct": round((budget_coord_factor - 1.0) * 100, 1),
            "final_budget": budget_calc["final_budget"],
            "total_labour_cost": budget_calc["total_labour_cost"],
            "currency_code": budget_calc["currency_code"],
            "currency_symbol": budget_calc["currency_symbol"],
            "headcounts": budget_headcounts,
            "feasibility_status": "Comfortable (Extended Duration)",
            "feasibility_analysis": f"Minimizes labor burn by utilizing a tight 2-person squad. Extends delivery to {budget_calendar_days} days to absorb workload without overtime premium.",
            "strategic_rationale": "Recommended when cash preservation takes precedence over rapid market entry.",
        }

        # -------------------------------------------------------------
        # SCENARIO 2: BALANCED (Standard Recommended, 4-5 Specialists)
        # -------------------------------------------------------------
        balanced_team_size = 4
        balanced_coord_factor = 1.0 + (0.05 * (balanced_team_size - 1))  # +15%
        balanced_effective_effort = round(total_effort_hours * balanced_coord_factor, 1)
        balanced_daily_team_hours = balanced_team_size * daily_person_productive_hours
        balanced_effort_cal_days = math.ceil((balanced_effective_effort / balanced_daily_team_hours) * work_to_cal_ratio)
        balanced_calendar_days = max(hard_floor_calendar_days, math.ceil((balanced_effort_cal_days + 7) * 1.15))

        balanced_headcounts = {
            "Frontend Developer": 1,
            "Backend Developer": 1,
            "QA Engineer": 1,
            "Project Manager": 1,
            "UI/UX Designer": 1,
            "DevOps Engineer": 1,
        }
        balanced_allocations = {
            "Frontend Developer": {"allocated_hours": round(total_effort_hours * 0.35, 1)},
            "Backend Developer": {"allocated_hours": round(total_effort_hours * 0.40, 1)},
            "QA Engineer": {"allocated_hours": round(total_effort_hours * 0.15, 1)},
            "Project Manager": {"allocated_hours": round(total_effort_hours * 0.10, 1)},
        }
        balanced_calc = cost_budget_engine.calculate_budget(
            total_effort_hours=total_effort_hours,
            optimistic_hours=round(total_effort_hours * 0.8, 1),
            pessimistic_hours=round(total_effort_hours * 1.3, 1),
            role_allocations=balanced_allocations,
            role_rates=rates,
            one_time_infra_inr=one_time_infra_inr,
            tooling_setup_inr=tooling_setup_inr,
            other_direct_costs_inr=other_direct_costs_inr,
            contingency_rate=contingency_rate,
            currency=currency,
            currency_exchange_rate=currency_exchange_rate,
            role_headcounts=balanced_headcounts,
        )

        scenario_balanced = {
            "scenario_key": "balanced",
            "name": "Balanced (Risk-Adjusted Benchmark)",
            "team_size": balanced_team_size,
            "calendar_days": balanced_calendar_days,
            "effective_effort_hours": balanced_effective_effort,
            "coordination_overhead_pct": round((balanced_coord_factor - 1.0) * 100, 1),
            "final_budget": balanced_calc["final_budget"],
            "total_labour_cost": balanced_calc["total_labour_cost"],
            "currency_code": balanced_calc["currency_code"],
            "currency_symbol": balanced_calc["currency_symbol"],
            "headcounts": balanced_headcounts,
            "feasibility_status": "Balanced & Defensible",
            "feasibility_analysis": f"Maintains dedicated engineering, testing, and management. Achieves optimal schedule throughput in {balanced_calendar_days} calendar days.",
            "strategic_rationale": "Recommended institutional baseline balancing speed, code maintainability, and expenditure.",
        }

        # -------------------------------------------------------------
        # SCENARIO 3: DEADLINE-FOCUSED (Fast-Track, 7-8 Engineers)
        # -------------------------------------------------------------
        deadline_team_size = 7
        deadline_coord_factor = 1.0 + (0.05 * (deadline_team_size - 1))  # +30% overhead (Brooks' Law)
        deadline_effective_effort = round(total_effort_hours * deadline_coord_factor, 1)
        deadline_daily_team_hours = deadline_team_size * daily_person_productive_hours
        deadline_effort_cal_days = math.ceil((deadline_effective_effort / deadline_daily_team_hours) * work_to_cal_ratio)
        deadline_calendar_days = max(hard_floor_calendar_days, deadline_effort_cal_days + 7)

        deadline_headcounts = {
            "Frontend Developer": 2,
            "Backend Developer": 2,
            "QA Engineer": 1,
            "DevOps Engineer": 1,
            "Project Manager": 1,
        }
        deadline_allocations = {
            "Frontend Developer": {"allocated_hours": round(total_effort_hours * 0.35, 1)},
            "Backend Developer": {"allocated_hours": round(total_effort_hours * 0.40, 1)},
            "QA Engineer": {"allocated_hours": round(total_effort_hours * 0.15, 1)},
            "Project Manager": {"allocated_hours": round(total_effort_hours * 0.10, 1)},
        }
        deadline_calc = cost_budget_engine.calculate_budget(
            total_effort_hours=total_effort_hours,
            optimistic_hours=round(total_effort_hours * 0.8, 1),
            pessimistic_hours=round(total_effort_hours * 1.3, 1),
            role_allocations=deadline_allocations,
            role_rates=rates,
            one_time_infra_inr=one_time_infra_inr * 1.25,
            tooling_setup_inr=tooling_setup_inr * 1.25,
            other_direct_costs_inr=other_direct_costs_inr,
            contingency_rate=min(0.30, contingency_rate * 1.25),
            currency=currency,
            currency_exchange_rate=currency_exchange_rate,
            role_headcounts=deadline_headcounts,
        )

        feasibility_status = "Feasible (Fast-Track)"
        feasibility_notes = f"Compresses duration to {deadline_calendar_days} calendar days using high parallelization. Incurs +30% Brooks' Law coordination penalty."

        if requested_deadline_days and requested_deadline_days < hard_floor_calendar_days:
            deficit = hard_floor_calendar_days - requested_deadline_days
            feasibility_status = "Infeasible (Physical Critical-Path Constraint)"
            feasibility_notes = (
                f"Requested deadline of {requested_deadline_days} days is mathematically impossible. "
                f"The unparallelizable critical path sequence requires at least {hard_floor_calendar_days} calendar days. "
                f"Deficit of {deficit} days cannot be solved by adding headcount (Brooks' Law). Scope pruning required."
            )

        scenario_deadline = {
            "scenario_key": "deadline_focused",
            "name": "Deadline-Focused (Fast-Track)",
            "team_size": deadline_team_size,
            "calendar_days": deadline_calendar_days,
            "effective_effort_hours": deadline_effective_effort,
            "coordination_overhead_pct": round((deadline_coord_factor - 1.0) * 100, 1),
            "final_budget": deadline_calc["final_budget"],
            "total_labour_cost": deadline_calc["total_labour_cost"],
            "currency_code": deadline_calc["currency_code"],
            "currency_symbol": deadline_calc["currency_symbol"],
            "headcounts": deadline_headcounts,
            "feasibility_status": feasibility_status,
            "feasibility_analysis": feasibility_notes,
            "strategic_rationale": "Applied when immediate go-to-market or contractual penalty outweighs incremental coordination costs.",
        }

        return {
            "critical_path_calendar_days": crit_calendar_days,
            "physical_floor_calendar_days": hard_floor_calendar_days,
            "requested_deadline_days": requested_deadline_days,
            "scenarios": [scenario_budget, scenario_balanced, scenario_deadline],
            "comparison_summary": {
                "budget_delta_pct": round(
                    ((scenario_deadline["final_budget"] - scenario_budget["final_budget"]) / max(1.0, scenario_budget["final_budget"])) * 100.0, 1
                ),
                "duration_delta_days": scenario_budget["calendar_days"] - scenario_deadline["calendar_days"],
                "brooks_law_penalty_delta_pct": scenario_deadline["coordination_overhead_pct"] - scenario_budget["coordination_overhead_pct"],
            },
        }


resource_optimizer = ResourceOptimizer()
