# =============================================================================
# RESEMIS EPM ENGINE - WORKING CAPITAL TESTS
# =============================================================================

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.working_capital import (
    WCTerms, calculate_ar, calculate_inventory, calculate_ap,
    calculate_deltas, calculate_net_wc, working_capital_engine
)


class TestAR:
    """Tests for Accounts Receivable calculation."""

    def test_zero_revenue_zero_ar(self):
        """Zero revenue should give zero AR."""
        ar = calculate_ar({"2026-06": 0}, dso_days=45)
        assert ar["2026-06"] == 0

    def test_ar_formula(self):
        """AR = Revenue * (DSO / 30)."""
        ar = calculate_ar({"2026-06": 30000}, dso_days=45)
        assert ar["2026-06"] == 45000  # 30000 * 1.5

    def test_higher_dso_higher_ar(self):
        """Higher DSO should give higher AR."""
        ar_30 = calculate_ar({"2026-06": 30000}, dso_days=30)
        ar_60 = calculate_ar({"2026-06": 30000}, dso_days=60)
        assert ar_60["2026-06"] > ar_30["2026-06"]


class TestInventory:
    """Tests for Inventory calculation."""

    def test_inventory_formula(self):
        """Inventory = COGS * (DIO / 30)."""
        inv = calculate_inventory({"2026-06": 10000}, dio_days=30)
        assert inv["2026-06"] == 10000  # 10000 * 1.0


class TestAP:
    """Tests for Accounts Payable calculation."""

    def test_ap_formula(self):
        """AP = COGS * (DPO / 30)."""
        ap = calculate_ap({"2026-06": 10000}, dpo_days=60)
        assert ap["2026-06"] == 20000  # 10000 * 2.0

    def test_higher_dpo_better_cash(self):
        """Higher DPO means more AP (better for cash)."""
        ap_30 = calculate_ap({"2026-06": 10000}, dpo_days=30)
        ap_90 = calculate_ap({"2026-06": 10000}, dpo_days=90)
        assert ap_90["2026-06"] > ap_30["2026-06"]


class TestDeltas:
    """Tests for delta calculations."""

    def test_first_month_delta(self):
        """First month delta equals the value (previous was 0)."""
        values = {"2026-01": 100, "2026-02": 150}
        deltas = calculate_deltas(values, ["2026-01", "2026-02"])
        assert deltas["2026-01"] == 100
        assert deltas["2026-02"] == 50


class TestNetWC:
    """Tests for net working capital."""

    def test_net_wc_formula(self):
        """Net WC = AR + Inventory - AP."""
        ar = {"2026-06": 100}
        inv = {"2026-06": 50}
        ap = {"2026-06": 80}
        net_wc = calculate_net_wc(ar, inv, ap)
        assert net_wc["2026-06"] == 70  # 100 + 50 - 80


class TestWCEngine:
    """Integration tests for working capital engine."""

    def test_full_calculation(self):
        """Test full working capital calculation."""
        assumptions = {
            "time_horizon": {"start_month": "2026-06", "end_month": "2026-07"},
            "working_capital": {"dso_days": 30, "dio_days": 30, "dpo_days": 30}
        }
        revenue = {"2026-06": 10000, "2026-07": 12000}
        cogs = {"2026-06": 5000, "2026-07": 6000}

        output = working_capital_engine(assumptions, revenue, cogs)

        # AR = Revenue * 1.0 (30/30)
        assert output.ar["2026-06"] == 10000
        assert output.ar["2026-07"] == 12000

        # Delta AR
        assert output.delta_ar["2026-06"] == 10000  # From 0
        assert output.delta_ar["2026-07"] == 2000  # 12000 - 10000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
