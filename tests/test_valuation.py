# =============================================================================
# RESEMIS EPM ENGINE - VALUATION ENGINE TESTS
# =============================================================================

import pytest
import sys
import os
import copy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.valuation import (
    ValuationParams, calculate_discount_factors,
    calculate_terminal_value_gordon, calculate_terminal_value_multiple,
    calculate_irr, calculate_moic, calculate_pv_fcf,
    valuation_engine
)


class TestDiscountFactors:
    """Tests for discount factor calculation."""

    def test_discount_factors_decrease(self):
        """Discount factors should decrease over time."""
        months = ["2026-01", "2026-06", "2026-12"]
        df = calculate_discount_factors(months, 0.10)
        assert df["2026-01"] > df["2026-06"] > df["2026-12"]

    def test_higher_rate_lower_df(self):
        """Higher discount rate should give lower discount factors."""
        months = ["2026-06"]
        df_low = calculate_discount_factors(months, 0.05)
        df_high = calculate_discount_factors(months, 0.20)
        assert df_low["2026-06"] > df_high["2026-06"]


class TestTerminalValue:
    """Tests for terminal value calculations."""

    def test_gordon_growth(self):
        """Test Gordon Growth terminal value."""
        # TV = FCF * (1 + g) / (r - g) = 100 * 1.02 / (0.10 - 0.02) = 1275
        tv = calculate_terminal_value_gordon(100, 0.10, 0.02)
        assert abs(tv - 1275) < 0.01

    def test_gordon_invalid_rates(self):
        """Gordon should fail if discount <= growth."""
        with pytest.raises(ValueError):
            calculate_terminal_value_gordon(100, 0.02, 0.05)

    def test_exit_multiple(self):
        """Test exit multiple terminal value."""
        tv = calculate_terminal_value_multiple(1000, 10)
        assert tv == 10000


class TestIRR:
    """Tests for IRR calculation."""

    def test_simple_irr(self):
        """Test simple IRR calculation."""
        # -100 at t=0, +121 at t=12 months (annual return ~21%)
        cf = [-100] + [0] * 11 + [121]
        irr = calculate_irr(cf)
        assert irr is not None
        assert abs(irr - 0.21) < 0.05  # ~21% annual

    def test_no_irr_all_positive(self):
        """No IRR if all cash flows are positive."""
        cf = [100, 100, 100]
        irr = calculate_irr(cf)
        assert irr is None

    def test_no_irr_all_negative(self):
        """No IRR if all cash flows are negative."""
        cf = [-100, -100, -100]
        irr = calculate_irr(cf)
        assert irr is None


class TestMOIC:
    """Tests for MOIC calculation."""

    def test_moic_formula(self):
        """MOIC = Proceeds / Invested."""
        moic = calculate_moic(100, 250)
        assert moic == 2.5

    def test_moic_zero_invested(self):
        """MOIC should be 0 if nothing invested."""
        moic = calculate_moic(0, 100)
        assert moic == 0.0


class TestPVFCF:
    """Tests for PV of FCF calculation."""

    def test_pv_fcf(self):
        """PV = FCF * discount_factor."""
        fcf = {"2026-06": 1000}
        df = {"2026-06": 0.9}
        pv_fcf, total = calculate_pv_fcf(fcf, df)
        assert pv_fcf["2026-06"] == 900
        assert total == 900


class TestValuationEngine:
    """Integration tests for valuation engine."""

    def test_zero_fcf(self):
        """Zero FCF should give zero value (except terminal)."""
        assumptions = {
            "time_horizon": {"start_month": "2026-06", "end_month": "2026-06"},
            "valuation": {
                "discount_rate": 0.15,
                "terminal_growth_rate": 0.02,
                "terminal_method": "gordon",
                "exit_year": 2026,
                "equity": {"ownership_pct": 1.0, "invested": {"by_month": {}}}
            }
        }
        output = valuation_engine(
            assumptions,
            free_cf={"2026-06": 0},
            ebitda={"2026-06": 0},
            cash_balance={"2026-06": 0},
            debt_balance={"2026-06": 0}
        )
        assert output.total_pv_fcf == 0
        assert output.terminal_value == 0

    def test_higher_discount_lower_ev(self):
        """Higher discount rate should give lower EV."""
        base_assumptions = {
            "time_horizon": {"start_month": "2026-06", "end_month": "2026-06"},
            "valuation": {
                "terminal_growth_rate": 0.02,
                "terminal_method": "gordon",
                "exit_year": 2026,
                "equity": {"ownership_pct": 1.0, "invested": {"by_month": {}}}
            }
        }
        fcf = {"2026-06": 1000}
        ebitda = {"2026-06": 2000}
        cash = {"2026-06": 100}
        debt = {"2026-06": 0}

        assumptions_low = copy.deepcopy(base_assumptions)
        assumptions_low["valuation"]["discount_rate"] = 0.10
        assumptions_high = copy.deepcopy(base_assumptions)
        assumptions_high["valuation"]["discount_rate"] = 0.20

        output_low = valuation_engine(assumptions_low, fcf, ebitda, cash, debt)
        output_high = valuation_engine(assumptions_high, fcf, ebitda, cash, debt)

        assert output_low.enterprise_value > output_high.enterprise_value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
