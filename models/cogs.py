# =============================================================================
# RESEMIS EPM ENGINE - COGS ENGINE
# =============================================================================
# Main COGS calculation module that orchestrates BOM, consumption, and costs.
#
# KEY PRINCIPLE: BOM-driven COGS (no flat EUR/kg allowed)
#
# EXECUTION ORDER:
# 1. Load BOM definitions
# 2. Calculate input prices for all months
# 3. Calculate input consumption from volume and BOM
# 4. Calculate variable COGS (consumption * price)
# 5. Calculate fixed COGS with ramp
# 6. Aggregate and derive unit costs
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, Tuple, List
from collections import defaultdict

from .bom import load_bom, validate_bom, get_all_input_ids, ProductBOM
from .input_prices import calculate_all_input_prices, validate_input_prices
from .consumption import calculate_input_consumption, aggregate_consumption_by_product
from .variable_cogs import (
    calculate_variable_cogs_detailed,
    aggregate_variable_cogs_by_product,
    aggregate_variable_cogs_total,
    calculate_unit_variable_cogs
)
from .fixed_cogs import calculate_fixed_cogs, allocate_fixed_cogs
from .revenue import generate_months


@dataclass
class COGSOutput:
    """Output structure for COGS engine."""

    # Detailed outputs
    consumption: Dict[Tuple[str, str, str], float] = field(default_factory=dict)
    variable_cogs_detailed: Dict[Tuple[str, str, str], float] = field(default_factory=dict)

    # Product-level aggregations
    variable_cogs_product: Dict[Tuple[str, str], float] = field(default_factory=dict)
    fixed_cogs_allocated: Dict[Tuple[str, str], float] = field(default_factory=dict)

    # Monthly totals
    variable_cogs_total: Dict[str, float] = field(default_factory=dict)
    fixed_cogs: Dict[str, float] = field(default_factory=dict)
    total_cogs: Dict[str, float] = field(default_factory=dict)

    # Unit costs (derived)
    unit_variable_cogs: Dict[str, float] = field(default_factory=dict)
    unit_fixed_cogs: Dict[str, float] = field(default_factory=dict)
    unit_total_cogs: Dict[str, float] = field(default_factory=dict)

    # Validation
    errors: List[str] = field(default_factory=list)


def cogs_engine(
    assumptions: Dict,
    units_kg: Dict[Tuple[str, str, str], float]
) -> COGSOutput:
    """
    Main COGS engine.

    Args:
        assumptions: Full assumptions dictionary loaded from YAML
        units_kg: Production volume from revenue engine
                  Dict[(month, product, market), kg]

    Returns:
        COGSOutput with all calculated values

    Execution order:
        1. Load and validate BOM
        2. Calculate input prices
        3. Calculate consumption
        4. Calculate variable COGS
        5. Calculate fixed COGS
        6. Aggregate and derive unit costs
    """
    output = COGSOutput()

    # Extract config sections
    time_horizon = assumptions.get("time_horizon", {})
    start_month = time_horizon.get("start_month", "2026-01")
    end_month = time_horizon.get("end_month", "2030-12")

    bom_config = assumptions.get("bom", {})
    input_prices_config = assumptions.get("input_prices", {})
    fixed_cogs_config = assumptions.get("fixed_cogs", {})

    # Generate months
    months = generate_months(start_month, end_month)

    # 1. Load and validate BOM
    bom = load_bom(assumptions)
    bom_errors = validate_bom(bom)
    output.errors.extend(bom_errors)

    # 2. Calculate input prices
    input_ids = get_all_input_ids(bom)
    price_errors = validate_input_prices(input_prices_config)
    output.errors.extend(price_errors)

    input_prices = calculate_all_input_prices(months, input_ids, input_prices_config)

    # 3. Calculate consumption
    output.consumption = calculate_input_consumption(units_kg, bom)

    # 4. Calculate variable COGS
    output.variable_cogs_detailed = calculate_variable_cogs_detailed(
        output.consumption, input_prices
    )
    output.variable_cogs_product = aggregate_variable_cogs_by_product(
        output.variable_cogs_detailed
    )
    output.variable_cogs_total = aggregate_variable_cogs_total(
        output.variable_cogs_product
    )

    # 5. Calculate fixed COGS
    fixed_base = fixed_cogs_config.get("base_monthly", 0.0)
    fixed_ramp = fixed_cogs_config.get("ramp", {}).get("by_month", {})

    output.fixed_cogs = calculate_fixed_cogs(months, fixed_base, fixed_ramp)

    # Aggregate units by product/month for fixed COGS allocation
    units_by_product: Dict[Tuple[str, str], float] = defaultdict(float)
    for (month, product, market), kg in units_kg.items():
        units_by_product[(month, product)] += kg

    output.fixed_cogs_allocated = allocate_fixed_cogs(
        output.fixed_cogs, dict(units_by_product)
    )

    # 6. Calculate total COGS and unit costs
    # Total volume by month
    units_total: Dict[str, float] = defaultdict(float)
    for (month, product, market), kg in units_kg.items():
        units_total[month] += kg
    units_total = dict(units_total)

    # Total COGS = Variable + Fixed
    for month in months:
        var_cogs = output.variable_cogs_total.get(month, 0.0)
        fix_cogs = output.fixed_cogs.get(month, 0.0)
        output.total_cogs[month] = var_cogs + fix_cogs

    # Unit costs
    output.unit_variable_cogs = calculate_unit_variable_cogs(
        output.variable_cogs_total, units_total
    )

    for month in months:
        total_kg = units_total.get(month, 0.0)
        if total_kg > 0:
            output.unit_fixed_cogs[month] = output.fixed_cogs.get(month, 0.0) / total_kg
            output.unit_total_cogs[month] = output.total_cogs.get(month, 0.0) / total_kg
        else:
            output.unit_fixed_cogs[month] = 0.0
            output.unit_total_cogs[month] = 0.0

    return output


def validate_cogs_output(output: COGSOutput) -> List[str]:
    """
    Validate COGS engine output.

    Args:
        output: COGSOutput to validate

    Returns:
        List of validation errors

    Validations:
        - All COGS values >= 0
        - Total COGS = Variable + Fixed
        - No flat COGS (variable must come from BOM)
    """
    errors = []
    tolerance = 0.01

    # Check non-negative
    for key, cogs in output.variable_cogs_detailed.items():
        if cogs < 0:
            errors.append(f"Negative variable COGS at {key}: {cogs}")

    for month, cogs in output.fixed_cogs.items():
        if cogs < 0:
            errors.append(f"Negative fixed COGS at {month}: {cogs}")

    # Check total = variable + fixed
    for month, total in output.total_cogs.items():
        var = output.variable_cogs_total.get(month, 0.0)
        fix = output.fixed_cogs.get(month, 0.0)
        expected = var + fix
        if abs(total - expected) > tolerance:
            errors.append(
                f"Total COGS mismatch at {month}: {total} != {var} + {fix}"
            )

    return errors


# =============================================================================
# END OF COGS ENGINE
# =============================================================================
