from typing import Dict, Any, List, Optional, Tuple
from app.core.config import settings
from app.services.estimation.currency_converter import currency_converter


class FinancialInvariantViolation(Exception):
    """Raised when ReportedBuildLabourCost != Sum(RoleHours * RoleRate)."""
    pass


class CostBudgetEngine:
    """
    Authoritative Cost Engine guaranteeing financial invariants,
    explicit separation of labour, infrastructure, and single-pass contingency.
    """

    def __init__(self):
        self.rate_profiles = settings.RATE_PROFILES
        self.default_contingency = settings.DEFAULT_CONTINGENCY_PCT

    def get_role_rates(self, profile_name: str = "Professional", custom_rates: Dict[str, float] = None) -> Dict[str, float]:
        base = dict(self.rate_profiles.get(profile_name, self.rate_profiles["Professional"]))
        if custom_rates:
            for role, rate in custom_rates.items():
                if rate > 0:
                    base[role] = float(rate)
        return base

    def calculate_labour_cost(
        self,
        role_allocations: Dict[str, Dict[str, Any]],
        role_rates: Dict[str, float],
        role_headcounts: Optional[Dict[str, int]] = None,
    ) -> Tuple[float, Dict[str, Dict[str, Any]]]:
        """
        Calculates role-by-role cost and enforces the Mandatory Financial Invariant.
        Filters out zero-headcount or unallocated roles.
        """
        role_breakdown = {}
        total_labour = 0.0

        for role, data in role_allocations.items():
            hours = float(data.get("allocated_hours", 0.0))
            # Omit inactive / zero-headcount roles
            if role_headcounts is not None and role_headcounts.get(role, 1) <= 0:
                continue
            if hours <= 0:
                continue

            rate = float(role_rates.get(role, 1200.0))
            cost = round(hours * rate, 2)
            role_breakdown[role] = {
                "allocated_hours": hours,
                "hourly_rate_inr": rate,
                "role_cost_inr": cost,
            }
            total_labour += cost

        total_labour = round(total_labour, 2)

        # Invariant check: ReportedBuildLabourCost == Sum(RoleHours * RoleHourlyRate)
        check_sum = sum(item["role_cost_inr"] for item in role_breakdown.values())
        if abs(total_labour - check_sum) > 0.05:
            raise FinancialInvariantViolation(
                f"Financial Invariant Failed: TotalLabourCost ({total_labour}) != Sum(RoleCost) ({check_sum})"
            )

        return total_labour, role_breakdown

    def calculate_budget(
        self,
        total_effort_hours: float,
        optimistic_hours: float,
        pessimistic_hours: float,
        role_allocations: Dict[str, Dict[str, Any]],
        role_rates: Dict[str, float],
        one_time_infra_inr: float = 25000.0,
        tooling_setup_inr: float = 15000.0,
        other_direct_costs_inr: float = 0.0,
        contingency_rate: float = 0.15,
        currency: str = "INR",
        currency_exchange_rate: Optional[float] = None,
        role_headcounts: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Calculates the complete defensible financial budget and uncertainty bounds.
        Supports multi-currency conversion while preserving INR ground-truth invariants.
        """
        contingency_pct = max(0.0, min(0.50, float(contingency_rate)))

        # 1. Likely Labour Cost (strictly in canonical INR)
        likely_labour, role_breakdown = self.calculate_labour_cost(role_allocations, role_rates, role_headcounts)

        # Blended rate for consistent range scaling
        blended_hourly_rate = likely_labour / max(1.0, total_effort_hours)

        # 2. Additional direct costs
        infra_setup = max(0.0, float(one_time_infra_inr))
        tooling_setup = max(0.0, float(tooling_setup_inr))
        direct_costs = max(0.0, float(other_direct_costs_inr))
        total_additional_costs = round(infra_setup + tooling_setup + direct_costs, 2)

        # 3. Pre-contingency cost
        pre_contingency_likely = round(likely_labour + total_additional_costs, 2)

        # 4. Contingency (Applied EXACTLY ONCE!)
        contingency_amount_likely = round(pre_contingency_likely * contingency_pct, 2)

        # 5. Final likely budget
        final_budget_likely = round(pre_contingency_likely + contingency_amount_likely, 2)

        # 6. Low (Optimistic) and High (Pessimistic) range bounds
        opt_labour = round(optimistic_hours * blended_hourly_rate, 2)
        pess_labour = round(pessimistic_hours * blended_hourly_rate, 2)

        pre_contingency_low = round(opt_labour + total_additional_costs, 2)
        pre_contingency_high = round(pess_labour + total_additional_costs, 2)

        contingency_low = round(pre_contingency_low * (contingency_pct * 0.7), 2)
        contingency_high = round(pre_contingency_high * (contingency_pct * 1.3), 2)

        final_budget_low = round(pre_contingency_low + contingency_low, 2)
        final_budget_high = round(pre_contingency_high + contingency_high, 2)

        # 7. Convert every budget component using centralized authoritative CurrencyConverter
        raw_budget = {
            "final_build_budget_inr": final_budget_likely,
            "labour_cost_inr": likely_labour,
            "one_time_infrastructure_setup_inr": infra_setup,
            "software_tooling_setup_inr": tooling_setup,
            "other_direct_costs_inr": direct_costs,
            "total_additional_costs_inr": total_additional_costs,
            "pre_contingency_cost_inr": pre_contingency_likely,
            "contingency_amount_inr": contingency_amount_likely,
            "contingency_pct": round(contingency_pct * 100.0, 1),
            "budget_range": {
                "low_inr": final_budget_low,
                "likely_inr": final_budget_likely,
                "high_inr": final_budget_high,
            },
            "role_costs": role_breakdown,
        }

        converted = currency_converter.convert_budget_components(
            raw_budget,
            target_currency=currency,
            custom_rate=currency_exchange_rate,
        )

        # Attach auxiliary metrics while preserving all converted and canonical fields
        rate = converted["exchange_rate"]
        converted["canonical_amount_inr"] = final_budget_likely
        converted["blended_hourly_rate_inr"] = round(blended_hourly_rate, 2)
        converted["blended_hourly_rate_converted"] = round(blended_hourly_rate / rate, 2) if rate > 0 else round(blended_hourly_rate, 2)
        converted["effort_range"] = {
            "optimistic_hours": round(optimistic_hours, 1),
            "expected_hours": round(total_effort_hours, 1),
            "pessimistic_hours": round(pessimistic_hours, 1),
        }
        converted["role_costs_list"] = [
            {
                "role": role,
                "allocated_hours": data["allocated_hours"],
                "hourly_rate_inr": data["hourly_rate_inr"],
                "total_cost_inr": data["role_cost_inr"],
                "hourly_rate_converted": data["hourly_rate_converted"],
                "total_cost_converted": data["role_cost_converted"],
                "currency_code": converted["currency_code"],
                "currency_symbol": converted["currency_symbol"],
            }
            for role, data in converted["role_costs"].items()
        ]

        return converted


cost_budget_engine = CostBudgetEngine()
