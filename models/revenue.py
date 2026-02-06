# =============================================================================
# RESEMIS EPM ENGINE - REVENUE ENGINE
# =============================================================================
# Main revenue calculation module that orchestrates volume, pricing, and mix.
#
# EXECUTION ORDER:
# 1. Calculate SOM with ramp for each market
# 2. Calculate addressable demand (TAM * SAM * SOM)
# 3. Calculate potential demand (sum across markets)
# 4. Apply capacity constraint (if defined)
# 5. Allocate back to markets (proportionally)
# 6. Allocate to products (mix)
# 7. Calculate net prices
# 8. Calculate revenue
# 9. Aggregate by product, market, total
#
# MAIN FORMULA:
# Revenue[t,p,m] = Units_kg[t,p,m] * Net_price[t,p,m]
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, Tuple, List
from collections import defaultdict

from .volume import (
    calculate_som_with_ramp,
    calculate_addressable_kg,
    calculate_potential_kg,
    apply_capacity_constraint,
    allocate_to_markets
)
from .pricing import calculate_all_net_prices, validate_pricing_inputs
from .mix import allocate_to_products, validate_mix


@dataclass
class RevenueOutput:
    """Output structure for revenue engine."""

    # Detailed outputs (month, product, market)
    units_kg: Dict[Tuple[str, str, str], float] = field(default_factory=dict)
    net_prices: Dict[Tuple[str, str, str], float] = field(default_factory=dict)
    revenue: Dict[Tuple[str, str, str], float] = field(default_factory=dict)

    # Aggregations
    revenue_total: Dict[str, float] = field(default_factory=dict)  # by month
    revenue_by_product: Dict[Tuple[str, str], float] = field(default_factory=dict)
    revenue_by_market: Dict[Tuple[str, str], float] = field(default_factory=dict)

    # Intermediate outputs (for debugging/validation)
    addressable_kg: Dict[Tuple[str, str], float] = field(default_factory=dict)
    potential_kg: Dict[str, float] = field(default_factory=dict)
    sellable_kg: Dict[str, float] = field(default_factory=dict)
    allocated_kg: Dict[Tuple[str, str], float] = field(default_factory=dict)

    # Validation
    errors: List[str] = field(default_factory=list)


def generate_months(start_month: str, end_month: str) -> List[str]:
    """
    Generate list of months between start and end (inclusive).

    Args:
        start_month: Start month "YYYY-MM"
        end_month: End month "YYYY-MM"

    Returns:
        List of months ["YYYY-MM", ...]
    """
    months = []
    year = int(start_month[:4])
    month = int(start_month[5:7])

    end_year = int(end_month[:4])
    end_mon = int(end_month[5:7])

    while (year, month) <= (end_year, end_mon):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1

    return months


def build_som_pct(
    months: List[str],
    markets: List[dict],
    volume_config: Dict
) -> Dict[Tuple[str, str], float]:
    """
    Build SOM percentage for all month/market combinations.

    Args:
        months: List of months
        markets: List of market configs with activation_month
        volume_config: Volume assumptions including som_share and ramp

    Returns:
        Dict[(month, market_id), som_pct]
    """
    som_pct = {}

    som_share = volume_config.get("som_share", {})
    per_market_pct = som_share.get("per_market_pct", {})
    ramp_config = som_share.get("ramp", {}).get("by_market", {})

    for market in markets:
        market_id = market["market_id"]
        activation_month = market.get("activation_month", months[0])
        steady_state = per_market_pct.get(market_id, 0.0)

        # Get ramp config for this market
        market_ramp = ramp_config.get(market_id, {})
        duration = market_ramp.get("duration_months", 0)
        curve = market_ramp.get("curve", "linear")
        ramp_start = market_ramp.get("start_month", activation_month)

        for month in months:
            som = calculate_som_with_ramp(
                month=month,
                market=market_id,
                steady_state_som=steady_state,
                activation_month=ramp_start,
                ramp_duration_months=duration,
                ramp_curve=curve
            )
            som_pct[(month, market_id)] = som

    return som_pct


