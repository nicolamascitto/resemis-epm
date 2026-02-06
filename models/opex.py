# =============================================================================
# RESEMIS EPM ENGINE - OPEX ENGINE
# =============================================================================
# Calculates operating expenses (fixed and variable).
#
# CATEGORIES:
# Fixed: management_ga, it_admin, rd_base, legal_compliance
# Variable: linked to activity drivers (kg, markets)
# S&M: special case with CAC per market
#
# KEY PRINCIPLE: OpEx NOT dependent on EUR revenue (activity-based)
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, Tuple, List
from collections import defaultdict


@dataclass
class FixedOpExCategory:
    """Fixed OpEx category configuration."""
    category_id: str
    base_monthly: float  # EUR per month
    ramp_factors: Dict[str, float] = field(default_factory=dict)  # by month


@dataclass
class VariableOpExDriver:
    """Variable OpEx driver configuration."""
    driver_id: str
    cost_per_unit: float  # EUR per unit of activity


@dataclass
class SMParams:
    """Sales & Marketing parameters."""
    fixed_base: float  # EUR per month
    ramp_factors: Dict[str, float] = field(default_factory=dict)  # by month
    cac_by_market: Dict[str, float] = field(default_factory=dict)  # EUR per market activation


@dataclass
class OpExOutput:
    """Output structure for OpEx engine."""

    # Detailed outputs
    fixed_opex: Dict[Tuple[str, str], float] = field(default_factory=dict)  # (month, category)
    variable_opex: Dict[Tuple[str, str], float] = field(default_factory=dict)  # (month, driver)
    sm_opex: Dict[str, float] = field(default_factory=dict)  # by month
    sm_cac: Dict[Tuple[str, str], float] = field(default_factory=dict)  # (month, market)

    # Aggregations
    total_fixed: Dict[str, float] = field(default_factory=dict)
    total_variable: Dict[str, float] = field(default_factory=dict)
    total_sm: Dict[str, float] = field(default_factory=dict)
    total_opex: Dict[str, float] = field(default_factory=dict)

    # Validation
    errors: List[str] = field(default_factory=list)


def get_ramp_for_month(month: str, ramp_factors: Dict[str, float]) -> float:
    """Get ramp factor for month using step function."""
    if not ramp_factors:
        return 1.0

    if month in ramp_factors:
        return ramp_factors[month]

    applicable_ramp = 1.0
    for ramp_month, ramp in sorted(ramp_factors.items()):
        if ramp_month <= month:
            applicable_ramp = ramp
        else:
            break

    return applicable_ramp


# =============================================================================
# FIXED OPEX
# =============================================================================

def load_fixed_opex_categories(assumptions: Dict) -> List[FixedOpExCategory]:
    """Load fixed OpEx categories from assumptions."""
    result = []
    opex_config = assumptions.get("opex", {})
    fixed_config = opex_config.get("fixed", {})
    by_category = fixed_config.get("by_category", {})

    for cat_id, cat_data in by_category.items():
        category = FixedOpExCategory(
            category_id=cat_id,
            base_monthly=cat_data.get("base_monthly", 0.0),
            ramp_factors=cat_data.get("ramp", {}).get("by_month", {})
        )
        result.append(category)

    return result


def calculate_fixed_opex(
    months: List[str],
    categories: List[FixedOpExCategory]
) -> Dict[Tuple[str, str], float]:
    """
    Calculate fixed OpEx by category and month.

    Formula: Fixed_OpEx[t,c] = base_monthly[c] * ramp[t,c]
    """
    result: Dict[Tuple[str, str], float] = {}

    for month in months:
        for cat in categories:
            ramp = get_ramp_for_month(month, cat.ramp_factors)
            result[(month, cat.category_id)] = cat.base_monthly * ramp

    return result


def aggregate_fixed_opex(
    fixed_opex: Dict[Tuple[str, str], float]
) -> Dict[str, float]:
    """Aggregate fixed OpEx by month."""
    result: Dict[str, float] = defaultdict(float)
    for (month, category), amount in fixed_opex.items():
        result[month] += amount
    return dict(result)


# =============================================================================
# ACTIVITY DRIVERS
# =============================================================================

def extract_activity_drivers(
    revenue_output,
    months: List[str],
    markets: List[dict]
) -> Dict[Tuple[str, str], float]:
    """
    Extract activity driver values from revenue output.

    Drivers:
    - units_kg_total: total kg sold per month
    - active_markets: count of markets with revenue > 0
    - new_markets_activated: markets activated in month (based on activation_month)
    """
    result: Dict[Tuple[str, str], float] = {}

    # Units kg total
    for month in months:
        total_kg = 0.0
        for (m, product, market), kg in revenue_output.units_kg.items():
            if m == month:
                total_kg += kg
        result[(month, "units_kg_total")] = total_kg

    # Active markets (markets with revenue > 0)
    for month in months:
        active_count = 0
        markets_with_revenue = set()
        for (m, product, market), rev in revenue_output.revenue.items():
            if m == month and rev > 0:
                markets_with_revenue.add(market)
        result[(month, "active_markets")] = len(markets_with_revenue)

    # New markets activated (based on activation_month)
    for month in months:
        new_count = 0
        for market in markets:
            if market.get("activation_month") == month:
                new_count += 1
        result[(month, "new_markets_activated")] = new_count

    return result


# =============================================================================
# VARIABLE OPEX
# =============================================================================

def load_variable_opex_drivers(assumptions: Dict) -> List[VariableOpExDriver]:
    """Load variable OpEx drivers from assumptions."""
    result = []
    opex_config = assumptions.get("opex", {})
    variable_config = opex_config.get("variable", {})
    by_driver = variable_config.get("by_driver", {})

    for driver_id, driver_data in by_driver.items():
        driver = VariableOpExDriver(
            driver_id=driver_id,
            cost_per_unit=driver_data.get("cost_per_unit", 0.0)
        )
        result.append(driver)

    return result


