# =============================================================================
# RESEMIS EPM ENGINE - COGS ENGINE TESTS
# =============================================================================
# Unit tests for the COGS engine modules.
# =============================================================================

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.bom import BOMInput, ProductBOM, load_bom, validate_bom
from models.input_prices import get_input_price_for_month, calculate_all_input_prices
from models.consumption import calculate_input_consumption
from models.variable_cogs import (
    calculate_variable_cogs_detailed,
    aggregate_variable_cogs_by_product,
    calculate_unit_variable_cogs
)
from models.fixed_cogs import calculate_fixed_cogs, allocate_fixed_cogs
from models.cogs import cogs_engine, validate_cogs_output


# =============================================================================
# BOM MODULE TESTS
# =============================================================================

class TestBOM:
    """Tests for BOM module."""

    def test_product_bom_total_qty(self):
        """Test total input quantity calculation."""
        bom = ProductBOM(
            product_id="test",
            inputs=[
                BOMInput("input1", "Input 1", 0.6, "raw_material"),
                BOMInput("input2", "Input 2", 0.5, "raw_material"),
            ]
        )
        assert bom.total_input_qty() == 1.1  # >= 1 for yield loss

    def test_validate_bom_yield_loss(self):
        """BOM with total < 1 should fail validation."""
        bom = {
            "test": ProductBOM(
                product_id="test",
                inputs=[
                    BOMInput("input1", "Input 1", 0.4, "raw_material"),
                    BOMInput("input2", "Input 2", 0.3, "raw_material"),
                ]
            )
        }
        errors = validate_bom(bom)
        assert len(errors) > 0
        assert "yield loss" in errors[0].lower()

    def test_validate_bom_valid(self):
        """Valid BOM should pass validation."""
        bom = {
            "test": ProductBOM(
                product_id="test",
                inputs=[
                    BOMInput("input1", "Input 1", 0.6, "raw_material"),
                    BOMInput("input2", "Input 2", 0.5, "raw_material"),
                ]
            )
        }
        errors = validate_bom(bom)
        assert len(errors) == 0


class TestLoadBOM:
    """Tests for BOM loading from assumptions."""

    def test_load_bom(self):
        """Test loading BOM from assumptions structure."""
        assumptions = {
            "bom": {
                "by_product": {
                    "biocore": {
                        "inputs": [
                            {"input_id": "rm1", "input_name": "Raw Material 1",
                             "qty_per_kg": 0.6, "input_type": "raw_material"},
                            {"input_id": "rm2", "input_name": "Raw Material 2",
                             "qty_per_kg": 0.5, "input_type": "raw_material"},
                        ]
                    }
                }
            }
        }
        bom = load_bom(assumptions)
        assert "biocore" in bom
        assert len(bom["biocore"].inputs) == 2
        assert bom["biocore"].total_input_qty() == 1.1


# =============================================================================
# INPUT PRICES TESTS
# =============================================================================

class TestInputPrices:
    """Tests for input price calculations."""

    def test_base_price_only(self):
        """Should use base price when no monthly overrides."""
        config = {"by_input": {"rm1": {"base_price": 1.50, "by_month": {}}}}
        price = get_input_price_for_month("2026-06", "rm1", config)
        assert price == 1.50

    def test_step_function(self):
        """Should use most recent price before target month."""
        config = {
            "by_input": {
                "rm1": {
                    "base_price": 1.50,
                    "by_month": {"2026-01": 1.40, "2027-01": 1.30}
                }
            }
        }
        # Before any override: base price
        assert get_input_price_for_month("2025-12", "rm1", config) == 1.50
        # After first override
        assert get_input_price_for_month("2026-06", "rm1", config) == 1.40
        # After second override
        assert get_input_price_for_month("2027-06", "rm1", config) == 1.30


# =============================================================================
# CONSUMPTION TESTS
# =============================================================================

class TestConsumption:
    """Tests for input consumption calculation."""

    def test_basic_consumption(self):
        """Consumption = Volume * BOM qty."""
        units_kg = {("2026-06", "biocore", "italy"): 100}
        bom = {
            "biocore": ProductBOM(
                product_id="biocore",
                inputs=[
                    BOMInput("rm1", "RM1", 0.6, "raw_material"),
                    BOMInput("rm2", "RM2", 0.5, "raw_material"),
                ]
            )
        }
        consumption = calculate_input_consumption(units_kg, bom)
        assert consumption[("2026-06", "biocore", "rm1")] == 60  # 100 * 0.6
        assert consumption[("2026-06", "biocore", "rm2")] == 50  # 100 * 0.5

    def test_zero_volume(self):
        """Zero volume should give zero consumption."""
        units_kg = {("2026-06", "biocore", "italy"): 0}
        bom = {
            "biocore": ProductBOM(
                product_id="biocore",
                inputs=[BOMInput("rm1", "RM1", 0.6, "raw_material")]
            )
        }
        consumption = calculate_input_consumption(units_kg, bom)
        assert consumption[("2026-06", "biocore", "rm1")] == 0

    def test_double_volume_double_consumption(self):
        """2x volume should give 2x consumption."""
        bom = {
            "biocore": ProductBOM(
                product_id="biocore",
                inputs=[BOMInput("rm1", "RM1", 0.6, "raw_material")]
            )
        }
        units_kg_1 = {("2026-06", "biocore", "italy"): 100}
        units_kg_2 = {("2026-06", "biocore", "italy"): 200}

        cons_1 = calculate_input_consumption(units_kg_1, bom)
        cons_2 = calculate_input_consumption(units_kg_2, bom)

        assert cons_2[("2026-06", "biocore", "rm1")] == 2 * cons_1[("2026-06", "biocore", "rm1")]


