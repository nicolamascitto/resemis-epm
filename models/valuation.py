# =============================================================================
# RESEMIS EPM ENGINE - VALUATION ENGINE
# =============================================================================
# Investor-grade valuation calculations including DCF, IRR, MOIC.
#
# METHODS:
# - Gordon Growth: Terminal = FCF * (1+g) / (r-g)
# - Exit Multiple: Terminal = EBITDA * Multiple
#
# METRICS:
# - Enterprise Value = PV(FCF) + PV(Terminal)
# - Equity Value = EV + Cash - Debt
# - IRR = rate where NPV(equity CF) = 0
# - MOIC = Total proceeds / Total invested
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
import math


@dataclass
class ValuationParams:
    """Valuation parameters."""
    discount_rate: float  # Annual WACC or hurdle rate
    terminal_growth_rate: float  # Annual terminal growth
    terminal_multiple: Optional[float] = None  # EBITDA multiple if using multiple method
    method: str = "gordon"  # "gordon" or "multiple"
    exit_year: int = 2030


@dataclass
class EquitySchedule:
    """Equity investment schedule."""
    invested: Dict[str, float] = field(default_factory=dict)  # by month
    ownership_pct: float = 1.0
    exit_month: str = "2030-12"


@dataclass
class ValuationOutput:
    """Output structure for valuation engine."""

    # DCF components
    discount_factors: Dict[str, float] = field(default_factory=dict)
    pv_fcf: Dict[str, float] = field(default_factory=dict)  # PV of each FCF
    total_pv_fcf: float = 0.0
    terminal_value: float = 0.0
    pv_terminal: float = 0.0

    # Values
    enterprise_value: float = 0.0
    equity_value: float = 0.0

    # Returns
    irr: Optional[float] = None
    moic: float = 0.0
    payback_month: Optional[str] = None

    # Unit economics
    gross_margin: Dict[str, float] = field(default_factory=dict)
    contribution_margin: Dict[str, float] = field(default_factory=dict)
    revenue_per_kg: Dict[str, float] = field(default_factory=dict)
    cogs_per_kg: Dict[str, float] = field(default_factory=dict)
    opex_to_revenue: Dict[str, float] = field(default_factory=dict)

    # Warnings
    warnings: List[str] = field(default_factory=list)

    # Validation
    errors: List[str] = field(default_factory=list)


def load_valuation_params(assumptions: Dict) -> ValuationParams:
    """Load valuation parameters from assumptions."""
    val_config = assumptions.get("valuation", {})
    return ValuationParams(
        discount_rate=val_config.get("discount_rate", 0.15),
        terminal_growth_rate=val_config.get("terminal_growth_rate", 0.02),
        terminal_multiple=val_config.get("terminal_multiple"),
        method=val_config.get("terminal_method", "gordon"),
        exit_year=val_config.get("exit_year", 2030)
    )


def load_equity_schedule(assumptions: Dict) -> EquitySchedule:
    """Load equity schedule from assumptions."""
    val_config = assumptions.get("valuation", {})
    equity_config = val_config.get("equity", {})
    return EquitySchedule(
        invested=equity_config.get("invested", {}).get("by_month", {}),
        ownership_pct=equity_config.get("ownership_pct", 1.0),
        exit_month=f"{val_config.get('exit_year', 2030)}-12"
    )


def calculate_discount_factors(
    months: List[str],
    annual_rate: float
) -> Dict[str, float]:
    """
    Calculate discount factors for each month.

    Formula: discount_factor[t] = 1 / (1 + monthly_rate)^t
    """
    monthly_rate = (1 + annual_rate) ** (1/12) - 1
    result: Dict[str, float] = {}

    for i, month in enumerate(months):
        periods = i + 1  # Month 1 is period 1
        result[month] = 1 / ((1 + monthly_rate) ** periods)

    return result


def calculate_pv_fcf(
    free_cf: Dict[str, float],
    discount_factors: Dict[str, float]
) -> tuple:
    """
    Calculate present value of free cash flows.

    Returns: (pv_fcf_by_month, total_pv_fcf)
    """
    pv_fcf: Dict[str, float] = {}
    total = 0.0

    for month, fcf in free_cf.items():
        df = discount_factors.get(month, 1.0)
        pv = fcf * df
        pv_fcf[month] = pv
        total += pv

    return pv_fcf, total


def calculate_terminal_value_gordon(
    final_fcf: float,
    discount_rate: float,
    terminal_growth: float
) -> float:
    """
    Calculate terminal value using Gordon Growth model.

    Formula: TV = FCF * (1 + g) / (r - g)
    """
    if discount_rate <= terminal_growth:
        raise ValueError("Discount rate must be greater than terminal growth rate")

    return final_fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)


