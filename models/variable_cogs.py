# =============================================================================
# RESEMIS EPM ENGINE - VARIABLE COGS MODULE
# =============================================================================
# Calculates variable COGS from input consumption and prices.
#
# FORMULAS:
# Variable_COGS_input[t,p,i] = Consumption_kg[t,p,i] * Input_price[t,i]
# Variable_COGS_product[t,p] = SUM_i(Variable_COGS_input[t,p,i])
# Total_Variable_COGS[t] = SUM_p(Variable_COGS_product[t,p])
# =============================================================================

from typing import Dict, Tuple, List
from collections import defaultdict


def calculate_variable_cogs_detailed(
    consumption: Dict[Tuple[str, str, str], float],
    input_prices: Dict[Tuple[str, str], float]
) -> Dict[Tuple[str, str, str], float]:
    """
    Calculate variable COGS at input level.

    Args:
        consumption: Input consumption by (month, product, input_id) in kg
        input_prices: Input prices by (month, input_id) in EUR/kg

    Returns:
        Variable COGS by (month, product, input_id) in EUR

    Formula:
        Variable_COGS_input[t,p,i] = Consumption_kg[t,p,i] * Input_price[t,i]
    """
    result: Dict[Tuple[str, str, str], float] = {}

    for (month, product, input_id), kg in consumption.items():
        price = input_prices.get((month, input_id), 0.0)
        cogs = kg * price
        result[(month, product, input_id)] = cogs

    return result


def aggregate_variable_cogs_by_product(
    variable_cogs_detailed: Dict[Tuple[str, str, str], float]
) -> Dict[Tuple[str, str], float]:
    """
    Aggregate variable COGS by product and month.

    Args:
        variable_cogs_detailed: Variable COGS by (month, product, input_id)

    Returns:
        Variable COGS by (month, product)
        Dict[(month, product), EUR]

    Formula:
        Variable_COGS_product[t,p] = SUM_i(Variable_COGS_input[t,p,i])
    """
    result: Dict[Tuple[str, str], float] = defaultdict(float)

    for (month, product, input_id), cogs in variable_cogs_detailed.items():
        result[(month, product)] += cogs

    return dict(result)


def aggregate_variable_cogs_total(
    variable_cogs_by_product: Dict[Tuple[str, str], float]
) -> Dict[str, float]:
    """
    Aggregate total variable COGS by month.

    Args:
        variable_cogs_by_product: Variable COGS by (month, product)

    Returns:
        Total variable COGS by month
        Dict[month, EUR]

    Formula:
        Total_Variable_COGS[t] = SUM_p(Variable_COGS_product[t,p])
    """
    result: Dict[str, float] = defaultdict(float)

    for (month, product), cogs in variable_cogs_by_product.items():
        result[month] += cogs

    return dict(result)


def calculate_unit_variable_cogs(
    variable_cogs_total: Dict[str, float],
    units_kg_total: Dict[str, float]
) -> Dict[str, float]:
    """
    Calculate variable COGS per kg (unit variable COGS).

    Args:
        variable_cogs_total: Total variable COGS by month
        units_kg_total: Total production volume by month

    Returns:
        Unit variable COGS by month (EUR/kg)
        Dict[month, EUR/kg]

    Formula:
        Unit_Variable_COGS[t] = Total_Variable_COGS[t] / Units_kg_total[t]

    Notes:
        - Returns 0 if volume is 0 (avoid division by zero)
    """
    result: Dict[str, float] = {}

    for month, total_cogs in variable_cogs_total.items():
        total_kg = units_kg_total.get(month, 0.0)
        if total_kg > 0:
            result[month] = total_cogs / total_kg
        else:
            result[month] = 0.0

    return result


def validate_variable_cogs(
    variable_cogs_detailed: Dict[Tuple[str, str, str], float],
    consumption: Dict[Tuple[str, str, str], float],
    input_prices: Dict[Tuple[str, str], float]
) -> List[str]:
    """
    Validate variable COGS calculations.

    Args:
        variable_cogs_detailed: Calculated variable COGS
        consumption: Input consumption
        input_prices: Input prices

    Returns:
        List of validation errors

    Validations:
        - All COGS >= 0
        - COGS = consumption * price (within tolerance)
    """
    errors = []
    tolerance = 0.01  # EUR

    for key, cogs in variable_cogs_detailed.items():
        if cogs < 0:
            errors.append(f"Negative variable COGS at {key}: {cogs}")

        month, product, input_id = key
        cons = consumption.get(key, 0.0)
        price = input_prices.get((month, input_id), 0.0)
        expected = cons * price

        if abs(cogs - expected) > tolerance:
            errors.append(
                f"COGS mismatch at {key}: {cogs} != {cons} * {price} = {expected}"
            )

    return errors


# =============================================================================
# END OF VARIABLE COGS MODULE
# =============================================================================
