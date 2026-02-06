# =============================================================================
# RESEMIS EPM ENGINE - MAIN ENTRY POINT
# =============================================================================
# Command-line interface for running the EPM engine.
#
# Usage:
#   python main.py run --scenario base
#   python main.py run --all
#   python main.py validate
# =============================================================================

import argparse
from pathlib import Path
import json
import copy
import yaml

from models.scenario import (
    run_scenario, run_all_scenarios,
    compare_scenarios, validate_scenario_ordering
)
from models.validation_report import generate_validation_report, format_report
from models.workbook_bridge import (
    build_assumptions_from_workbook,
    reconcile_engine_to_workbook,
)
from models.revenue import revenue_engine
from models.cogs import cogs_engine
from models.opex import opex_engine
from models.working_capital import working_capital_engine
from models.cashflow import cashflow_engine
from models.valuation import valuation_engine


def run_single_scenario(scenario_id: str, assumptions_dir: Path):
    """Run a single scenario and print summary."""
    print(f"\nRunning scenario: {scenario_id}")
    print("-" * 40)

    result = run_scenario(scenario_id, assumptions_dir)

    # Print errors if any
    if result.errors:
        print("\nERRORS:")
        for error in result.errors:
            print(f"  - {error}")

    # Print warnings if any
    if result.warnings:
        print("\nWARNINGS:")
        for warning in result.warnings:
            print(f"  - {warning}")

    # Print key metrics
    print("\nKEY METRICS:")
    print(f"  Total Revenue:     EUR {result.total_revenue:,.0f}")
    print(f"  Total COGS:        EUR {result.total_cogs:,.0f}")
    print(f"  Total OpEx:        EUR {result.total_opex:,.0f}")
    print(f"  Final EBITDA:      EUR {result.final_ebitda:,.0f}")
    print(f"  Cumulative FCF:    EUR {result.cumulative_fcf:,.0f}")
    print(f"  Enterprise Value:  EUR {result.enterprise_value:,.0f}")
    print(f"  Equity Value:      EUR {result.equity_value:,.0f}")
    if result.irr is not None:
        print(f"  IRR:               {result.irr:.1%}")
    print(f"  MOIC:              {result.moic:.2f}x")

    return result


def run_all(assumptions_dir: Path):
    """Run all scenarios and compare."""
    scenarios = ["conservative", "base", "aggressive"]

    print("\n" + "=" * 60)
    print("RUNNING ALL SCENARIOS")
    print("=" * 60)

    results = run_all_scenarios(scenarios, assumptions_dir)

    # Print individual results
    for scenario_id in scenarios:
        result = results[scenario_id]
        print(f"\n{scenario_id.upper()}")
        print("-" * 40)
        print(f"  Revenue:  EUR {result.total_revenue:,.0f}")
        print(f"  EBITDA:   EUR {result.final_ebitda:,.0f}")
        print(f"  EV:       EUR {result.enterprise_value:,.0f}")
        if result.irr is not None:
            print(f"  IRR:      {result.irr:.1%}")
        print(f"  MOIC:     {result.moic:.2f}x")

    # Compare
    print("\n" + "=" * 60)
    print("COMPARISON vs BASE")
    print("=" * 60)

    matrix = compare_scenarios(results, "base")
    for metric in ["total_revenue", "enterprise_value", "moic"]:
        print(f"\n{metric}:")
        for scenario_id in scenarios:
            value = matrix.metrics.get(metric, {}).get(scenario_id, 0)
            variance = matrix.variances.get(metric, {}).get(scenario_id, 0)
            print(f"  {scenario_id:12}: {value:>15,.0f}  ({variance:+.1%})")

    # Validate ordering
    print("\n" + "=" * 60)
    print("ORDERING VALIDATION")
    print("=" * 60)

    ordering_errors = validate_scenario_ordering(results)
    if ordering_errors:
        print("\nFAILED - Ordering violations:")
        for error in ordering_errors:
            print(f"  - {error}")
    else:
        print("\nPASSED - Scenario ordering is correct")

    return results


