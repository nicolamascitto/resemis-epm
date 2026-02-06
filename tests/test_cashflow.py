# =============================================================================
# RESEMIS EPM ENGINE - CASHFLOW ENGINE TESTS
# =============================================================================

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.cashflow import (
    CapexSchedule, FundingSchedule,
    calculate_ebitda, calculate_operating_cf, calculate_capex,
    calculate_free_cf, cashflow_engine
)


class TestEBITDA:
    """Tests for EBITDA calculation."""

    def test_ebitda_formula(self):
        """EBITDA = Revenue - COGS - OpEx."""
        revenue = {"2026-06": 10000}
        cogs = {"2026-06": 4000}
        opex = {"2026-06": 3000}
        ebitda = calculate_ebitda(revenue, cogs, opex)
        assert ebitda["2026-06"] == 3000

    def test_zero_revenue(self):
        """Zero revenue -> EBITDA = -OpEx - COGS."""
        revenue = {"2026-06": 0}
        cogs = {"2026-06": 0}
        opex = {"2026-06": 5000}
        ebitda = calculate_ebitda(revenue, cogs, opex)
        assert ebitda["2026-06"] == -5000


class TestOperatingCF:
    """Tests for Operating Cash Flow."""

    def test_ocf_formula(self):
        """Operating CF = EBITDA - Delta WC."""
        ebitda = {"2026-06": 5000}
        delta_wc = {"2026-06": 1000}
        ocf = calculate_operating_cf(ebitda, delta_wc)
        assert ocf["2026-06"] == 4000

    def test_wc_increase_reduces_cf(self):
        """WC increase (positive delta) reduces operating CF."""
        ebitda = {"2026-06": 5000}
        delta_wc_low = {"2026-06": 500}
        delta_wc_high = {"2026-06": 2000}

        ocf_low = calculate_operating_cf(ebitda, delta_wc_low)
        ocf_high = calculate_operating_cf(ebitda, delta_wc_high)

        assert ocf_low["2026-06"] > ocf_high["2026-06"]


class TestCapex:
    """Tests for Capex calculation."""

    def test_base_capex(self):
        """Base monthly capex."""
        schedule = CapexSchedule(base_monthly=1000, milestones={})
        capex = calculate_capex(["2026-06", "2026-07"], schedule)
        assert capex["2026-06"] == 1000
        assert capex["2026-07"] == 1000

    def test_milestone_capex(self):
        """Milestone one-off capex."""
        schedule = CapexSchedule(base_monthly=1000, milestones={"2026-06": 50000})
        capex = calculate_capex(["2026-06", "2026-07"], schedule)
        assert capex["2026-06"] == 51000  # 1000 + 50000
        assert capex["2026-07"] == 1000  # base only


class TestFreeCF:
    """Tests for Free Cash Flow."""

    def test_fcf_formula(self):
        """Free CF = Operating CF - Capex."""
        ocf = {"2026-06": 5000}
        capex = {"2026-06": 2000}
        fcf = calculate_free_cf(ocf, capex)
        assert fcf["2026-06"] == 3000

    def test_capex_shock(self):
        """High capex should reduce FCF."""
        ocf = {"2026-06": 5000}
        capex_low = {"2026-06": 1000}
        capex_high = {"2026-06": 10000}

        fcf_low = calculate_free_cf(ocf, capex_low)
        fcf_high = calculate_free_cf(ocf, capex_high)

        assert fcf_low["2026-06"] > fcf_high["2026-06"]
        assert fcf_high["2026-06"] < 0  # Negative FCF from high capex


class TestCashflowEngine:
    """Integration tests for cashflow engine."""

    def test_full_calculation(self):
        """Test full cashflow calculation."""
        assumptions = {
            "time_horizon": {"start_month": "2026-06", "end_month": "2026-07"},
            "capex": {"base_monthly": 1000, "milestones": {"by_month": {}}},
            "funding": {
                "initial_cash": 100000,
                "equity": {"by_month": {}},
                "debt": {"interest_rate": 0.05, "by_month": {}}
            }
        }
        revenue = {"2026-06": 10000, "2026-07": 12000}
        cogs = {"2026-06": 4000, "2026-07": 5000}
        opex = {"2026-06": 3000, "2026-07": 3500}
        delta_wc = {"2026-06": 500, "2026-07": 200}

        output = cashflow_engine(assumptions, revenue, cogs, opex, delta_wc)

        # EBITDA
        assert output.ebitda["2026-06"] == 3000  # 10000 - 4000 - 3000
        assert output.ebitda["2026-07"] == 3500  # 12000 - 5000 - 3500

        # Operating CF
        assert output.operating_cf["2026-06"] == 2500  # 3000 - 500
        assert output.operating_cf["2026-07"] == 3300  # 3500 - 200

        # Free CF
        assert output.free_cf["2026-06"] == 1500  # 2500 - 1000
        assert output.free_cf["2026-07"] == 2300  # 3300 - 1000

    def test_funding_injection(self):
        """Equity injection should increase cash balance."""
        assumptions = {
            "time_horizon": {"start_month": "2026-06", "end_month": "2026-06"},
            "capex": {"base_monthly": 0, "milestones": {"by_month": {}}},
            "funding": {
                "initial_cash": 0,
                "equity": {"by_month": {"2026-06": 100000}},
                "debt": {"interest_rate": 0, "by_month": {}}
            }
        }

        output = cashflow_engine(assumptions, {"2026-06": 0}, {"2026-06": 0},
                                  {"2026-06": 0}, {"2026-06": 0})

        assert output.financing_cf["2026-06"] == 100000
        assert output.cash_balance["2026-06"] == 100000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
