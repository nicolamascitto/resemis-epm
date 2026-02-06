# =============================================================================
# RESEMIS EPM ENGINE - PRICING MODULE
# =============================================================================
# Calculates net prices after discounts.
# All prices in EUR/kg.
#
# FORMULA:
# Net_price[t,p,m] = List_price[t,p] * (1 - Discount[t,p,m])
# =============================================================================

from typing import Dict, Tuple


def get_price_for_month(
    month: str,
    prices_by_month: Dict[str, float],
    base_price: float
) -> float:
    """
    Get price for a specific month, using most recent defined price.

    Args:
        month: Target month "YYYY-MM"
        prices_by_month: Price overrides by month Dict[month, price]
        base_price: Default price if no override

    Returns:
        Price for the month (EUR/kg)

    Logic:
        - If exact month exists in prices_by_month, use it
        - Otherwise, use the most recent price <= month
        - If no prices defined before month, use base_price
    """
    if not prices_by_month:
        return base_price

    if month in prices_by_month:
        return prices_by_month[month]

    # Find most recent price before this month
    applicable_price = base_price
    for price_month, price in sorted(prices_by_month.items()):
        if price_month <= month:
            applicable_price = price
        else:
            break

    return applicable_price


def get_discount_for_month(
    month: str,
    product: str,
    market: str,
    discounts: Dict
) -> float:
    """
    Get discount percentage for a specific month/product/market.

    Args:
        month: Target month "YYYY-MM"
        product: Product ID
        market: Market ID
        discounts: Nested discount structure from assumptions

    Returns:
        Discount percentage [0, 1], defaults to 0 if not found

    Logic:
        - Navigate through nested structure
        - If month not found, use most recent discount <= month
        - If no discount defined, return 0
    """
    by_product = discounts.get("by_product", {})
    product_discounts = by_product.get(product, {})
    by_market = product_discounts.get("by_market", {})
    market_discounts = by_market.get(market, {})
    by_month = market_discounts.get("by_month", {})

    if not by_month:
        return 0.0

    if month in by_month:
        return by_month[month]

    # Find most recent discount
    applicable_discount = 0.0
    for discount_month, discount in sorted(by_month.items()):
        if discount_month <= month:
            applicable_discount = discount
        else:
            break

    return applicable_discount


def calculate_net_price(
    month: str,
    product: str,
    market: str,
    list_prices: Dict,
    discounts: Dict
) -> float:
    """
    Calculate net price for a single month/product/market combination.

    Args:
        month: Target month "YYYY-MM"
        product: Product ID
        market: Market ID
        list_prices: List price structure from assumptions
        discounts: Discount structure from assumptions

    Returns:
        Net price in EUR/kg

    Formula:
        Net_price = List_price * (1 - Discount_pct)

    Notes:
        - Discount is applied as (1 - discount) so 10% discount = 0.9 multiplier
        - List price uses step function (most recent defined price)
    """
    # Get list price for this product/month
    product_prices = list_prices.get("by_product", {}).get(product, {})
    base_price = product_prices.get("base_price", 0.0)
    prices_by_month = product_prices.get("by_month", {})

    list_price = get_price_for_month(month, prices_by_month, base_price)

    # Get discount
    discount_pct = get_discount_for_month(month, product, market, discounts)

    # Calculate net price
    net_price = list_price * (1 - discount_pct)

    return net_price


def calculate_all_net_prices(
    months: list,
    products: list,
    markets: list,
    list_prices: Dict,
    discounts: Dict
) -> Dict[Tuple[str, str, str], float]:
    """
    Calculate net prices for all month/product/market combinations.

    Args:
        months: List of months ["YYYY-MM", ...]
        products: List of product IDs
        markets: List of market IDs
        list_prices: List price structure from assumptions
        discounts: Discount structure from assumptions

    Returns:
        Net prices indexed by (month, product, market)
        Dict[(month, product, market), EUR/kg]

    Formula:
        Net_price[t,p,m] = List_price[t,p] * (1 - Discount[t,p,m])
    """
    result: Dict[Tuple[str, str, str], float] = {}

    for month in months:
        for product in products:
            for market in markets:
                net_price = calculate_net_price(
                    month, product, market, list_prices, discounts
                )
                result[(month, product, market)] = net_price

    return result


def validate_pricing_inputs(
    list_prices: Dict,
    discounts: Dict
) -> list:
    """
    Validate pricing assumptions.

    Args:
        list_prices: List price structure
        discounts: Discount structure

    Returns:
        List of validation errors (empty if valid)

    Validations:
        - All list prices >= 0
        - All discounts in [0, 1]
    """
    errors = []

    # Validate list prices
    by_product = list_prices.get("by_product", {})
    for product, product_data in by_product.items():
        base_price = product_data.get("base_price", 0)
        if base_price < 0:
            errors.append(f"Negative base price for {product}: {base_price}")

        by_month = product_data.get("by_month", {})
        for month, price in by_month.items():
            if price < 0:
                errors.append(f"Negative price for {product} at {month}: {price}")

    # Validate discounts
    by_product = discounts.get("by_product", {})
    for product, product_data in by_product.items():
        by_market = product_data.get("by_market", {})
        for market, market_data in by_market.items():
            by_month = market_data.get("by_month", {})
            for month, discount in by_month.items():
                if discount < 0 or discount > 1:
                    errors.append(
                        f"Discount out of range [0,1] for {product}/{market} "
                        f"at {month}: {discount}"
                    )

    return errors


# =============================================================================
# END OF PRICING MODULE
# =============================================================================
