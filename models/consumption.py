# =============================================================================
# RESEMIS EPM ENGINE - CONSUMPTION MODULE
# =============================================================================
# Calculates input consumption based on BOM and production volume.
#
# FORMULA:
# Input_consumption_kg[t,p,i] = Units_kg[t,p] * BOM_qty_per_kg[p,i]
# =============================================================================

from typing import Dict, Tuple, List
from .bom import ProductBOM


def calculate_input_consumption(
    units_kg: Dict[Tuple[str, str, str], float],
    bom: Dict[str, ProductBOM]
) -> Dict[Tuple[str, str, str], float]:
    """
    Calculate input consumption based on BOM and production volume.

    Args:
        units_kg: Production volume by (month, product, market)
                  Dict[(month, product, market), kg]
        bom: BOM definitions by product
             Dict[product_id, ProductBOM]

    Returns:
        Input consumption by (month, product, input)
        Dict[(month, product, input_id), kg]

    Formula:
        Input_consumption_kg[t,p,i] = Units_kg[t,p] * BOM_qty_per_kg[p,i]

    Notes:
        - Aggregates units across markets for each product/month
        - BOM is per kg of output, so consumption = volume * BOM qty
    """
    # First aggregate units by product/month (sum across markets)
    units_by_product_month: Dict[Tuple[str, str], float] = {}
    for (month, product, market), kg in units_kg.items():
        key = (month, product)
        units_by_product_month[key] = units_by_product_month.get(key, 0.0) + kg

    # Calculate consumption
    result: Dict[Tuple[str, str, str], float] = {}

    for (month, product), output_kg in units_by_product_month.items():
        product_bom = bom.get(product)
        if product_bom is None:
            continue

        for bom_input in product_bom.inputs:
            consumption = output_kg * bom_input.qty_per_kg
            result[(month, product, bom_input.input_id)] = consumption

    return result


def aggregate_consumption_by_input(
    consumption: Dict[Tuple[str, str, str], float]
) -> Dict[Tuple[str, str], float]:
    """
    Aggregate consumption by input and month (across products).

    Args:
        consumption: Input consumption by (month, product, input_id)

    Returns:
        Total consumption by (month, input_id)
        Dict[(month, input_id), kg]
    """
    result: Dict[Tuple[str, str], float] = {}

    for (month, product, input_id), kg in consumption.items():
        key = (month, input_id)
        result[key] = result.get(key, 0.0) + kg

    return result


def aggregate_consumption_by_product(
    consumption: Dict[Tuple[str, str, str], float]
) -> Dict[Tuple[str, str], float]:
    """
    Aggregate total consumption by product and month (across inputs).

    Args:
        consumption: Input consumption by (month, product, input_id)

    Returns:
        Total input kg consumed by (month, product)
        Dict[(month, product), kg]
    """
    result: Dict[Tuple[str, str], float] = {}

    for (month, product, input_id), kg in consumption.items():
        key = (month, product)
        result[key] = result.get(key, 0.0) + kg

    return result


def validate_consumption(
    consumption: Dict[Tuple[str, str, str], float],
    units_kg: Dict[Tuple[str, str, str], float],
    bom: Dict[str, ProductBOM]
) -> List[str]:
    """
    Validate consumption calculations.

    Args:
        consumption: Calculated consumption
        units_kg: Production volume
        bom: BOM definitions

    Returns:
        List of validation errors

    Validations:
        - All consumption >= 0
        - Consumption consistent with BOM and volume
    """
    errors = []

    # Check non-negative
    for key, kg in consumption.items():
        if kg < 0:
            errors.append(f"Negative consumption at {key}: {kg}")

    # Check consistency with BOM
    # Aggregate units by product/month
    units_by_pm: Dict[Tuple[str, str], float] = {}
    for (month, product, market), kg in units_kg.items():
        key = (month, product)
        units_by_pm[key] = units_by_pm.get(key, 0.0) + kg

    for (month, product, input_id), calc_consumption in consumption.items():
        output_kg = units_by_pm.get((month, product), 0.0)
        product_bom = bom.get(product)
        if product_bom is None:
            continue

        try:
            bom_input = product_bom.get_input(input_id)
            expected = output_kg * bom_input.qty_per_kg
            if abs(calc_consumption - expected) > 0.01:
                errors.append(
                    f"Consumption mismatch at {(month, product, input_id)}: "
                    f"{calc_consumption} != {expected}"
                )
        except KeyError:
            errors.append(f"Input {input_id} not in BOM for {product}")

    return errors


# =============================================================================
# END OF CONSUMPTION MODULE
# =============================================================================