def calculate_terminal_value_multiple(
    final_ebitda: float,
    multiple: float
) -> float:
    """
    Calculate terminal value using exit multiple.

    Formula: TV = EBITDA * Multiple
    """
    return final_ebitda * multiple


def calculate_irr(
    cash_flows: List[float],
    periods: int = 12
) -> Optional[float]:
    """
    Calculate IRR using Newton-Raphson method.

    Args:
        cash_flows: List of cash flows (negative = investment, positive = return)
        periods: Periods per year (12 for monthly)

    Returns:
        Annual IRR or None if no solution
    """
    if not cash_flows or all(cf == 0 for cf in cash_flows):
        return None

    # Check for sign change
    has_negative = any(cf < 0 for cf in cash_flows)
    has_positive = any(cf > 0 for cf in cash_flows)
    if not (has_negative and has_positive):
        return None

    def npv(rate):
        monthly_rate = (1 + rate) ** (1/periods) - 1
        total = 0.0
        for i, cf in enumerate(cash_flows):
            total += cf / ((1 + monthly_rate) ** i)
        return total

    def npv_derivative(rate):
        monthly_rate = (1 + rate) ** (1/periods) - 1
        d_monthly = (1/periods) * (1 + rate) ** (1/periods - 1)
        total = 0.0
        for i, cf in enumerate(cash_flows):
            if i > 0:
                total -= i * cf * d_monthly / ((1 + monthly_rate) ** (i + 1))
        return total

    # Newton-Raphson
    rate = 0.10  # Initial guess
    for _ in range(100):
        try:
            f = npv(rate)
            f_prime = npv_derivative(rate)
            if abs(f_prime) < 1e-10:
                break
            new_rate = rate - f / f_prime
            if abs(new_rate - rate) < 1e-6:
                return new_rate
            rate = new_rate
            # Bound rate
            rate = max(-0.99, min(10.0, rate))
        except (ValueError, ZeroDivisionError):
            break

    return rate if abs(npv(rate)) < 0.01 else None


def calculate_moic(
    total_invested: float,
    total_proceeds: float
) -> float:
    """
    Calculate Multiple on Invested Capital.

    Formula: MOIC = Total proceeds / Total invested
    """
    if total_invested <= 0:
        return 0.0
    return total_proceeds / total_invested


def calculate_payback(
    equity_cf: Dict[str, float],
    months: List[str]
) -> Optional[str]:
    """
    Calculate payback period.

    Returns first month where cumulative equity CF >= 0
    """
    cumulative = 0.0
    for month in months:
        cumulative += equity_cf.get(month, 0.0)
        if cumulative >= 0:
            return month
    return None


def calculate_unit_economics(
    revenue_total: Dict[str, float],
    cogs_total: Dict[str, float],
    variable_cogs: Dict[str, float],
    opex_total: Dict[str, float],
    variable_opex: Dict[str, float],
    units_kg_total: Dict[str, float]
) -> tuple:
    """
    Calculate unit economics KPIs.

    Returns: (gross_margin, contribution_margin, rev_per_kg, cogs_per_kg, opex_to_rev)
    """
    gross_margin: Dict[str, float] = {}
    contribution_margin: Dict[str, float] = {}
    revenue_per_kg: Dict[str, float] = {}
    cogs_per_kg: Dict[str, float] = {}
    opex_to_revenue: Dict[str, float] = {}

    all_months = set(revenue_total.keys())

    for month in all_months:
        rev = revenue_total.get(month, 0.0)
        cogs = cogs_total.get(month, 0.0)
        var_cogs = variable_cogs.get(month, 0.0)
        opex = opex_total.get(month, 0.0)
        var_opex = variable_opex.get(month, 0.0)
        kg = units_kg_total.get(month, 0.0)

        # Gross margin = (Revenue - COGS) / Revenue
        if rev > 0:
            gross_margin[month] = (rev - cogs) / rev
            opex_to_revenue[month] = opex / rev
        else:
            gross_margin[month] = 0.0
            opex_to_revenue[month] = 0.0

        # Contribution margin = (Revenue - Var COGS - Var OpEx) / Revenue
        if rev > 0:
            contribution_margin[month] = (rev - var_cogs - var_opex) / rev
        else:
            contribution_margin[month] = 0.0

        # Per kg metrics
        if kg > 0:
            revenue_per_kg[month] = rev / kg
            cogs_per_kg[month] = cogs / kg
        else:
            revenue_per_kg[month] = 0.0
            cogs_per_kg[month] = 0.0

    return gross_margin, contribution_margin, revenue_per_kg, cogs_per_kg, opex_to_revenue


