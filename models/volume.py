# =============================================================================
# RESEMIS EPM ENGINE - VOLUME MODULE
# =============================================================================
# Calculates addressable demand, potential demand, and applies capacity
# constraints. All volumes in kg (physical units).
#
# FORMULAS:
# - Addressable_kg[t,m] = TAM_kg[m] * SAM_pct[m] * SOM_pct[t,m]
# - Potential_kg[t] = SUM_m(Addressable_kg[t,m])
# - Sellable_kg[t] = MIN(Potential_kg[t], Capacity_kg[t])
# =============================================================================

from typing import Dict, Tuple, Optional
from collections import defaultdict


def calculate_som_with_ramp(
    month: str,
    market: str,
    steady_state_som: float,
    activation_month: str,
    ramp_duration_months: int,
    ramp_curve: str = "linear"
) -> float:
    """
    Calculate SOM percentage for a given month, applying ramp from activation.

    Args:
        month: Target month in format "YYYY-MM"
        market: Market identifier
        steady_state_som: Final SOM percentage when ramp completes [0, 1]
        activation_month: Month when market becomes active
        ramp_duration_months: Number of months to reach steady state
        ramp_curve: Type of ramp ("linear" or "s-curve")

    Returns:
        SOM percentage for the given month [0, 1]

    Formula:
        If month < activation_month: SOM = 0
        If month >= activation_month + ramp_duration: SOM = steady_state_som
        Otherwise (linear): SOM = steady_state_som * (months_elapsed / ramp_duration)
    """
    # Convert month strings to comparable integers (YYYYMM)
    def month_to_int(m: str) -> int:
        return int(m.replace("-", ""))

    month_int = month_to_int(month)
    activation_int = month_to_int(activation_month)

    # Before activation: SOM = 0
    if month_int < activation_int:
        return 0.0

    # Calculate months elapsed since activation
    year = int(month[:4])
    mon = int(month[5:7])
    act_year = int(activation_month[:4])
    act_mon = int(activation_month[5:7])

    months_elapsed = (year - act_year) * 12 + (mon - act_mon)

    # After ramp complete: steady state
    if months_elapsed >= ramp_duration_months:
        return steady_state_som

    # During ramp
    if ramp_curve == "linear":
        return steady_state_som * (months_elapsed / ramp_duration_months)
    elif ramp_curve == "s-curve":
        # S-curve: slower start/end, faster middle
        import math
        x = months_elapsed / ramp_duration_months
        k = 10  # Steepness factor
        s_factor = 1 / (1 + math.exp(-k * (x - 0.5)))
        return steady_state_som * s_factor
    else:
        # Default to linear if unknown curve
        return steady_state_som * (months_elapsed / ramp_duration_months)


def calculate_addressable_kg(
    tam_kg: Dict[str, float],
    sam_pct: Dict[str, float],
    som_pct: Dict[Tuple[str, str], float],
) -> Dict[Tuple[str, str], float]:
    """
    Calculate addressable kg per market per month.

    Args:
        tam_kg: Total Addressable Market by market in kg
                Dict[market_id, kg]
        sam_pct: Serviceable Addressable Market as percentage of TAM
                 Dict[market_id, pct] where pct in [0, 1]
        som_pct: Serviceable Obtainable Market as percentage of SAM
                 Dict[(month, market_id), pct] where pct in [0, 1]

    Returns:
        Addressable kg per market per month
        Dict[(month, market_id), kg]

    Formula:
        Addressable_kg[t,m] = TAM_kg[m] * SAM_pct[m] * SOM_pct[t,m]

    Notes:
        - TAM is in physical kg, NOT revenue
        - SAM_pct and SOM_pct are in [0, 1]
        - SOM includes market activation (SOM=0 before activation)
    """
    result: Dict[Tuple[str, str], float] = {}

    for (month, market), som in som_pct.items():
        tam = tam_kg.get(market, 0.0)
        sam = sam_pct.get(market, 0.0)

        addressable = tam * sam * som
        result[(month, market)] = addressable

    return result


def calculate_potential_kg(
    addressable_kg: Dict[Tuple[str, str], float]
) -> Dict[str, float]:
    """
    Sum addressable kg across all markets for each month.

    Args:
        addressable_kg: Addressable kg by month and market
                        Dict[(month, market_id), kg]

    Returns:
        Total potential kg per month
        Dict[month, kg]

    Formula:
        Potential_kg[t] = SUM_m(Addressable_kg[t,m])

    Notes:
        - Aggregates all markets into single monthly total
        - This is pre-capacity constraint
    """
    result: Dict[str, float] = defaultdict(float)

    for (month, market), kg in addressable_kg.items():
        result[month] += kg

    return dict(result)


def apply_capacity_constraint(
    potential_kg: Dict[str, float],
    capacity_kg: Optional[Dict[str, float]]
) -> Dict[str, float]:
    """
    Apply capacity constraint if defined.

    Args:
        potential_kg: Total potential demand per month
                      Dict[month, kg]
        capacity_kg: Maximum production capacity per month (optional)
                     Dict[month, kg] or None if no constraint

    Returns:
        Sellable kg per month (constrained)
        Dict[month, kg]

    Formula:
        If capacity defined: Sellable_kg[t] = MIN(Potential_kg[t], Capacity_kg[t])
        If no capacity: Sellable_kg[t] = Potential_kg[t]

    Notes:
        - Capacity is a SOFT constraint (not blocking, just limiting)
        - Returns copy of potential_kg if capacity is None or empty
        - Months without capacity defined are unconstrained
    """
    if capacity_kg is None or len(capacity_kg) == 0:
        return dict(potential_kg)

    result: Dict[str, float] = {}

    for month, potential in potential_kg.items():
        capacity = capacity_kg.get(month)
        if capacity is not None:
            result[month] = min(potential, capacity)
        else:
            result[month] = potential

    return result


def allocate_to_markets(
    sellable_kg: Dict[str, float],
    addressable_kg: Dict[Tuple[str, str], float]
) -> Dict[Tuple[str, str], float]:
    """
    Allocate sellable kg back to markets proportionally.

    Args:
        sellable_kg: Total sellable kg per month (post-constraint)
                     Dict[month, kg]
        addressable_kg: Addressable kg by month and market
                        Dict[(month, market_id), kg]

    Returns:
        Allocated kg per month and market
        Dict[(month, market_id), kg]

    Formula:
        weight[t,m] = Addressable_kg[t,m] / SUM_m(Addressable_kg[t,m])
        Allocated_kg[t,m] = Sellable_kg[t] * weight[t,m]

    Notes:
        - Used when capacity constraint reduces total volume
        - Maintains proportional allocation across markets
        - If potential_kg for a month is 0, all allocations are 0
    """
    # Calculate potential (sum of addressable) for each month
    potential_by_month: Dict[str, float] = defaultdict(float)
    for (month, market), kg in addressable_kg.items():
        potential_by_month[month] += kg

    result: Dict[Tuple[str, str], float] = {}

    for (month, market), addressable in addressable_kg.items():
        potential = potential_by_month[month]
        sellable = sellable_kg.get(month, 0.0)

        if potential > 0:
            weight = addressable / potential
            result[(month, market)] = sellable * weight
        else:
            result[(month, market)] = 0.0

    return result


# =============================================================================
# END OF VOLUME MODULE
# =============================================================================