def run_validation(assumptions_dir: Path):
    """Run validation and generate report."""
    print("\n" + "=" * 60)
    print("RUNNING VALIDATION")
    print("=" * 60)

    result = run_scenario("base", assumptions_dir)

    report = generate_validation_report(
        scenario_id="base",
        revenue_output=result.revenue,
        cogs_output=result.cogs,
        opex_output=result.opex,
        wc_output=result.working_capital,
        cashflow_output=result.cashflow,
        valuation_output=result.valuation
    )

    print(format_report(report))


def build_from_workbook(workbook: Path, output: Path):
    """Build base assumptions YAML from workbook inputs."""
    assumptions = build_assumptions_from_workbook(workbook)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as handle:
        yaml.safe_dump(assumptions, handle, sort_keys=False)
    print(f"Wrote workbook-based assumptions to: {output}")


def reconcile_workbook(workbook: Path):
    """Run engine using workbook-derived assumptions and print annual variances."""
    assumptions = build_assumptions_from_workbook(workbook)

    revenue = revenue_engine(copy.deepcopy(assumptions))
    cogs = cogs_engine(copy.deepcopy(assumptions), revenue.units_kg)
    opex = opex_engine(copy.deepcopy(assumptions), revenue)
    wc = working_capital_engine(copy.deepcopy(assumptions), revenue.revenue_total, cogs.total_cogs)
    cashflow = cashflow_engine(
        copy.deepcopy(assumptions),
        revenue.revenue_total,
        cogs.total_cogs,
        opex.total_opex,
        wc.delta_wc,
    )
    valuation = valuation_engine(
        copy.deepcopy(assumptions),
        cashflow.free_cf,
        cashflow.ebitda,
        cashflow.cash_balance,
        cashflow.debt_balance,
        revenue_total=revenue.revenue_total,
        cogs_total=cogs.total_cogs,
        variable_cogs_total=cogs.variable_cogs_total,
        opex_total=opex.total_opex,
        variable_opex_total=opex.total_variable,
        units_kg_total={
            month: sum(kg for (m, _, _), kg in revenue.units_kg.items() if m == month)
            for month in revenue.revenue_total.keys()
        },
    )

    variances = reconcile_engine_to_workbook(
        workbook,
        revenue_total_monthly=revenue.revenue_total,
        cogs_total_monthly=cogs.total_cogs,
        opex_total_monthly=opex.total_opex,
        ebitda_monthly=cashflow.ebitda,
        ending_cash_monthly=cashflow.cash_balance,
        enterprise_value=valuation.enterprise_value,
    )

    print(json.dumps(variances, indent=2))


def main():
    parser = argparse.ArgumentParser(description="ReSemis EPM Engine")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run scenario(s)")
    run_parser.add_argument("--scenario", "-s", help="Scenario ID to run")
    run_parser.add_argument("--all", "-a", action="store_true", help="Run all scenarios")
    run_parser.add_argument("--dir", "-d", default="assumptions",
                           help="Assumptions directory")

    # Validate command
    val_parser = subparsers.add_parser("validate", help="Run validation")
    val_parser.add_argument("--dir", "-d", default="assumptions",
                           help="Assumptions directory")

    # Workbook -> assumptions command
    build_parser = subparsers.add_parser(
        "build-assumptions-from-workbook",
        help="Generate assumptions YAML from audited workbook V8"
    )
    build_parser.add_argument("--xlsx", required=True, help="Path to workbook file")
    build_parser.add_argument(
        "--output",
        default="assumptions/base.yaml",
        help="Output assumptions YAML path",
    )

    # Workbook reconciliation command
    rec_parser = subparsers.add_parser(
        "reconcile-workbook",
        help="Run model from workbook-derived assumptions and print variances"
    )
    rec_parser.add_argument("--xlsx", required=True, help="Path to workbook file")

    args = parser.parse_args()

    assumptions_dir = Path(args.dir if hasattr(args, 'dir') else "assumptions")

    if args.command == "run":
        if args.all:
            run_all(assumptions_dir)
        elif args.scenario:
            run_single_scenario(args.scenario, assumptions_dir)
        else:
            # Default: run base
            run_single_scenario("base", assumptions_dir)
    elif args.command == "validate":
        run_validation(assumptions_dir)
    elif args.command == "build-assumptions-from-workbook":
        build_from_workbook(Path(args.xlsx), Path(args.output))
    elif args.command == "reconcile-workbook":
        reconcile_workbook(Path(args.xlsx))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
