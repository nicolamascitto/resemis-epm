# =============================================================================
# RESEMIS EPM ENGINE - PRODUCT MIX MODULE
# =============================================================================
# Allocates volume to products based on mix percentages.
# Mix varies by market and year.
#
# FORMULA:
# Units_kg[t,p,m] = Allocated_kg[t,m] * Mix_pct[year(t),p,m]
# =============================================================================

from typing import Dict, Tuple


def get_year_from_month(month: str) -> str:
    """Extract year from month string "YYYY-MM" -> "YYYY"."""
    return month[:4]


def get_mix_for_month(
    month: str,
    product: str,
    market: str,
    mix_config: Dict
) -> float:
    """
    Get product mix percentage for a specific month/product/market.

    Args:
        month: Target month "YYYY-MM"
        product: Product ID
        market: Market ID
        mix_config: Mix structure from assumptions

    Returns:
        Mix percentage [0, 1]

    Logic:
        - Mix is defined by year, not month
        - If year not found, use most recent defined year
        - If market/product not found, return 0
    """
    year = get_year_from_month(month)

    by_market = mix_config.get("by_market", {})
    market_mix = by_market.get(market, {})
    by_product = market_mix.get("by_product", {})
    product_mix = by_product.get(product, {})
    by_year = product_mix.get("by_year", {})

    if not by_year:
        return 0.0

    if year in by_year:
        return by_year[year]

    # Find most recent year
    applicable_mix = 0.0
    for mix_year, mix_pct in sorted(by_year.items()):
        if mix_year <= year:
            applicable_mix = mix_pct
        else:
            break

    return applicable_mix


def allocate_to_products(
    allocated_kg_by_market: Dict[Tuple[str, str], float],
    products: list,
    mix_config: Dict
) -> Dict[Tuple[str, str, str], float]:
    """
    Allocate kg to products based on mix percentages.

    Args:
        allocated_kg_by_market: Kg by month and market
                                Dict[(month, market), kg]
        products: List of product IDs
        mix_config: Mix structure from assumptions

    Returns:
        Kg by month, product, and market
        Dict[(month, product, market), kg]

    Formula:
        Units_kg[t,p,m] = Allocated_kg[t,m] * Mix_pct[year(t),p,m]

    Notes:
        - Mix must sum to 1 for each market/year (validated separately)
        - Products with 0 mix get 0 kg
    """
    result: Dict[Tuple[str, str, str], float] = {}

    for (month, market), kg in allocated_kg_by_market.items():
        for product in products:
            mix_pct = get_mix_for_month(month, product, market, mix_config)
            result[(month, product, market)] = kg * mix_pct

    return result


def validate_mix(
    months: list,
    markets: list,
    products: list,
    mix_config: Dict,
    tolerance: float = 0.001
) -> list:
    """
    Validate that mix sums to 1 for each market/year.

    Args:
        months: List of months to validate
        markets: List of market IDs
        products: List of product IDs
        mix_config: Mix structure from assumptions
        tolerance: Acceptable deviation from 1.0

    Returns:
        List of validation errors (empty if valid)

    Validation:
        SUM_p(Mix_pct[year,p,m]) = 1 for all years and markets
    """
    errors = []

    # Get unique years from months
    years = sorted(set(get_year_from_month(m) for m in months))

    for year in years:
        month = f"{year}-01"  # Use January for mix lookup
        for market in markets:
            total_mix = 0.0
            for product in products:
                mix_pct = get_mix_for_month(month, product, market, mix_config)
                total_mix += mix_pct

            if abs(total_mix - 1.0) > tolerance:
                errors.append(
                    f"Mix does not sum to 1 for {market}/{year}: {total_mix:.4f}"
                )

    return errors


# =============================================================================
# END OF MIX MODULE
# =============================================================================