# =============================================================================
# VARIABLE COGS TESTS
# =============================================================================

class TestVariableCOGS:
    """Tests for variable COGS calculation."""

    def test_basic_variable_cogs(self):
        """Variable COGS = Consumption * Price."""
        consumption = {("2026-06", "biocore", "rm1"): 60}
        input_prices = {("2026-06", "rm1"): 1.50}

        cogs = calculate_variable_cogs_detailed(consumption, input_prices)
        assert cogs[("2026-06", "biocore", "rm1")] == 90  # 60 * 1.50

    def test_price_isolation(self):
        """Changing price should change COGS proportionally."""
        consumption = {("2026-06", "biocore", "rm1"): 60}

        cogs_1 = calculate_variable_cogs_detailed(consumption, {("2026-06", "rm1"): 1.00})
        cogs_2 = calculate_variable_cogs_detailed(consumption, {("2026-06", "rm1"): 2.00})

        assert cogs_2[("2026-06", "biocore", "rm1")] == 2 * cogs_1[("2026-06", "biocore", "rm1")]


# =============================================================================
# FIXED COGS TESTS
# =============================================================================

class TestFixedCOGS:
    """Tests for fixed COGS calculation."""

    def test_basic_fixed_cogs(self):
        """Fixed COGS = base * ramp."""
        fixed = calculate_fixed_cogs(
            months=["2026-06"],
            base_monthly=10000,
            ramp_by_month={"2026-01": 1.0}
        )
        assert fixed["2026-06"] == 10000

    def test_ramp_factor(self):
        """Ramp factor should scale fixed COGS."""
        fixed = calculate_fixed_cogs(
            months=["2026-06", "2027-06"],
            base_monthly=10000,
            ramp_by_month={"2026-01": 1.0, "2027-01": 1.5}
        )
        assert fixed["2026-06"] == 10000
        assert fixed["2027-06"] == 15000

    def test_allocation(self):
        """Allocation should be proportional to volume."""
        fixed_cogs = {"2026-06": 10000}
        units_by_product = {
            ("2026-06", "product_a"): 60,
            ("2026-06", "product_b"): 40
        }
        allocated = allocate_fixed_cogs(fixed_cogs, units_by_product)
        assert allocated[("2026-06", "product_a")] == 6000  # 60%
        assert allocated[("2026-06", "product_b")] == 4000  # 40%


# =============================================================================
# COGS ENGINE INTEGRATION TESTS
# =============================================================================

class TestCOGSEngine:
    """Integration tests for main COGS engine."""

    def get_test_assumptions(self):
        """Create test assumptions."""
        return {
            "time_horizon": {"start_month": "2026-06", "end_month": "2026-06"},
            "bom": {
                "by_product": {
                    "biocore": {
                        "inputs": [
                            {"input_id": "rm1", "input_name": "RM1",
                             "qty_per_kg": 0.6, "input_type": "raw_material"},
                            {"input_id": "rm2", "input_name": "RM2",
                             "qty_per_kg": 0.5, "input_type": "raw_material"},
                        ]
                    }
                }
            },
            "input_prices": {
                "by_input": {
                    "rm1": {"base_price": 1.50, "by_month": {}},
                    "rm2": {"base_price": 1.00, "by_month": {}},
                }
            },
            "fixed_cogs": {
                "base_monthly": 5000,
                "ramp": {"by_month": {"2026-01": 1.0}}
            }
        }

    def test_zero_volume_zero_variable_cogs(self):
        """Zero volume should result in zero variable COGS."""
        assumptions = self.get_test_assumptions()
        units_kg = {("2026-06", "biocore", "italy"): 0}

        output = cogs_engine(assumptions, units_kg)

        assert output.variable_cogs_total.get("2026-06", 0) == 0
        # Fixed COGS still exists
        assert output.fixed_cogs["2026-06"] == 5000

    def test_full_calculation(self):
        """Test full COGS calculation pipeline."""
        assumptions = self.get_test_assumptions()
        units_kg = {("2026-06", "biocore", "italy"): 100}

        output = cogs_engine(assumptions, units_kg)

        # Variable COGS: (100 * 0.6 * 1.50) + (100 * 0.5 * 1.00) = 90 + 50 = 140
        assert output.variable_cogs_total["2026-06"] == 140

        # Fixed COGS
        assert output.fixed_cogs["2026-06"] == 5000

        # Total COGS
        assert output.total_cogs["2026-06"] == 5140

        # Unit costs
        assert output.unit_variable_cogs["2026-06"] == 1.40  # 140 / 100
        assert output.unit_total_cogs["2026-06"] == 51.40  # 5140 / 100

    def test_no_flat_cogs_check(self):
        """Verify COGS comes from BOM, not flat rate."""
        assumptions = self.get_test_assumptions()

        # Two different volumes
        units_kg_1 = {("2026-06", "biocore", "italy"): 100}
        units_kg_2 = {("2026-06", "biocore", "italy"): 200}

        output_1 = cogs_engine(assumptions, units_kg_1)
        output_2 = cogs_engine(assumptions, units_kg_2)

        # Variable COGS should scale with volume (not flat)
        var_1 = output_1.variable_cogs_total["2026-06"]
        var_2 = output_2.variable_cogs_total["2026-06"]

        assert var_2 == 2 * var_1  # 2x volume = 2x variable COGS


class TestCOGSValidation:
    """Tests for COGS output validation."""

    def test_valid_output(self):
        """Valid output should have no errors."""
        from models.cogs import COGSOutput
        output = COGSOutput(
            variable_cogs_total={"2026-06": 100},
            fixed_cogs={"2026-06": 50},
            total_cogs={"2026-06": 150}
        )
        errors = validate_cogs_output(output)
        assert len(errors) == 0


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
