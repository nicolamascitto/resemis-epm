# =============================================================================
# RESEMIS EPM ENGINE - FIXED COGS MODULE
# =============================================================================
# Calculates fixed COGS with ramp factors.
#
# FORMULAS:
# Fixed_COGS[t] = Fixed_COGS_base * Ramp[t]
# Fixed_COGS_allocated[t,p] = Fixed_COGS[t] * (Units_kg[t,p] / Units_kg_total[t])
# =============================================================================

from typing import Dict, Tuple, List
from collections import defaultdict


def get_ramp_for_month(
    month: str,
    ramp_by_month: Dict[str, float]
) -> float:
    """
    Get ramp factor for a specific month using step function.

    Args:
        month: Target month "YYYY-MM"
        ramp_by_month: Ramp factors by month

    Returns:
        Ramp factor (defaults to 1.0 if not defined)

    Logic:
        - If exact month found, use it
        - Otherwise use most recent ramp <= month
        - Default to 1.0 if no ramp defined
    """
    if not ramp_by_month:
        return 1.0

    if month in ramp_by_month:
        return ramp_by_month[month]

    # Find most recent ramp
    applicable_ramp = 1.0
    for ramp_month, ramp in sorted(ramp_by_month.items()):
        if ramp_month <= month:
            applicable_ramp = ramp
        else:
            break

    return applicable_ramp


def calculate_fixed_cogs(
    months: List[str],
    base_monthly: float,
    ramp_by_month: Dict[str, float]
) -> Dict[str, float]:
    """
    Calculate fixed COGS by month.

    Args:
        months: List of months
        base_monthly: Base fixed COGS per month (EUR)
        ramp_by_month: Ramp factors by month

    Returns:
        Fixed COGS by month (EUR)
        Dict[month, EUR]

    Formula:
        Fixed_COGS[t] = base_monthly * ramp[t]
    """
    result: Dict[str, float] = {}

    for month in months:
        ramp = get_ramp_for_month(month, ramp_by_month)
        result[month] = base_monthly * ramp

    return result


def allocate_fixed_cogs(
    fixed_cogs: Dict[str, float],
    units_kg_by_product: Dict[Tuple[str, str], float]
) -> Dict[Tuple[str, str], float]:
    """
    Allocate fixed COGS to products proportionally (for reporting only).

    Args:
        fixed_cogs: Total fixed COGS by month
        units_kg_by_product: Volume by (month, product)

    Returns:
        Fixed COGS allocated by (month, product)
        Dict[(month, product), EUR]

    Formula:
        Fixed_COGS_allocated[t,p] = Fixed_COGS[t] * (Units_kg[t,p] / Units_kg_total[t])

    Notes:
        - This is for reporting purposes only, not for decision-making
        - If total volume is 0, allocate 0 to all products
    """
    # Calculate total volume by month
    volume_by_month: Dict[str, float] = defaultdict(float)
    for (month, product), kg in units_kg_by_product.items():
        volume_by_month[month] += kg

    result: Dict[Tuple[str, str], float] = {}

    for (month, product), kg in units_kg_by_product.items():
        total_kg = volume_by_month[month]
        total_fixed = fixed_cogs.get(month, 0.0)

        if total_kg > 0:
            allocation = total_fixed * (kg / total_kg)
        else:
            allocation = 0.0

        result[(month, product)] = allocation

    return result


def validate_fixed_cogs(
    fixed_cogs: Dict[str, float],
    base_monthly: float,
    ramp_by_month: Dict[str, float]
) -> List[str]:
    """
    Validate fixed COGS calculations.

    Args:
        fixed_cogs: Calculated fixed COGS
        base_monthly: Base amount
        ramp_by_month: Ramp factors

    Returns:
        List of validation errors

    Validations:
        - All fixed COGS >= 0
        - Ramp factors > 0
    """
    errors = []

    # Check base is non-negative
    if base_monthly < 0:
        errors.append(f"Negative base_monthly: {base_monthly}")

    # Check ramp factors are positive
    for month, ramp in ramp_by_month.items():
        if ramp < 0:
            errors.append(f"Negative ramp factor at {month}: {ramp}")

    # Check calculated COGS are non-negative
    for month, cogs in fixed_cogs.items():
        if cogs < 0:
            errors.append(f"Negative fixed COGS at {month}: {cogs}")

    return errors


# =============================================================================
# END OF FIXED COGS MODULE
# =============================================================================