def valuation_engine(
    assumptions: Dict,
    free_cf: Dict[str, float],
    ebitda: Dict[str, float],
    cash_balance: Dict[str, float],
    debt_balance: Dict[str, float],
    revenue_total: Dict[str, float] = None,
    cogs_total: Dict[str, float] = None,
    variable_cogs_total: Dict[str, float] = None,
    opex_total: Dict[str, float] = None,
    variable_opex_total: Dict[str, float] = None,
    units_kg_total: Dict[str, float] = None
) -> ValuationOutput:
    """
    Main valuation engine.

    Args:
        assumptions: Full assumptions dictionary
        free_cf: Free cash flow by month
        ebitda: EBITDA by month
        cash_balance: Cash balance by month
        debt_balance: Debt balance by month
        revenue_total: Revenue by month (for unit economics)
        cogs_total: COGS by month (for unit economics)
        variable_cogs_total: Variable COGS by month
        opex_total: OpEx by month (for unit economics)
        variable_opex_total: Variable OpEx by month
        units_kg_total: Volume by month (for unit economics)

    Returns:
        ValuationOutput with all valuation calculations
    """
    output = ValuationOutput()

    # Load params
    val_params = load_valuation_params(assumptions)
    equity_schedule = load_equity_schedule(assumptions)

    # Validate
    if val_params.discount_rate <= val_params.terminal_growth_rate:
        output.errors.append(
            f"Discount rate ({val_params.discount_rate}) must be > "
            f"terminal growth ({val_params.terminal_growth_rate})"
        )
        return output

    # Get months in order
    from .revenue import generate_months
    time_horizon = assumptions.get("time_horizon", {})
    months = generate_months(
        time_horizon.get("start_month", "2026-01"),
        time_horizon.get("end_month", "2030-12")
    )

    # 1. Calculate discount factors
    output.discount_factors = calculate_discount_factors(months, val_params.discount_rate)

    # 2. Calculate PV of FCF
    output.pv_fcf, output.total_pv_fcf = calculate_pv_fcf(free_cf, output.discount_factors)

    # 3. Calculate terminal value
    final_month = months[-1] if months else None
    if final_month:
        final_fcf = free_cf.get(final_month, 0.0)
        final_ebitda = ebitda.get(final_month, 0.0)
        final_df = output.discount_factors.get(final_month, 1.0)

        if val_params.method == "gordon":
            output.terminal_value = calculate_terminal_value_gordon(
                final_fcf, val_params.discount_rate, val_params.terminal_growth_rate
            )
        elif val_params.method == "multiple" and val_params.terminal_multiple:
            output.terminal_value = calculate_terminal_value_multiple(
                final_ebitda, val_params.terminal_multiple
            )

        output.pv_terminal = output.terminal_value * final_df

        # Warning if terminal > 70% of EV
        ev_total = output.total_pv_fcf + output.pv_terminal
        if ev_total > 0 and output.pv_terminal / ev_total > 0.70:
            output.warnings.append(
                f"Terminal value represents {output.pv_terminal/ev_total:.1%} of EV"
            )

    # 4. Enterprise Value
    output.enterprise_value = output.total_pv_fcf + output.pv_terminal

    # 5. Equity Value
    final_cash = cash_balance.get(final_month, 0.0) if final_month else 0.0
    final_debt = debt_balance.get(final_month, 0.0) if final_month else 0.0
    output.equity_value = output.enterprise_value + final_cash - final_debt

    # 6. IRR
    equity_cf: Dict[str, float] = {}
    for month in months:
        equity_cf[month] = -equity_schedule.invested.get(month, 0.0)
    if final_month:
        equity_cf[final_month] += output.equity_value * equity_schedule.ownership_pct

    cf_list = [equity_cf.get(m, 0.0) for m in months]
    output.irr = calculate_irr(cf_list)

    # 7. MOIC
    total_invested = sum(equity_schedule.invested.values())
    total_proceeds = output.equity_value * equity_schedule.ownership_pct
    output.moic = calculate_moic(total_invested, total_proceeds)

    # 8. Payback
    output.payback_month = calculate_payback(equity_cf, months)

    # 9. Unit Economics (if data provided)
    if revenue_total and cogs_total and opex_total:
        (output.gross_margin, output.contribution_margin, output.revenue_per_kg,
         output.cogs_per_kg, output.opex_to_revenue) = calculate_unit_economics(
            revenue_total, cogs_total,
            variable_cogs_total or {},
            opex_total,
            variable_opex_total or {},
            units_kg_total or {}
        )

    return output


def validate_valuation_output(output: ValuationOutput) -> List[str]:
    """Validate valuation output."""
    errors = []

    if output.enterprise_value < 0:
        errors.append(f"Negative enterprise value: {output.enterprise_value}")

    if output.irr is not None and (output.irr < -1 or output.irr > 10):
        errors.append(f"IRR out of reasonable range: {output.irr}")

    return errors


# =============================================================================
# END OF VALUATION ENGINE
# =============================================================================
