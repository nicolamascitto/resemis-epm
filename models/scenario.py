# =============================================================================
# RESEMIS EPM ENGINE - SCENARIO ENGINE
# =============================================================================
# Orchestrates the full model pipeline for each scenario.
#
# KEY PRINCIPLES:
# - Scenarios change INPUTS only, never formulas
# - Pure functions, no global state
# - Deterministic: same inputs -> same outputs
# - Ordering validation: Conservative <= Base <= Aggressive
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
from .assumptions import (
    deep_merge as deep_merge_assumptions,
    load_yaml_file as load_yaml_file_assumptions,
    load_scenario_assumptions as load_scenario_assumptions_impl,
    validate_assumptions as validate_assumptions_impl,
)


@dataclass
class ScenarioResult:
    """Complete results for one scenario."""
    scenario_id: str
    description: str = ""

    # Engine outputs
    revenue: object = None
    cogs: object = None
    opex: object = None
    working_capital: object = None
    cashflow: object = None
    valuation: object = None

    # Key metrics summary
    total_revenue: float = 0.0
    total_cogs: float = 0.0
    total_opex: float = 0.0
    final_ebitda: float = 0.0
    cumulative_fcf: float = 0.0
    enterprise_value: float = 0.0
    equity_value: float = 0.0
    irr: Optional[float] = None
    moic: float = 0.0

    # Validation
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ComparisonMatrix:
    """Comparison of multiple scenarios."""
    scenarios: List[str] = field(default_factory=list)
    metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    variances: Dict[str, Dict[str, float]] = field(default_factory=dict)


def deep_merge(base: dict, override: dict) -> dict:
    """Backward-compatible wrapper around assumptions.deep_merge."""
    return deep_merge_assumptions(base, override)


def load_yaml_file(path: Path) -> dict:
    """Backward-compatible wrapper around assumptions.load_yaml_file."""
    return load_yaml_file_assumptions(path)


def load_scenario_assumptions(
    scenario_id: str,
    assumptions_dir: Path
) -> dict:
    """Backward-compatible wrapper around assumptions.load_scenario_assumptions."""
    return load_scenario_assumptions_impl(scenario_id, assumptions_dir)


def validate_assumptions(assumptions: dict) -> List[str]:
    """Backward-compatible wrapper around assumptions.validate_assumptions."""
    return validate_assumptions_impl(assumptions)


def run_scenario(
    scenario_id: str,
    assumptions_dir: Path
) -> ScenarioResult:
    """
    Execute full pipeline for one scenario.

    Execution order:
    1. Load and validate assumptions
    2. Revenue Engine
    3. COGS Engine
    4. OpEx Engine
    5. Working Capital Engine
    6. Cashflow Engine
    7. Valuation Engine
    """
    from .revenue import revenue_engine
    from .cogs import cogs_engine
    from .opex import opex_engine
    from .working_capital import working_capital_engine
    from .cashflow import cashflow_engine
    from .valuation import valuation_engine

    result = ScenarioResult(scenario_id=scenario_id)

    # 1. Load assumptions
    assumptions = load_scenario_assumptions(scenario_id, assumptions_dir)
    result.description = assumptions.get("description", "")

    # Validate
    validation_errors = validate_assumptions(assumptions)
    if validation_errors:
        result.errors.extend(validation_errors)
        return result

    # 2. Revenue Engine
    result.revenue = revenue_engine(assumptions)
    result.errors.extend(result.revenue.errors)

    # 3. COGS Engine
    result.cogs = cogs_engine(assumptions, result.revenue.units_kg)
    result.errors.extend(result.cogs.errors)

    # 4. OpEx Engine
    result.opex = opex_engine(assumptions, result.revenue)
    result.errors.extend(result.opex.errors)

    # 5. Working Capital Engine
    result.working_capital = working_capital_engine(
        assumptions,
        result.revenue.revenue_total,
        result.cogs.total_cogs
    )
    result.errors.extend(result.working_capital.errors)

    # 6. Cashflow Engine
    result.cashflow = cashflow_engine(
        assumptions,
        result.revenue.revenue_total,
        result.cogs.total_cogs,
        result.opex.total_opex,
        result.working_capital.delta_wc
    )
    result.warnings.extend(result.cashflow.funding_gaps)

    # 7. Valuation Engine
    result.valuation = valuation_engine(
        assumptions,
        result.cashflow.free_cf,
        result.cashflow.ebitda,
        result.cashflow.cash_balance,
        result.cashflow.debt_balance,
        revenue_total=result.revenue.revenue_total,
        cogs_total=result.cogs.total_cogs,
        variable_cogs_total=result.cogs.variable_cogs_total,
        opex_total=result.opex.total_opex,
        variable_opex_total=result.opex.total_variable,
        units_kg_total=dict((m, sum(kg for (mo, p, ma), kg in result.revenue.units_kg.items() if mo == m))
                           for m in result.revenue.revenue_total.keys())
    )
    result.warnings.extend(result.valuation.warnings)

    # Extract key metrics
    result.total_revenue = sum(result.revenue.revenue_total.values())
    result.total_cogs = sum(result.cogs.total_cogs.values())
    result.total_opex = sum(result.opex.total_opex.values())

    if result.cashflow.ebitda:
        result.final_ebitda = list(result.cashflow.ebitda.values())[-1]
    result.cumulative_fcf = sum(result.cashflow.free_cf.values())

    result.enterprise_value = result.valuation.enterprise_value
    result.equity_value = result.valuation.equity_value
    result.irr = result.valuation.irr
    result.moic = result.valuation.moic

    return result


