# =============================================================================
# RESEMIS EPM ENGINE - VALIDATION REPORT GENERATOR
# =============================================================================
# Generates comprehensive validation reports for model outputs.
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    message: str = ""
    variance: Optional[float] = None


@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str = ""
    scenario_id: str = ""

    # Test results by category
    unit_tests: Dict[str, List[TestResult]] = field(default_factory=dict)
    integration_tests: List[TestResult] = field(default_factory=list)
    reconciliation_tests: List[TestResult] = field(default_factory=list)

    # Summary
    total_passed: int = 0
    total_failed: int = 0
    overall_passed: bool = False

    # Errors and warnings
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_revenue_engine(revenue_output) -> List[TestResult]:
    """Validate revenue engine output."""
    results = []

    # Check for errors
    if revenue_output.errors:
        results.append(TestResult(
            "no_errors", False,
            f"Revenue engine has errors: {revenue_output.errors}"
        ))
    else:
        results.append(TestResult("no_errors", True))

    # Check revenue is non-negative
    all_positive = all(v >= 0 for v in revenue_output.revenue_total.values())
    results.append(TestResult(
        "non_negative_revenue", all_positive,
        "" if all_positive else "Found negative revenue"
    ))

    # Check units are non-negative
    all_units_positive = all(v >= 0 for v in revenue_output.units_kg.values())
    results.append(TestResult(
        "non_negative_units", all_units_positive,
        "" if all_units_positive else "Found negative units"
    ))

    return results


def validate_cogs_engine(cogs_output) -> List[TestResult]:
    """Validate COGS engine output."""
    results = []

    # Check for errors
    if cogs_output.errors:
        results.append(TestResult(
            "no_errors", False,
            f"COGS engine has errors: {cogs_output.errors}"
        ))
    else:
        results.append(TestResult("no_errors", True))

    # Check COGS is non-negative
    all_positive = all(v >= 0 for v in cogs_output.total_cogs.values())
    results.append(TestResult(
        "non_negative_cogs", all_positive,
        "" if all_positive else "Found negative COGS"
    ))

    # Check total = variable + fixed
    tolerance = 0.01
    for month, total in cogs_output.total_cogs.items():
        var = cogs_output.variable_cogs_total.get(month, 0)
        fixed = cogs_output.fixed_cogs.get(month, 0)
        if abs(total - (var + fixed)) > tolerance:
            results.append(TestResult(
                "cogs_sum_check", False,
                f"Total != Variable + Fixed at {month}"
            ))
            break
    else:
        results.append(TestResult("cogs_sum_check", True))

    return results


def validate_cashflow_engine(cashflow_output, revenue_total, cogs_total, opex_total) -> List[TestResult]:
    """Validate cashflow engine output."""
    results = []

    # Check EBITDA formula
    tolerance = 0.01
    for month, ebitda in cashflow_output.ebitda.items():
        expected = revenue_total.get(month, 0) - cogs_total.get(month, 0) - opex_total.get(month, 0)
        if abs(ebitda - expected) > tolerance:
            results.append(TestResult(
                "ebitda_formula", False,
                f"EBITDA mismatch at {month}"
            ))
            break
    else:
        results.append(TestResult("ebitda_formula", True))

    return results


def validate_valuation_engine(valuation_output) -> List[TestResult]:
    """Validate valuation engine output."""
    results = []

    # Check for errors
    if valuation_output.errors:
        results.append(TestResult(
            "no_errors", False,
            f"Valuation engine has errors: {valuation_output.errors}"
        ))
    else:
        results.append(TestResult("no_errors", True))

    # Check EV is reasonable (not negative unless truly distressed)
    results.append(TestResult(
        "ev_calculated", valuation_output.enterprise_value is not None,
        "" if valuation_output.enterprise_value is not None else "EV not calculated"
    ))

    return results