def calculate_variable_opex(
    activity_drivers: Dict[Tuple[str, str], float],
    drivers: List[VariableOpExDriver]
) -> Dict[Tuple[str, str], float]:
    """
    Calculate variable OpEx from activity drivers.

    Formula: Variable_OpEx[t,d] = Activity_value[t,d] * cost_per_unit[d]
    """
    result: Dict[Tuple[str, str], float] = {}

    for driver in drivers:
        for (month, driver_id), value in activity_drivers.items():
            if driver_id == driver.driver_id:
                result[(month, driver_id)] = value * driver.cost_per_unit

    return result


def aggregate_variable_opex(
    variable_opex: Dict[Tuple[str, str], float]
) -> Dict[str, float]:
    """Aggregate variable OpEx by month."""
    result: Dict[str, float] = defaultdict(float)
    for (month, driver), amount in variable_opex.items():
        result[month] += amount
    return dict(result)


# =============================================================================
# SALES & MARKETING
# =============================================================================

def load_sm_params(assumptions: Dict) -> SMParams:
    """Load S&M parameters from assumptions."""
    opex_config = assumptions.get("opex", {})
    sm_config = opex_config.get("sales_marketing", {})

    return SMParams(
        fixed_base=sm_config.get("fixed_base", 0.0),
        ramp_factors=sm_config.get("ramp", {}).get("by_month", {}),
        cac_by_market=sm_config.get("cac", {}).get("by_market", {})
    )


def calculate_sm_opex(
    months: List[str],
    markets: List[dict],
    sm_params: SMParams
) -> Tuple[Dict[str, float], Dict[Tuple[str, str], float]]:
    """
    Calculate S&M OpEx including CAC.

    Formula: SM_OpEx[t] = SM_fixed_base * SM_ramp[t] + SUM_m(New_markets[t,m] * CAC[m])

    Returns:
        Tuple of (sm_fixed_by_month, cac_by_month_market)
    """
    sm_fixed: Dict[str, float] = {}
    sm_cac: Dict[Tuple[str, str], float] = {}

    for month in months:
        # Fixed S&M with ramp
        ramp = get_ramp_for_month(month, sm_params.ramp_factors)
        sm_fixed[month] = sm_params.fixed_base * ramp

        # CAC for markets activated this month
        for market in markets:
            market_id = market["market_id"]
            if market.get("activation_month") == month:
                cac = sm_params.cac_by_market.get(market_id, 0.0)
                sm_cac[(month, market_id)] = cac

    return sm_fixed, sm_cac


def aggregate_sm_opex(
    sm_fixed: Dict[str, float],
    sm_cac: Dict[Tuple[str, str], float]
) -> Dict[str, float]:
    """Aggregate total S&M OpEx by month."""
    result: Dict[str, float] = dict(sm_fixed)
    for (month, market), cac in sm_cac.items():
        result[month] = result.get(month, 0.0) + cac
    return result


# =============================================================================
# MAIN OPEX ENGINE
# =============================================================================

def opex_engine(
    assumptions: Dict,
    revenue_output
) -> OpExOutput:
    """
    Main OpEx engine.

    Args:
        assumptions: Full assumptions dictionary
        revenue_output: Output from revenue engine

    Returns:
        OpExOutput with all calculated values
    """
    output = OpExOutput()

    # Extract config
    time_horizon = assumptions.get("time_horizon", {})
    start_month = time_horizon.get("start_month", "2026-01")
    end_month = time_horizon.get("end_month", "2030-12")
    markets_config = assumptions.get("markets", [])

    # Generate months
    from .revenue import generate_months
    months = generate_months(start_month, end_month)

    # 1. Fixed OpEx
    fixed_categories = load_fixed_opex_categories(assumptions)
    output.fixed_opex = calculate_fixed_opex(months, fixed_categories)
    output.total_fixed = aggregate_fixed_opex(output.fixed_opex)

    # 2. Activity drivers
    activity_drivers = extract_activity_drivers(revenue_output, months, markets_config)

    # 3. Variable OpEx
    variable_drivers = load_variable_opex_drivers(assumptions)
    output.variable_opex = calculate_variable_opex(activity_drivers, variable_drivers)
    output.total_variable = aggregate_variable_opex(output.variable_opex)

    # 4. S&M OpEx
    sm_params = load_sm_params(assumptions)
    sm_fixed, output.sm_cac = calculate_sm_opex(months, markets_config, sm_params)
    output.sm_opex = sm_fixed
    output.total_sm = aggregate_sm_opex(sm_fixed, output.sm_cac)

    # 5. Total OpEx
    for month in months:
        fixed = output.total_fixed.get(month, 0.0)
        variable = output.total_variable.get(month, 0.0)
        sm = output.total_sm.get(month, 0.0)
        output.total_opex[month] = fixed + variable + sm

    return output


def validate_opex_output(output: OpExOutput) -> List[str]:
    """Validate OpEx output."""
    errors = []

    # Check non-negative
    for key, amount in output.fixed_opex.items():
        if amount < 0:
            errors.append(f"Negative fixed OpEx at {key}: {amount}")

    for key, amount in output.variable_opex.items():
        if amount < 0:
            errors.append(f"Negative variable OpEx at {key}: {amount}")

    for month, amount in output.total_opex.items():
        if amount < 0:
            errors.append(f"Negative total OpEx at {month}: {amount}")

    return errors


# =============================================================================
# END OF OPEX ENGINE
# =============================================================================
