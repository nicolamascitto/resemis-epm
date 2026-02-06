# =============================================================================
# RESEMIS EPM ENGINE - OPEX ENGINE TESTS
# =============================================================================

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.opex import (
    FixedOpExCategory, VariableOpExDriver, SMParams,
    calculate_fixed_opex, aggregate_fixed_opex,
    calculate_variable_opex, calculate_sm_opex,
    opex_engine, validate_opex_output
)


class TestFixedOpEx:
    """Tests for fixed OpEx calculation."""

    def test_basic_fixed_opex(self):
        """Fixed OpEx = base * ramp."""
        categories = [
            FixedOpExCategory("mgmt", 10000, {"2026-01": 1.0})
        ]
        result = calculate_fixed_opex(["2026-06"], categories)
        assert result[("2026-06", "mgmt")] == 10000

    def test_ramp_factor(self):
        """Ramp should scale fixed OpEx."""
        categories = [
            FixedOpExCategory("mgmt", 10000, {"2026-01": 1.0, "2027-01": 1.5})
        ]
        result = calculate_fixed_opex(["2026-06", "2027-06"], categories)
        assert result[("2026-06", "mgmt")] == 10000
        assert result[("2027-06", "mgmt")] == 15000

    def test_multiple_categories(self):
        """Multiple categories should be independent."""
        categories = [
            FixedOpExCategory("mgmt", 10000, {}),
            FixedOpExCategory("it", 5000, {})
        ]
        result = calculate_fixed_opex(["2026-06"], categories)
        assert result[("2026-06", "mgmt")] == 10000
        assert result[("2026-06", "it")] == 5000


class TestVariableOpEx:
    """Tests for variable OpEx calculation."""

    def test_zero_activity(self):
        """Zero activity should give zero variable OpEx."""
        drivers = [VariableOpExDriver("units_kg_total", 0.10)]
        activity = {("2026-06", "units_kg_total"): 0}
        result = calculate_variable_opex(activity, drivers)
        assert result.get(("2026-06", "units_kg_total"), 0) == 0

    def test_activity_scaling(self):
        """Variable OpEx should scale with activity."""
        drivers = [VariableOpExDriver("units_kg_total", 0.10)]
        activity_1 = {("2026-06", "units_kg_total"): 1000}
        activity_2 = {("2026-06", "units_kg_total"): 2000}

        result_1 = calculate_variable_opex(activity_1, drivers)
        result_2 = calculate_variable_opex(activity_2, drivers)

        assert result_1[("2026-06", "units_kg_total")] == 100
        assert result_2[("2026-06", "units_kg_total")] == 200


class TestSMOpEx:
    """Tests for S&M OpEx calculation."""

    def test_basic_sm(self):
        """S&M fixed with ramp."""
        sm_params = SMParams(
            fixed_base=20000,
            ramp_factors={"2026-01": 1.0},
            cac_by_market={}
        )
        sm_fixed, sm_cac = calculate_sm_opex(
            ["2026-06"], [], sm_params
        )
        assert sm_fixed["2026-06"] == 20000

    def test_cac_on_activation(self):
        """CAC charged on market activation."""
        sm_params = SMParams(
            fixed_base=0,
            ramp_factors={},
            cac_by_market={"italy": 50000}
        )
        markets = [{"market_id": "italy", "activation_month": "2026-06"}]
        sm_fixed, sm_cac = calculate_sm_opex(
            ["2026-06", "2026-07"], markets, sm_params
        )
        assert sm_cac[("2026-06", "italy")] == 50000
        assert ("2026-07", "italy") not in sm_cac


class TestOpExEngine:
    """Integration tests for OpEx engine."""

    def get_test_assumptions(self):
        return {
            "time_horizon": {"start_month": "2026-06", "end_month": "2026-06"},
            "markets": [{"market_id": "italy", "activation_month": "2026-06"}],
            "opex": {
                "fixed": {
                    "by_category": {
                        "mgmt": {"base_monthly": 10000, "ramp": {"by_month": {}}}
                    }
                },
                "variable": {"by_driver": {}},
                "sales_marketing": {
                    "fixed_base": 5000,
                    "ramp": {"by_month": {}},
                    "cac": {"by_market": {"italy": 50000}}
                }
            }
        }

    def get_mock_revenue_output(self):
        from dataclasses import dataclass, field
        from typing import Dict, Tuple

        @dataclass
        class MockRevenueOutput:
            units_kg: Dict[Tuple[str, str, str], float] = field(default_factory=dict)
            revenue: Dict[Tuple[str, str, str], float] = field(default_factory=dict)

        return MockRevenueOutput(
            units_kg={("2026-06", "biocore", "italy"): 100},
            revenue={("2026-06", "biocore", "italy"): 1000}
        )

    def test_full_opex_calculation(self):
        """Test full OpEx calculation."""
        assumptions = self.get_test_assumptions()
        revenue_output = self.get_mock_revenue_output()

        output = opex_engine(assumptions, revenue_output)

        # Fixed OpEx
        assert output.total_fixed["2026-06"] == 10000

        # S&M (fixed + CAC)
        assert output.total_sm["2026-06"] == 55000  # 5000 + 50000 CAC

        # Total
        assert output.total_opex["2026-06"] == 65000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