def reconcile_with_excel(
    engine_results: Dict[str, float],
    excel_data: Dict[str, float],
    metric_name: str,
    tolerance: float = 0.001
) -> TestResult:
    """
    Reconcile engine output with Excel baseline.

    Args:
        engine_results: Dict of metric values by month
        excel_data: Dict of Excel values by month
        metric_name: Name of the metric being tested
        tolerance: Maximum allowed variance (default 0.1%)

    Returns:
        TestResult with pass/fail and variance
    """
    max_variance = 0.0
    failed_months = []

    for month, engine_val in engine_results.items():
        excel_val = excel_data.get(month)
        if excel_val is None:
            continue

        if abs(excel_val) < 0.01:  # Avoid division by zero
            variance = abs(engine_val - excel_val)
        else:
            variance = abs(engine_val - excel_val) / abs(excel_val)

        max_variance = max(max_variance, variance)
        if variance > tolerance:
            failed_months.append((month, variance))

    passed = len(failed_months) == 0
    message = "" if passed else f"Failed months: {failed_months[:3]}"

    return TestResult(
        name=f"reconcile_{metric_name}",
        passed=passed,
        message=message,
        variance=max_variance
    )


def generate_validation_report(
    scenario_id: str,
    revenue_output,
    cogs_output,
    opex_output,
    wc_output,
    cashflow_output,
    valuation_output,
    excel_data: Optional[Dict] = None
) -> ValidationReport:
    """
    Generate comprehensive validation report.

    Args:
        scenario_id: Scenario identifier
        *_output: Engine outputs
        excel_data: Optional Excel baseline for reconciliation

    Returns:
        ValidationReport with all test results
    """
    report = ValidationReport(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        scenario_id=scenario_id
    )

    # Unit tests by engine
    report.unit_tests["Revenue Engine"] = validate_revenue_engine(revenue_output)
    report.unit_tests["COGS Engine"] = validate_cogs_engine(cogs_output)
    report.unit_tests["Cashflow Engine"] = validate_cashflow_engine(
        cashflow_output,
        revenue_output.revenue_total,
        cogs_output.total_cogs,
        opex_output.total_opex
    )
    report.unit_tests["Valuation Engine"] = validate_valuation_engine(valuation_output)

    # Excel reconciliation (if data provided)
    if excel_data:
        if "revenue_total" in excel_data:
            report.reconciliation_tests.append(
                reconcile_with_excel(
                    revenue_output.revenue_total,
                    excel_data["revenue_total"],
                    "revenue"
                )
            )
        if "total_cogs" in excel_data:
            report.reconciliation_tests.append(
                reconcile_with_excel(
                    cogs_output.total_cogs,
                    excel_data["total_cogs"],
                    "cogs"
                )
            )
        if "ebitda" in excel_data:
            report.reconciliation_tests.append(
                reconcile_with_excel(
                    cashflow_output.ebitda,
                    excel_data["ebitda"],
                    "ebitda"
                )
            )

    # Calculate summary
    all_tests = []
    for tests in report.unit_tests.values():
        all_tests.extend(tests)
    all_tests.extend(report.integration_tests)
    all_tests.extend(report.reconciliation_tests)

    report.total_passed = sum(1 for t in all_tests if t.passed)
    report.total_failed = sum(1 for t in all_tests if not t.passed)
    report.overall_passed = report.total_failed == 0

    return report


def format_report(report: ValidationReport) -> str:
    """Format validation report as text."""
    lines = [
        "=" * 60,
        "VALIDATION REPORT",
        "=" * 60,
        f"Date: {report.timestamp}",
        f"Scenario: {report.scenario_id}",
        "",
        "UNIT TESTS",
        "-" * 40
    ]

    for engine, tests in report.unit_tests.items():
        passed = sum(1 for t in tests if t.passed)
        total = len(tests)
        status = "PASSED" if passed == total else "FAILED"
        lines.append(f"{engine}: {passed}/{total} {status}")

    if report.reconciliation_tests:
        lines.extend([
            "",
            "EXCEL RECONCILIATION",
            "-" * 40
        ])
        for test in report.reconciliation_tests:
            status = "PASSED" if test.passed else "FAILED"
            variance_str = f"(variance: {test.variance:.2%})" if test.variance else ""
            lines.append(f"{test.name}: {status} {variance_str}")

    lines.extend([
        "",
        "=" * 60,
        f"OVERALL: {'PASSED' if report.overall_passed else 'FAILED'}",
        f"Total: {report.total_passed} passed, {report.total_failed} failed",
        "=" * 60
    ])

    return "\n".join(lines)


# =============================================================================
# END OF VALIDATION REPORT GENERATOR
# =============================================================================
