# =============================================================================
# RESEMIS EPM ENGINE - WORKING CAPITAL ENGINE
# =============================================================================
# Calculates working capital components and changes.
#
# COMPONENTS:
# - AR (Accounts Receivable): Revenue-linked via DSO
# - Inventory: COGS-linked via DIO
# - AP (Accounts Payable): COGS-linked via DPO
#
# FORMULAS:
# AR[t] = Revenue[t] * (DSO_days / 30)
# Inventory[t] = COGS[t] * (DIO_days / 30)
# AP[t] = COGS[t] * (DPO_days / 30)
# Delta_WC[t] = Delta_AR[t] + Delta_Inventory[t] - Delta_AP[t]
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class WCTerms:
    """Working capital terms (days)."""
    dso_days: int  # Days Sales Outstanding
    dio_days: int  # Days Inventory Outstanding
    dpo_days: int  # Days Payables Outstanding


@dataclass
class WCOutput:
    """Output structure for working capital engine."""

    # Balances
    ar: Dict[str, float] = field(default_factory=dict)  # Accounts Receivable
    inventory: Dict[str, float] = field(default_factory=dict)
    ap: Dict[str, float] = field(default_factory=dict)  # Accounts Payable
    net_wc: Dict[str, float] = field(default_factory=dict)  # Net Working Capital

    # Changes (deltas)
    delta_ar: Dict[str, float] = field(default_factory=dict)
    delta_inventory: Dict[str, float] = field(default_factory=dict)
    delta_ap: Dict[str, float] = field(default_factory=dict)
    delta_wc: Dict[str, float] = field(default_factory=dict)

    # Validation
    errors: List[str] = field(default_factory=list)


def load_wc_terms(assumptions: Dict) -> WCTerms:
    """Load working capital terms from assumptions."""
    wc_config = assumptions.get("working_capital", {})
    return WCTerms(
        dso_days=wc_config.get("dso_days", 45),
        dio_days=wc_config.get("dio_days", 30),
        dpo_days=wc_config.get("dpo_days", 60)
    )


def calculate_ar(
    revenue_total: Dict[str, float],
    dso_days: int
) -> Dict[str, float]:
    """
    Calculate Accounts Receivable.

    Formula: AR[t] = Revenue[t] * (DSO_days / 30)
    """
    result: Dict[str, float] = {}
    for month, revenue in revenue_total.items():
        result[month] = revenue * (dso_days / 30)
    return result


def calculate_inventory(
    cogs_total: Dict[str, float],
    dio_days: int
) -> Dict[str, float]:
    """
    Calculate Inventory.

    Formula: Inventory[t] = COGS[t] * (DIO_days / 30)
    """
    result: Dict[str, float] = {}
    for month, cogs in cogs_total.items():
        result[month] = cogs * (dio_days / 30)
    return result


def calculate_ap(
    cogs_total: Dict[str, float],
    dpo_days: int
) -> Dict[str, float]:
    """
    Calculate Accounts Payable.

    Formula: AP[t] = COGS[t] * (DPO_days / 30)
    """
    result: Dict[str, float] = {}
    for month, cogs in cogs_total.items():
        result[month] = cogs * (dpo_days / 30)
    return result


def calculate_deltas(
    values: Dict[str, float],
    months: List[str]
) -> Dict[str, float]:
    """
    Calculate period-over-period changes.

    Formula: Delta[t] = Value[t] - Value[t-1]
    """
    result: Dict[str, float] = {}
    prev_value = 0.0

    for month in months:
        current = values.get(month, 0.0)
        result[month] = current - prev_value
        prev_value = current

    return result


def calculate_net_wc(
    ar: Dict[str, float],
    inventory: Dict[str, float],
    ap: Dict[str, float]
) -> Dict[str, float]:
    """
    Calculate Net Working Capital.

    Formula: Net_WC[t] = AR[t] + Inventory[t] - AP[t]
    """
    result: Dict[str, float] = {}
    all_months = set(ar.keys()) | set(inventory.keys()) | set(ap.keys())

    for month in all_months:
        result[month] = (
            ar.get(month, 0.0) +
            inventory.get(month, 0.0) -
            ap.get(month, 0.0)
        )

    return result


def working_capital_engine(
    assumptions: Dict,
    revenue_total: Dict[str, float],
    cogs_total: Dict[str, float]
) -> WCOutput:
    """
    Main working capital engine.

    Args:
        assumptions: Full assumptions dictionary
        revenue_total: Total revenue by month from revenue engine
        cogs_total: Total COGS by month from COGS engine

    Returns:
        WCOutput with all working capital calculations
    """
    output = WCOutput()

    # Load terms
    wc_terms = load_wc_terms(assumptions)

    # Validate terms
    if wc_terms.dso_days < 0:
        output.errors.append(f"Negative DSO: {wc_terms.dso_days}")
    if wc_terms.dio_days < 0:
        output.errors.append(f"Negative DIO: {wc_terms.dio_days}")
    if wc_terms.dpo_days < 0:
        output.errors.append(f"Negative DPO: {wc_terms.dpo_days}")

    # Get months in order
    from .revenue import generate_months
    time_horizon = assumptions.get("time_horizon", {})
    months = generate_months(
        time_horizon.get("start_month", "2026-01"),
        time_horizon.get("end_month", "2030-12")
    )

    # Calculate balances
    output.ar = calculate_ar(revenue_total, wc_terms.dso_days)
    output.inventory = calculate_inventory(cogs_total, wc_terms.dio_days)
    output.ap = calculate_ap(cogs_total, wc_terms.dpo_days)
    output.net_wc = calculate_net_wc(output.ar, output.inventory, output.ap)

    # Calculate deltas
    output.delta_ar = calculate_deltas(output.ar, months)
    output.delta_inventory = calculate_deltas(output.inventory, months)
    output.delta_ap = calculate_deltas(output.ap, months)

    # Delta WC = Delta AR + Delta Inventory - Delta AP
    for month in months:
        d_ar = output.delta_ar.get(month, 0.0)
        d_inv = output.delta_inventory.get(month, 0.0)
        d_ap = output.delta_ap.get(month, 0.0)
        output.delta_wc[month] = d_ar + d_inv - d_ap

    return output


def validate_wc_output(output: WCOutput) -> List[str]:
    """Validate working capital output."""
    errors = []

    # Check non-negative balances
    for month, ar in output.ar.items():
        if ar < 0:
            errors.append(f"Negative AR at {month}: {ar}")

    for month, inv in output.inventory.items():
        if inv < 0:
            errors.append(f"Negative Inventory at {month}: {inv}")

    for month, ap in output.ap.items():
        if ap < 0:
            errors.append(f"Negative AP at {month}: {ap}")

    return errors


# =============================================================================
# END OF WORKING CAPITAL ENGINE
# =============================================================================
