# =============================================================================
# RESEMIS EPM ENGINE - INTEGRATION TESTS
# =============================================================================
# Tests for full pipeline execution and scenario behavior.
# =============================================================================

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.revenue import revenue_engine
from models.cogs import cogs_engine
from models.opex import opex_engine
from models.working_capital import working_capital_engine
from models.cashflow import cashflow_engine
from models.valuation import valuation_engine


class TestFullPipeline:
    """Tests for full pipeline execution."""

    def test_full_pipeline_executes(self, base_assumptions):
        """Full pipeline should execute without errors."""
        # Revenue
        revenue = revenue_engine(base_assumptions)
        assert revenue is not None
        assert len(revenue.errors) == 0

        # COGS
        cogs = cogs_engine(base_assumptions, revenue.units_kg)
        assert cogs is not None
        assert len(cogs.errors) == 0

        # OpEx
        opex = opex_engine(base_assumptions, revenue)
        assert opex is not None
        assert len(opex.errors) == 0

        # Working Capital
        wc = working_capital_engine(
            base_assumptions,
            revenue.revenue_total,
            cogs.total_cogs
        )
        assert wc is not None
        assert len(wc.errors) == 0

        # Cashflow
        cf = cashflow_engine(
            base_assumptions,
            revenue.revenue_total,
            cogs.total_cogs,
            opex.total_opex,
            wc.delta_wc
        )
        assert cf is not None

        # Valuation
        val = valuation_engine(
            base_assumptions,
            cf.free_cf,
            cf.ebitda,
            cf.cash_balance,
            cf.debt_balance
        )
        assert val is not None

    def test_pipeline_produces_outputs(self, base_assumptions):
        """Pipeline should produce meaningful outputs."""
        revenue = revenue_engine(base_assumptions)
        cogs = cogs_engine(base_assumptions, revenue.units_kg)

        # Check revenue was calculated
        total_rev = sum(revenue.revenue_total.values())
        assert total_rev > 0, "Should have positive revenue"

        # Check COGS was calculated
        total_cogs = sum(cogs.total_cogs.values())
        assert total_cogs > 0, "Should have positive COGS"


class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_same_input_same_output(self, base_assumptions):
        """Same assumptions should produce identical results."""
        result1 = revenue_engine(base_assumptions)
        result2 = revenue_engine(base_assumptions)

        assert result1.revenue_total == result2.revenue_total
        assert result1.units_kg == result2.units_kg

    def test_isolation_between_runs(self, base_assumptions):
        """Multiple runs should not affect each other."""
        import copy
        assumptions1 = copy.deepcopy(base_assumptions)
        assumptions2 = copy.deepcopy(base_assumptions)

        # Modify assumptions2
        assumptions2["pricing"]["list_price"]["by_product"]["biocore"]["base_price"] = 20.0

        result1 = revenue_engine(assumptions1)
        result2 = revenue_engine(assumptions2)

        # Results should be different
        total1 = sum(result1.revenue_total.values())
        total2 = sum(result2.revenue_total.values())
        assert total2 > total1, "Higher price should give higher revenue"


class TestNoScenarioBranching:
    """Tests to verify no scenario-specific branching in code."""

    def test_no_hardcoded_scenarios(self, base_assumptions):
        """Engine should work with any scenario, not just predefined ones."""
        import copy

        # Create a completely custom scenario
        custom = copy.deepcopy(base_assumptions)
        custom["scenario_id"] = "custom_test_scenario"

        # Should still work
        result = revenue_engine(custom)
        assert result is not None
        assert len(result.errors) == 0


class TestDataFlowIntegrity:
    """Tests for data flow integrity between engines."""

    def test_revenue_units_to_cogs(self, base_assumptions):
        """COGS consumption should match revenue units."""
        revenue = revenue_engine(base_assumptions)
        cogs = cogs_engine(base_assumptions, revenue.units_kg)

        # Total units should be consistent
        total_units_rev = sum(revenue.units_kg.values())

        # COGS consumption should be based on these units
        # (consumption = units * BOM qty, so should be proportional)
        assert len(cogs.consumption) > 0 if total_units_rev > 0 else True

    def test_revenue_to_working_capital(self, base_assumptions):
        """AR should be linked to revenue."""
        revenue = revenue_engine(base_assumptions)
        cogs = cogs_engine(base_assumptions, revenue.units_kg)
        wc = working_capital_engine(
            base_assumptions,
            revenue.revenue_total,
            cogs.total_cogs
        )

        # If revenue > 0, AR should be > 0
        total_rev = sum(revenue.revenue_total.values())
        total_ar = sum(wc.ar.values())

        if total_rev > 0:
            assert total_ar > 0, "AR should be positive when revenue is positive"


class TestConstraintEnforcement:
    """Tests for constraint enforcement."""

    def test_capacity_constraint_applied(self, base_assumptions):
        """Capacity constraint should limit volume."""
        import copy

        # Create unconstrained scenario
        unconstrained = copy.deepcopy(base_assumptions)
        unconstrained["volume"]["capacity"]["enabled"] = False

        # Create constrained scenario with very low capacity
        constrained = copy.deepcopy(base_assumptions)
        constrained["volume"]["capacity"]["enabled"] = True
        constrained["volume"]["capacity"]["by_month"] = {"2026-06": 10}  # Very low

        result_unconstrained = revenue_engine(unconstrained)
        result_constrained = revenue_engine(constrained)

        unconstrained_vol = sum(result_unconstrained.sellable_kg.values())
        constrained_vol = sum(result_constrained.sellable_kg.values())

        assert constrained_vol <= unconstrained_vol, "Capacity should limit volume"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
