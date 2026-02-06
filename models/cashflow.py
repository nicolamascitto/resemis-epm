# =============================================================================
# RESEMIS EPM ENGINE - CASHFLOW ENGINE
# =============================================================================
# Calculates cash flows and cash balance tracking.
#
# FLOW:
# EBITDA = Revenue - COGS - OpEx
# Operating CF = EBITDA - Delta_WC
# Free CF = Operating CF - Capex
# Net CF = Free CF + Financing CF
# Cash Balance[t] = Cash Balance[t-1] + Net CF[t]
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CapexSchedule:
    """Capital expenditure schedule."""
    base_monthly: float = 0.0  # Monthly recurring capex
    milestones: Dict[str, float] = field(default_factory=dict)  # One-off by month


@dataclass
class FundingSchedule:
    """Funding schedule (equity and debt)."""
    equity_raises: Dict[str, float] = field(default_factory=dict)  # by month
    debt_draws: Dict[str, float] = field(default_factory=dict)  # by month
    debt_repayments: Dict[str, float] = field(default_factory=dict)  # by month
    interest_rate: float = 0.0  # Annual rate


@dataclass
class CashflowOutput:
    """Output structure for cashflow engine."""

    # P&L derived
    ebitda: Dict[str, float] = field(default_factory=dict)

    # Cash flows
    operating_cf: Dict[str, float] = field(default_factory=dict)
    capex: Dict[str, float] = field(default_factory=dict)
    free_cf: Dict[str, float] = field(default_factory=dict)
    financing_cf: Dict[str, float] = field(default_factory=dict)
    net_cf: Dict[str, float] = field(default_factory=dict)

    # Balances
    cash_balance: Dict[str, float] = field(default_factory=dict)
    debt_balance: Dict[str, float] = field(default_factory=dict)

    # Interest
    interest_expense: Dict[str, float] = field(default_factory=dict)

    # Warnings
    funding_gaps: List[str] = field(default_factory=list)

    # Validation
    errors: List[str] = field(default_factory=list)


def load_capex_schedule(assumptions: Dict) -> CapexSchedule:
    """Load capex schedule from assumptions."""
    capex_config = assumptions.get("capex", {})
    return CapexSchedule(
        base_monthly=capex_config.get("base_monthly", 0.0),
        milestones=capex_config.get("milestones", {}).get("by_month", {})
    )


def load_funding_schedule(assumptions: Dict) -> FundingSchedule:
    """Load funding schedule from assumptions."""
    funding_config = assumptions.get("funding", {})

    equity_raises = funding_config.get("equity", {}).get("by_month", {})

    debt_config = funding_config.get("debt", {})
    debt_by_month = debt_config.get("by_month", {})

    debt_draws = {}
    debt_repayments = {}
    for month, data in debt_by_month.items():
        if isinstance(data, dict):
            debt_draws[month] = data.get("draw", 0.0)
            debt_repayments[month] = data.get("repayment", 0.0)

    return FundingSchedule(
        equity_raises=equity_raises,
        debt_draws=debt_draws,
        debt_repayments=debt_repayments,
        interest_rate=debt_config.get("interest_rate", 0.0)
    )


def calculate_ebitda(
    revenue_total: Dict[str, float],
    cogs_total: Dict[str, float],
    opex_total: Dict[str, float]
) -> Dict[str, float]:
    """
    Calculate EBITDA.

    Formula: EBITDA[t] = Revenue[t] - COGS[t] - OpEx[t]
    """
    result: Dict[str, float] = {}
    all_months = set(revenue_total.keys()) | set(cogs_total.keys()) | set(opex_total.keys())

    for month in all_months:
        rev = revenue_total.get(month, 0.0)
        cogs = cogs_total.get(month, 0.0)
        opex = opex_total.get(month, 0.0)
        result[month] = rev - cogs - opex

    return result


def calculate_operating_cf(
    ebitda: Dict[str, float],
    delta_wc: Dict[str, float]
) -> Dict[str, float]:
    """
    Calculate Operating Cash Flow.

    Formula: Operating_CF[t] = EBITDA[t] - Delta_WC[t]
    """
    result: Dict[str, float] = {}
    all_months = set(ebitda.keys()) | set(delta_wc.keys())

    for month in all_months:
        result[month] = ebitda.get(month, 0.0) - delta_wc.get(month, 0.0)

    return result


def calculate_capex(
    months: List[str],
    capex_schedule: CapexSchedule
) -> Dict[str, float]:
    """
    Calculate total Capex by month.

    Formula: Capex[t] = base_monthly + milestone[t]
    """
    result: Dict[str, float] = {}

    for month in months:
        base = capex_schedule.base_monthly
        milestone = capex_schedule.milestones.get(month, 0.0)
        result[month] = base + milestone

    return result


