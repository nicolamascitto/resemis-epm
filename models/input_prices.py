# =============================================================================
# RESEMIS EPM ENGINE - INPUT PRICES MODULE
# =============================================================================
# Calculates net input prices for BOM inputs with time-varying prices.
#
# FORMULA:
# Net_input_price[t,i] = Base_price[i] * Price_adjustment[t,i]
# =============================================================================

from typing import Dict, Tuple, List


def get_input_price_for_month(
    month: str,
    input_id: str,
    input_prices_config: Dict
) -> float:
    """
    Get input price for a specific month, using step function.

    Args:
        month: Target month "YYYY-MM"
        input_id: Input ID
        input_prices_config: Input prices structure from assumptions

    Returns:
        Price for the input in EUR/kg

    Logic:
        - If exact month exists in by_month, use it
        - Otherwise, use most recent price <= month
        - If no prices before month, use base_price
    """
    by_input = input_prices_config.get("by_input", {})
    input_data = by_input.get(input_id, {})

    base_price = input_data.get("base_price", 0.0)
    by_month = input_data.get("by_month", {})

    if not by_month:
        return base_price

    if month in by_month:
        return by_month[month]

    # Find most recent price before this month
    applicable_price = base_price
    for price_month, price in sorted(by_month.items()):
        if price_month <= month:
            applicable_price = price
        else:
            break

    return applicable_price


def calculate_all_input_prices(
    months: List[str],
    input_ids: List[str],
    input_prices_config: Dict
) -> Dict[Tuple[str, str], float]:
    """
    Calculate input prices for all month/input combinations.

    Args:
        months: List of months ["YYYY-MM", ...]
        input_ids: List of input IDs
        input_prices_config: Input prices structure from assumptions

    Returns:
        Input prices indexed by (month, input_id)
        Dict[(month, input_id), EUR/kg]
    """
    result: Dict[Tuple[str, str], float] = {}

    for month in months:
        for input_id in input_ids:
            price = get_input_price_for_month(month, input_id, input_prices_config)
            result[(month, input_id)] = price

    return result


def validate_input_prices(input_prices_config: Dict) -> List[str]:
    """
    Validate input prices assumptions.

    Args:
        input_prices_config: Input prices structure

    Returns:
        List of validation errors (empty if valid)

    Validations:
        - All base prices >= 0
        - All monthly prices >= 0
    """
    errors = []

    by_input = input_prices_config.get("by_input", {})
    for input_id, input_data in by_input.items():
        base_price = input_data.get("base_price", 0)
        if base_price < 0:
            errors.append(f"Negative base price for input {input_id}: {base_price}")

        by_month = input_data.get("by_month", {})
        for month, price in by_month.items():
            if price < 0:
                errors.append(
                    f"Negative price for input {input_id} at {month}: {price}"
                )

    return errors


# =============================================================================
# END OF INPUT PRICES MODULE
# =============================================================================
