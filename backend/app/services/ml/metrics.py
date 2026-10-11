"""
CostPilot AI — Statistical Evaluation Metrics for Software Effort, Cost & Duration Estimation.
Implements mathematically rigorous MMRE, MdMRE, and PRED(25) calculations with robust exclusion handling.
"""

from typing import Dict, Any, List, Optional, Tuple, Sequence
import numpy as np


def calculate_relative_error_metrics(
    actual_values: Sequence[Any],
    predicted_values: Sequence[Any],
) -> Dict[str, Any]:
    """
    Computes MMRE, MdMRE, and PRED(25) according to standard software engineering cost estimation metrics.
    
    Mathematical definitions:
      MRE_i = |A_i - P_i| / |A_i|
      MMRE = (1 / n) * sum(MRE_i) * 100%
      MdMRE = median(MRE_1, ..., MRE_n) * 100%
      PRED(25) = (#{i : MRE_i <= 0.25} / n) * 100%
      
    Exclusion rules:
      - Excludes missing (None), non-finite (NaN, Inf, -Inf), or non-positive (<= 0) actual values.
      - Excludes non-finite or missing predicted values.
      - Returns counts of eligible observations and exclusions with documented reasons.
      - Safely handles empty evaluation datasets (returns None / 0.0 with eligible_count = 0).
    """
    if actual_values is None or predicted_values is None:
        return {
            "mmre": 0.0,
            "mdmre": 0.0,
            "pred25": 0.0,
            "eligible_count": 0,
            "excluded_count": 0,
            "exclusion_reasons": ["Null or missing dataset passed"],
            "mre_values": [],
        }

    n_act = len(actual_values)
    n_pred = len(predicted_values)
    min_len = min(n_act, n_pred)

    eligible_mres: List[float] = []
    exclusion_reasons: List[str] = []
    excluded_count = abs(n_act - n_pred)
    if excluded_count > 0:
        exclusion_reasons.append(f"Mismatched input lengths: {n_act} actual vs {n_pred} predicted records.")

    for i in range(min_len):
        a_raw = actual_values[i]
        p_raw = predicted_values[i]

        # Check for None or missing
        if a_raw is None:
            excluded_count += 1
            exclusion_reasons.append(f"Record {i}: Actual value is null/missing.")
            continue
        if p_raw is None:
            excluded_count += 1
            exclusion_reasons.append(f"Record {i}: Predicted value is null/missing.")
            continue

        # Parse numeric values safely
        try:
            a_val = float(a_raw)
            p_val = float(p_raw)
        except (ValueError, TypeError):
            excluded_count += 1
            exclusion_reasons.append(f"Record {i}: Non-numeric value (actual={a_raw}, predicted={p_raw}).")
            continue

        # Check finiteness
        if not np.isfinite(a_val):
            excluded_count += 1
            exclusion_reasons.append(f"Record {i}: Actual value is non-finite (NaN or Inf).")
            continue
        if not np.isfinite(p_val):
            excluded_count += 1
            exclusion_reasons.append(f"Record {i}: Predicted value is non-finite (NaN or Inf).")
            continue

        # Check non-positive denominator (MRE requires non-zero positive actual target)
        if a_val <= 0.0:
            excluded_count += 1
            exclusion_reasons.append(f"Record {i}: Actual target is non-positive ({a_val} <= 0).")
            continue

        # Compute MRE
        mre_i = abs(a_val - p_val) / a_val
        eligible_mres.append(mre_i)

    eligible_count = len(eligible_mres)

    if eligible_count == 0:
        return {
            "mmre": 0.0,
            "mdmre": 0.0,
            "pred25": 0.0,
            "eligible_count": 0,
            "excluded_count": excluded_count,
            "exclusion_reasons": exclusion_reasons,
            "mre_values": [],
            "status": "No eligible observations for relative error computation",
        }

    mre_arr = np.array(eligible_mres, dtype=float)

    # Calculate metrics as percentages (0% - 100% scale)
    mmre = round(float(np.mean(mre_arr) * 100.0), 2)
    mdmre = round(float(np.median(mre_arr) * 100.0), 2)
    pred25 = round(float(np.mean(mre_arr <= 0.25) * 100.0), 2)

    return {
        "mmre": mmre,
        "mdmre": mdmre,
        "pred25": pred25,
        "eligible_count": eligible_count,
        "excluded_count": excluded_count,
        "exclusion_reasons": exclusion_reasons,
        "mre_values": [round(float(m), 4) for m in eligible_mres],
        "status": "valid",
    }


def calculate_individual_accuracy(
    actual: Optional[float],
    predicted: Optional[float],
) -> Optional[Dict[str, Any]]:
    """
    Computes individual estimate accuracy when verified actual outcome is available.
    Returns None if actual is unrecorded or non-positive.
    """
    if actual is None or predicted is None:
        return None
    try:
        a_val = float(actual)
        p_val = float(predicted)
    except (ValueError, TypeError):
        return None

    if not np.isfinite(a_val) or not np.isfinite(p_val) or a_val <= 0:
        return None

    abs_error = round(abs(a_val - p_val), 2)
    rel_error_pct = round((abs_error / a_val) * 100.0, 2)
    within_pred25 = (abs_error / a_val) <= 0.25

    return {
        "actual": a_val,
        "predicted": p_val,
        "absolute_error": abs_error,
        "relative_error_pct": rel_error_pct,
        "mre_pct": rel_error_pct,
        "within_pred25": within_pred25,
        "is_within_pred25": within_pred25,
        "is_eligible": True,
        "error_direction": "Overestimated" if p_val > a_val else ("Underestimated" if p_val < a_val else "Exact"),
    }