def calculate_free_cf(
    operating_cf: Dict[str, float],
    capex: Dict[str, float]
) -> Dict[str, float]:
    """
    Calculate Free Cash Flow.

    Formula: Free_CF[t] = Operating_CF[t] - Capex[t]
    """
    result: Dict[str, float] = {}
    all_months = set(operating_cf.keys()) | set(capex.keys())

    for month in all_months:
        result[month] = operating_cf.get(month, 0.0) - capex.get(month, 0.0)

    return result


def calculate_financing_cf(
    months: List[str],
    funding_schedule: FundingSchedule,
    debt_balance: Dict[str, float]
) -> tuple:
    """
    Calculate Financing Cash Flow and interest.

    Returns: (financing_cf, interest_expense, updated_debt_balance)
    """
    financing_cf: Dict[str, float] = {}
    interest_expense: Dict[str, float] = {}
    new_debt_balance: Dict[str, float] = {}

    monthly_rate = funding_schedule.interest_rate / 12
    prev_debt = 0.0

    for month in months:
        # Interest on previous balance
        interest = prev_debt * monthly_rate
        interest_expense[month] = interest

        # Debt movements
        draw = funding_schedule.debt_draws.get(month, 0.0)
        repay = funding_schedule.debt_repayments.get(month, 0.0)

        # Update debt balance
        current_debt = prev_debt + draw - repay
        new_debt_balance[month] = current_debt
        prev_debt = current_debt

        # Equity
        equity = funding_schedule.equity_raises.get(month, 0.0)

        # Financing CF
        financing_cf[month] = equity + draw - repay - interest

    return financing_cf, interest_expense, new_debt_balance


def cashflow_engine(
    assumptions: Dict,
    revenue_total: Dict[str, float],
    cogs_total: Dict[str, float],
    opex_total: Dict[str, float],
    delta_wc: Dict[str, float]
) -> CashflowOutput:
    """
    Main cashflow engine.

    Args:
        assumptions: Full assumptions dictionary
        revenue_total: Total revenue by month
        cogs_total: Total COGS by month
        opex_total: Total OpEx by month
        delta_wc: Working capital change by month

    Returns:
        CashflowOutput with all cash flow calculations
    """
    output = CashflowOutput()

    # Load schedules
    capex_schedule = load_capex_schedule(assumptions)
    funding_schedule = load_funding_schedule(assumptions)
    initial_cash = assumptions.get("funding", {}).get("initial_cash", 0.0)

    # Get months
    from .revenue import generate_months
    time_horizon = assumptions.get("time_horizon", {})
    months = generate_months(
        time_horizon.get("start_month", "2026-01"),
        time_horizon.get("end_month", "2030-12")
    )

    # 1. EBITDA
    output.ebitda = calculate_ebitda(revenue_total, cogs_total, opex_total)

    # 2. Operating Cash Flow
    output.operating_cf = calculate_operating_cf(output.ebitda, delta_wc)

    # 3. Capex
    output.capex = calculate_capex(months, capex_schedule)

    # 4. Free Cash Flow
    output.free_cf = calculate_free_cf(output.operating_cf, output.capex)

    # 5. Financing Cash Flow (needs debt balance tracking)
    financing_cf, interest, debt_balance = calculate_financing_cf(
        months, funding_schedule, {}
    )
    output.financing_cf = financing_cf
    output.interest_expense = interest
    output.debt_balance = debt_balance

    # 6. Net Cash Flow and Cash Balance
    prev_cash = initial_cash

    for month in months:
        free = output.free_cf.get(month, 0.0)
        financing = output.financing_cf.get(month, 0.0)

        net_cf = free + financing
        output.net_cf[month] = net_cf

        cash_balance = prev_cash + net_cf
        output.cash_balance[month] = cash_balance

        # Flag negative cash (warning, not blocking)
        if cash_balance < 0:
            output.funding_gaps.append(
                f"{month}: Negative cash balance {cash_balance:.2f}"
            )

        prev_cash = cash_balance

    return output


def validate_cashflow_output(
    output: CashflowOutput,
    revenue_total: Dict[str, float],
    cogs_total: Dict[str, float],
    opex_total: Dict[str, float]
) -> List[str]:
    """Validate cashflow output."""
    errors = []
    tolerance = 0.01

    # Check EBITDA = Revenue - COGS - OpEx
    for month, ebitda in output.ebitda.items():
        rev = revenue_total.get(month, 0.0)
        cogs = cogs_total.get(month, 0.0)
        opex = opex_total.get(month, 0.0)
        expected = rev - cogs - opex
        if abs(ebitda - expected) > tolerance:
            errors.append(f"EBITDA mismatch at {month}: {ebitda} != {expected}")

    return errors


# =============================================================================
# END OF CASHFLOW ENGINE
# =============================================================================