def revenue_engine(assumptions: Dict) -> RevenueOutput:
    """
    Main revenue engine.

    Args:
        assumptions: Full assumptions dictionary loaded from YAML

    Returns:
        RevenueOutput with all calculated values

    Execution order:
        1. Generate month list
        2. Build SOM with ramp
        3. Calculate addressable demand
        4. Calculate potential demand
        5. Apply capacity constraint
        6. Allocate back to markets
        7. Allocate to products (mix)
        8. Calculate net prices
        9. Calculate revenue
        10. Aggregate outputs
    """
    output = RevenueOutput()

    # Extract config sections
    time_horizon = assumptions.get("time_horizon", {})
    start_month = time_horizon.get("start_month", "2026-01")
    end_month = time_horizon.get("end_month", "2030-12")

    products_config = assumptions.get("products", [])
    markets_config = assumptions.get("markets", [])
    volume_config = assumptions.get("volume", {})
    mix_config = assumptions.get("mix", {})
    pricing_config = assumptions.get("pricing", {})

    # Extract IDs
    product_ids = [p["product_id"] for p in products_config]
    market_ids = [m["market_id"] for m in markets_config]

    # 1. Generate months
    months = generate_months(start_month, end_month)

    # 2. Build SOM with ramp
    som_pct = build_som_pct(months, markets_config, volume_config)

    # 3. Calculate addressable demand
    tam_kg = volume_config.get("tam", {}).get("per_market_kg", {})
    sam_pct = volume_config.get("sam_share", {}).get("per_market_pct", {})

    output.addressable_kg = calculate_addressable_kg(tam_kg, sam_pct, som_pct)

    # 4. Calculate potential demand
    output.potential_kg = calculate_potential_kg(output.addressable_kg)

    # 5. Apply capacity constraint
    capacity_config = volume_config.get("capacity", {})
    if capacity_config.get("enabled", False):
        capacity_kg = capacity_config.get("by_month", {})
    else:
        capacity_kg = None

    output.sellable_kg = apply_capacity_constraint(output.potential_kg, capacity_kg)

    # 6. Allocate back to markets
    output.allocated_kg = allocate_to_markets(output.sellable_kg, output.addressable_kg)

    # 7. Allocate to products (mix)
    output.units_kg = allocate_to_products(
        output.allocated_kg, product_ids, mix_config
    )

    # 8. Validate mix
    mix_errors = validate_mix(months, market_ids, product_ids, mix_config)
    output.errors.extend(mix_errors)

    # 9. Calculate net prices
    list_prices = pricing_config.get("list_price", {})
    discounts = pricing_config.get("discounts", {})

    # Validate pricing
    pricing_errors = validate_pricing_inputs(list_prices, discounts)
    output.errors.extend(pricing_errors)

    output.net_prices = calculate_all_net_prices(
        months, product_ids, market_ids, list_prices, discounts
    )

    # 10. Calculate revenue
    for (month, product, market), kg in output.units_kg.items():
        net_price = output.net_prices.get((month, product, market), 0.0)
        revenue = kg * net_price
        output.revenue[(month, product, market)] = revenue

    # 11. Aggregate
    revenue_total = defaultdict(float)
    revenue_by_product = defaultdict(float)
    revenue_by_market = defaultdict(float)

    for (month, product, market), rev in output.revenue.items():
        revenue_total[month] += rev
        revenue_by_product[(month, product)] += rev
        revenue_by_market[(month, market)] += rev

    # Convert defaultdicts to regular dicts
    output.revenue_total = dict(revenue_total)
    output.revenue_by_product = dict(revenue_by_product)
    output.revenue_by_market = dict(revenue_by_market)

    return output


def validate_revenue_output(output: RevenueOutput) -> List[str]:
    """
    Validate revenue engine output.

    Args:
        output: RevenueOutput to validate

    Returns:
        List of validation errors

    Validations:
        - All units_kg >= 0
        - All revenue >= 0
        - Revenue = units_kg * net_price (within tolerance)
    """
    errors = []
    tolerance = 0.01  # EUR tolerance for rounding

    # Validate non-negative values
    for key, kg in output.units_kg.items():
        if kg < 0:
            errors.append(f"Negative units_kg at {key}: {kg}")

    for key, rev in output.revenue.items():
        if rev < 0:
            errors.append(f"Negative revenue at {key}: {rev}")

    # Validate revenue calculation
    for key, rev in output.revenue.items():
        kg = output.units_kg.get(key, 0.0)
        price = output.net_prices.get(key, 0.0)
        expected = kg * price
        if abs(rev - expected) > tolerance:
            errors.append(
                f"Revenue mismatch at {key}: {rev} != {kg} * {price} = {expected}"
            )

    return errors


# =============================================================================
# END OF REVENUE ENGINE
# =============================================================================
