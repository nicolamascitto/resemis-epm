# =============================================================================
# RESEMIS EPM ENGINE - SCENARIO ENGINE TESTS
# =============================================================================

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.scenario import (
    deep_merge, load_scenario_assumptions, validate_assumptions,
    compare_scenarios, validate_scenario_ordering,
    ScenarioResult, ComparisonMatrix
)


class TestDeepMerge:
    """Tests for deep merge function."""

    def test_simple_override(self):
        """Simple values should be overridden."""
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        result = deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"] == 3

    def test_nested_merge(self):
        """Nested dicts should be merged recursively."""
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"y": 3}}
        result = deep_merge(base, override)
        assert result["a"]["x"] == 1
        assert result["a"]["y"] == 3

    def test_new_keys(self):
        """New keys in override should be added."""
        base = {"a": 1}
        override = {"b": 2}
        result = deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"] == 2

    def test_immutability(self):
        """Merge should not modify original dicts."""
        base = {"a": {"x": 1}}
        override = {"a": {"x": 2}}
        result = deep_merge(base, override)
        assert base["a"]["x"] == 1  # Original unchanged
        assert result["a"]["x"] == 2


class TestValidateAssumptions:
    """Tests for assumption validation."""

    def test_valid_assumptions(self):
        """Valid assumptions should pass."""
        assumptions = {
            "time_horizon": {},
            "products": [],
            "markets": [],
            "volume": {},
            "pricing": {},
            "bom": {},
            "valuation": {"discount_rate": 0.15, "terminal_growth_rate": 0.02}
        }
        errors = validate_assumptions(assumptions)
        assert len(errors) == 0

    def test_missing_section(self):
        """Missing required section should fail."""
        assumptions = {"time_horizon": {}}
        errors = validate_assumptions(assumptions)
        assert any("Missing required section" in e for e in errors)

    def test_invalid_rates(self):
        """discount_rate <= terminal_growth should fail."""
        assumptions = {
            "time_horizon": {}, "products": [], "markets": [],
            "volume": {}, "pricing": {}, "bom": {},
            "valuation": {"discount_rate": 0.02, "terminal_growth_rate": 0.05}
        }
        errors = validate_assumptions(assumptions)
        assert any("discount_rate" in e for e in errors)


class TestScenarioComparison:
    """Tests for scenario comparison."""

    def test_comparison_matrix(self):
        """Test comparison matrix generation."""
        results = {
            "base": ScenarioResult(scenario_id="base", total_revenue=1000),
            "aggressive": ScenarioResult(scenario_id="aggressive", total_revenue=1200)
        }
        matrix = compare_scenarios(results, "base")
        assert "base" in matrix.scenarios
        assert matrix.metrics["total_revenue"]["base"] == 1000
        assert matrix.metrics["total_revenue"]["aggressive"] == 1200

    def test_variance_calculation(self):
        """Test variance vs base calculation."""
        results = {
            "base": ScenarioResult(scenario_id="base", total_revenue=1000),
            "aggressive": ScenarioResult(scenario_id="aggressive", total_revenue=1200)
        }
        matrix = compare_scenarios(results, "base")
        # Variance = (1200 - 1000) / 1000 = 0.20
        assert abs(matrix.variances["total_revenue"]["aggressive"] - 0.20) < 0.01


class TestScenarioOrdering:
    """Tests for scenario ordering validation."""

    def test_valid_ordering(self):
        """Valid ordering should pass."""
        results = {
            "conservative": ScenarioResult(scenario_id="conservative",
                                           total_revenue=800, final_ebitda=100,
                                           cumulative_fcf=50, enterprise_value=500, moic=1.5),
            "base": ScenarioResult(scenario_id="base",
                                   total_revenue=1000, final_ebitda=150,
                                   cumulative_fcf=100, enterprise_value=700, moic=2.0),
            "aggressive": ScenarioResult(scenario_id="aggressive",
                                         total_revenue=1200, final_ebitda=200,
                                         cumulative_fcf=150, enterprise_value=900, moic=2.5)
        }
        errors = validate_scenario_ordering(results)
        assert len(errors) == 0

    def test_invalid_ordering(self):
        """Invalid ordering should fail."""
        results = {
            "conservative": ScenarioResult(scenario_id="conservative",
                                           total_revenue=1500,  # Higher than base!
                                           final_ebitda=100, cumulative_fcf=50,
                                           enterprise_value=500, moic=1.5),
            "base": ScenarioResult(scenario_id="base",
                                   total_revenue=1000, final_ebitda=150,
                                   cumulative_fcf=100, enterprise_value=700, moic=2.0),
            "aggressive": ScenarioResult(scenario_id="aggressive",
                                         total_revenue=1200, final_ebitda=200,
                                         cumulative_fcf=150, enterprise_value=900, moic=2.5)
        }
        errors = validate_scenario_ordering(results)
        assert len(errors) > 0
        assert any("total_revenue" in e for e in errors)


class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_same_input_same_output(self):
        """Same assumptions should produce same merge result."""
        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"d": 3}}

        result1 = deep_merge(base, override)
        result2 = deep_merge(base, override)

        assert result1 == result2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