def run_all_scenarios(
    scenarios: List[str],
    assumptions_dir: Path
) -> Dict[str, ScenarioResult]:
    """
    Run all scenarios and collect results.

    Args:
        scenarios: List of scenario IDs (e.g., ["conservative", "base", "aggressive"])
        assumptions_dir: Path to assumptions directory

    Returns:
        Dict mapping scenario_id to ScenarioResult
    """
    results = {}
    for scenario_id in scenarios:
        results[scenario_id] = run_scenario(scenario_id, assumptions_dir)
    return results


def compare_scenarios(
    results: Dict[str, ScenarioResult],
    base_scenario: str = "base"
) -> ComparisonMatrix:
    """
    Generate comparison matrix and variance analysis.

    Args:
        results: Dict of scenario results
        base_scenario: Reference scenario for variance calculation

    Returns:
        ComparisonMatrix with metrics and variances
    """
    matrix = ComparisonMatrix()
    matrix.scenarios = list(results.keys())

    # Metrics to compare
    metric_names = [
        "total_revenue", "total_cogs", "total_opex",
        "final_ebitda", "cumulative_fcf",
        "enterprise_value", "equity_value", "irr", "moic"
    ]

    base_result = results.get(base_scenario)

    for metric in metric_names:
        matrix.metrics[metric] = {}
        matrix.variances[metric] = {}

        for scenario_id, result in results.items():
            value = getattr(result, metric, None)
            if value is not None:
                matrix.metrics[metric][scenario_id] = value

                # Calculate variance vs base
                if base_result:
                    base_value = getattr(base_result, metric, None)
                    if base_value is not None and base_value != 0:
                        variance = (value - base_value) / abs(base_value)
                        matrix.variances[metric][scenario_id] = variance

    return matrix


def validate_scenario_ordering(
    results: Dict[str, ScenarioResult]
) -> List[str]:
    """
    Validate: Conservative <= Base <= Aggressive for key metrics.

    Returns list of ordering violations (blocking errors).
    """
    errors = []

    cons = results.get("conservative")
    base = results.get("base")
    agg = results.get("aggressive")

    if not (cons and base and agg):
        return []  # Can't validate without all three

    # Metrics that should be ordered (positive is good)
    ordered_metrics = [
        ("total_revenue", "higher is better"),
        ("final_ebitda", "higher is better"),
        ("cumulative_fcf", "higher is better"),
        ("enterprise_value", "higher is better"),
        ("moic", "higher is better"),
    ]

    for metric, direction in ordered_metrics:
        cons_val = getattr(cons, metric, 0)
        base_val = getattr(base, metric, 0)
        agg_val = getattr(agg, metric, 0)

        # Check Conservative <= Base <= Aggressive
        if not (cons_val <= base_val <= agg_val):
            errors.append(
                f"Scenario ordering violation for {metric}: "
                f"Conservative ({cons_val:.2f}) <= Base ({base_val:.2f}) <= "
                f"Aggressive ({agg_val:.2f}) is not satisfied"
            )

    # IRR special handling (can be None)
    if cons.irr is not None and base.irr is not None and agg.irr is not None:
        if not (cons.irr <= base.irr <= agg.irr):
            errors.append(
                f"Scenario ordering violation for IRR: "
                f"Conservative ({cons.irr:.2%}) <= Base ({base.irr:.2%}) <= "
                f"Aggressive ({agg.irr:.2%}) is not satisfied"
            )

    return errors


# =============================================================================
# END OF SCENARIO ENGINE
# =============================================================================
