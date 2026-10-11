import math
from typing import Dict, Any, List, Tuple
from app.core.config import settings


class TeamTimelineEngine:
    """
    Computes role distribution, team staffing FTE, productive capacity,
    critical-path timeline, and schedule feasibility against requested deadlines.
    """

    def __init__(self):
        self.role_profiles = settings.ROLE_PROFILES_BY_PROJECT_TYPE
        self.default_profile = settings.ROLE_PROFILES_BY_PROJECT_TYPE["Default"]
        self.productive_hours_per_day = settings.PRODUCTIVE_HOURS_PER_DAY
        self.availability_factor = settings.DEFAULT_AVAILABILITY_FACTOR

    def get_role_profile(self, project_type: str) -> Dict[str, float]:
        profile = self.role_profiles.get(project_type, self.default_profile)
        # Normalize to ensure exactly 1.00 sum
        total_p = sum(profile.values())
        if abs(total_p - 1.0) > 0.0001 and total_p > 0:
            return {r: round(p / total_p, 4) for r, p in profile.items()}
        return profile

    def calculate_role_allocations(
        self,
        total_effort_hours: float,
        project_type: str,
        custom_profile: Dict[str, float] = None,
        role_headcounts: Dict[str, int] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Allocates total effort hours across specialized roles.
        Guarantees that sum(AllocatedHours) == total_effort_hours.
        Excludes roles with 0 headcount when role_headcounts is provided.
        """
        if custom_profile:
            raw_profile = custom_profile
            tot = sum(raw_profile.values())
            profile = {r: p / tot for r, p in raw_profile.items()} if tot > 0 else self.get_role_profile(project_type)
        else:
            profile = dict(self.get_role_profile(project_type))

        # If role_headcounts is provided, filter out inactive (0 or negative) headcount roles
        if role_headcounts is not None and len(role_headcounts) > 0:
            active_roles = {r for r, count in role_headcounts.items() if count > 0}
            if active_roles:
                filtered_profile = {r: pct for r, pct in profile.items() if r in active_roles}
                for r in active_roles:
                    if r not in filtered_profile:
                        filtered_profile[r] = 1.0 / len(active_roles)
                tot = sum(filtered_profile.values())
                profile = {r: p / tot for r, p in filtered_profile.items()} if tot > 0 else filtered_profile

        allocations = {}
        allocated_sum = 0.0
        sorted_roles = list(profile.keys())
        if not sorted_roles:
            sorted_roles = ["Full-Stack Developer"]
            profile = {"Full-Stack Developer": 1.0}

        for role, pct in profile.items():
            hours = round(total_effort_hours * pct, 1)
            allocations[role] = {
                "percentage": round(pct * 100.0, 1),
                "allocated_hours": hours,
            }
            allocated_sum += hours

        # Invariant fix: reconcile rounding remainder to the primary engineering role
        diff = round(total_effort_hours - allocated_sum, 1)
        if abs(diff) > 0:
            primary_role = "Backend Developer" if "Backend Developer" in allocations else sorted_roles[0]
            allocations[primary_role]["allocated_hours"] = round(allocations[primary_role]["allocated_hours"] + diff, 1)

        return allocations

    def calculate_timeline_and_capacity(
        self,
        total_effort_hours: float,
        critical_path_hours: float,
        team_size: int = 4,
        requested_deadline_days: int = None,
        role_allocations: Dict[str, Dict[str, Any]] = None,
        working_hours_per_day: float = 8.0,
        working_days_per_week: int = 5,
        role_headcounts: Dict[str, int] = None,
    ) -> Dict[str, Any]:
        """
        Calculates feasible calendar days, role FTE, team capacity, and schedule feasibility.
        Explicitly incorporates working hours per day and working days per week into capacity.
        """
        # Determine active team size from role_headcounts if available
        if role_headcounts is not None and len(role_headcounts) > 0:
            active_sum = sum(max(0, int(cnt)) for cnt in role_headcounts.values())
            if active_sum > 0:
                safe_team_size = max(1, min(settings.MAX_TEAM_SIZE, active_sum))
            else:
                safe_team_size = max(1, min(settings.MAX_TEAM_SIZE, int(team_size)))
        else:
            safe_team_size = max(1, min(settings.MAX_TEAM_SIZE, int(team_size)))

        safe_work_hours = max(4.0, min(16.0, float(working_hours_per_day)))
        safe_work_days = max(1, min(7, int(working_days_per_week)))
        availability = float(self.availability_factor)  # e.g. 0.85

        # Coordination overhead penalty (Brooks' Law heuristic: +5% per additional team member beyond 1)
        coordination_factor = 1.0 + (0.05 * (safe_team_size - 1))
        effective_effort = total_effort_hours * coordination_factor

        # Working days to calendar days ratio
        work_to_calendar_ratio = 7.0 / safe_work_days
        daily_person_productive_hours = safe_work_hours * availability
        daily_team_productive_hours = safe_team_size * daily_person_productive_hours
        weekly_capacity_per_person = round(daily_person_productive_hours * safe_work_days, 1)
        weekly_team_capacity = round(daily_team_productive_hours * safe_work_days, 1)

        # 1. Effort-driven duration (calendar days)
        effort_work_days = effective_effort / max(1.0, daily_team_productive_hours)
        effort_calendar_days = math.ceil(effort_work_days * work_to_calendar_ratio)

        # 2. Critical path duration (calendar days): critical path cannot be parallelized
        crit_work_days = critical_path_hours / max(1.0, daily_person_productive_hours)
        crit_calendar_days = math.ceil(crit_work_days * work_to_calendar_ratio)

        # Fixed overhead for setup and deployment buffer (7 calendar days)
        min_feasible_calendar_days = max(crit_calendar_days, effort_calendar_days) + 7
        likely_calendar_days = math.ceil(min_feasible_calendar_days * 1.15)  # 15% schedule variance buffer

        # Role FTE staffing requirements based on feasible duration
        feasible_work_days = max(1.0, (likely_calendar_days - 7) * (safe_work_days / 7.0))
        person_capacity_hours = max(1.0, feasible_work_days * daily_person_productive_hours)

        roles_staffing = {}
        if role_allocations:
            for role, data in role_allocations.items():
                hours = data.get("allocated_hours", 0.0)
                # Omit roles with 0 allocated hours or 0 headcount from active staffing
                if role_headcounts and role_headcounts.get(role, 1) <= 0:
                    continue
                if hours <= 0:
                    continue
                fte = round(hours / person_capacity_hours, 2)
                headcount = role_headcounts.get(role) if role_headcounts and role in role_headcounts else (math.ceil(fte) if fte > 0 else 0)
                roles_staffing[role] = {
                    "allocated_hours": hours,
                    "required_fte": fte,
                    "recommended_headcount": headcount,
                }

        # Check deadline feasibility
        is_feasible = True
        feasibility_status = "Feasible"
        feasibility_warning = None
        schedule_pressure_factor = 1.0

        if requested_deadline_days is not None and requested_deadline_days > 0:
            if requested_deadline_days < min_feasible_calendar_days:
                is_feasible = False
                deficit_days = min_feasible_calendar_days - requested_deadline_days
                feasibility_status = "Infeasible (Deadline Too Aggressive)"
                feasibility_warning = (
                    f"Requested deadline of {requested_deadline_days} days is mathematically infeasible. "
                    f"Minimum feasible duration is {min_feasible_calendar_days} calendar days "
                    f"due to critical-path sequence ({crit_calendar_days} days) and team capacity ({weekly_team_capacity}h/wk). "
                    f"Deficit: {deficit_days} calendar days. Scope reduction or staged delivery is recommended."
                )
                schedule_pressure_factor = min(2.0, min_feasible_calendar_days / requested_deadline_days)
            elif requested_deadline_days < likely_calendar_days:
                feasibility_status = "Tight (High Schedule Pressure)"
                feasibility_warning = (
                    f"Requested deadline of {requested_deadline_days} days is feasible but tight. "
                    f"Minimal buffer for unexpected defects or scope creep."
                )
                schedule_pressure_factor = 1.25
            else:
                feasibility_status = "Comfortable"

        return {
            "team_size": safe_team_size,
            "working_hours_per_day": safe_work_hours,
            "working_days_per_week": safe_work_days,
            "weekly_team_capacity_hours": weekly_team_capacity,
            "daily_team_productive_hours": round(daily_team_productive_hours, 1),
            "weekly_capacity_per_person_hours": weekly_capacity_per_person,
            "min_feasible_calendar_days": min_feasible_calendar_days,
            "likely_calendar_days": likely_calendar_days,
            "effort_calendar_days": effort_calendar_days,
            "critical_path_calendar_days": crit_calendar_days,
            "critical_path_hours": critical_path_hours,
            "coordination_overhead_pct": round((coordination_factor - 1.0) * 100, 1),
            "effective_effort_hours": round(effective_effort, 1),
            "requested_deadline_days": requested_deadline_days,
            "is_timeline_feasible": is_feasible,
            "feasibility_status": feasibility_status,
            "feasibility_warning": feasibility_warning,
            "schedule_pressure_factor": round(schedule_pressure_factor, 2),
            "roles_staffing": roles_staffing,
        }


team_timeline_engine = TeamTimelineEngine()
