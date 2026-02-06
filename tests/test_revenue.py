# =============================================================================
# RESEMIS EPM ENGINE - REVENUE ENGINE TESTS
# =============================================================================
# Unit tests for the revenue engine modules.
# =============================================================================

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.volume import (
    calculate_som_with_ramp,
    calculate_addressable_kg,
    calculate_potential_kg,
    apply_capacity_constraint,
    allocate_to_markets
)
from models.pricing import (
    get_price_for_month,
    get_discount_for_month,
    calculate_net_price,
    validate_pricing_inputs
)
from models.mix import (
    get_mix_for_month,
    allocate_to_products,
    validate_mix
)
from models.revenue import (
    generate_months,
    revenue_engine,
    validate_revenue_output
)


# =============================================================================
# VOLUME MODULE TESTS
# =============================================================================

class TestSomWithRamp:
    """Tests for calculate_som_with_ramp function."""

    def test_before_activation(self):
        """SOM should be 0 before activation month."""
        result = calculate_som_with_ramp(
            month="2026-01",
            market="italy",
            steady_state_som=0.10,
            activation_month="2026-06",
            ramp_duration_months=24
        )
        assert result == 0.0

    def test_at_activation(self):
        """SOM should be 0 at activation month (start of ramp)."""
        result = calculate_som_with_ramp(
            month="2026-06",
            market="italy",
            steady_state_som=0.10,
            activation_month="2026-06",
            ramp_duration_months=24
        )
        assert result == 0.0

    def test_during_ramp_linear(self):
        """SOM should ramp linearly."""
        result = calculate_som_with_ramp(
            month="2026-12",
            market="italy",
            steady_state_som=0.10,
            activation_month="2026-06",
            ramp_duration_months=24,
            ramp_curve="linear"
        )
        # 6 months elapsed out of 24 = 25% of ramp
        expected = 0.10 * (6 / 24)
        assert abs(result - expected) < 0.0001

    def test_after_ramp_complete(self):
        """SOM should be at steady state after ramp."""
        result = calculate_som_with_ramp(
            month="2028-06",
            market="italy",
            steady_state_som=0.10,
            activation_month="2026-06",
            ramp_duration_months=24
        )
        assert result == 0.10


class TestAddressableKg:
    """Tests for calculate_addressable_kg function."""

    def test_basic_calculation(self):
        """Test basic TAM * SAM * SOM calculation."""
        tam = {"italy": 1000}
        sam = {"italy": 0.25}
        som = {("2026-06", "italy"): 0.10}
        result = calculate_addressable_kg(tam, sam, som)
        assert result[("2026-06", "italy")] == 25  # 1000 * 0.25 * 0.10

    def test_multiple_markets(self):
        """Test calculation with multiple markets."""
        tam = {"italy": 1000, "eu": 5000}
        sam = {"italy": 0.25, "eu": 0.20}
        som = {
            ("2026-06", "italy"): 0.10,
            ("2026-06", "eu"): 0.05
        }
        result = calculate_addressable_kg(tam, sam, som)
        assert result[("2026-06", "italy")] == 25  # 1000 * 0.25 * 0.10
        assert result[("2026-06", "eu")] == 50  # 5000 * 0.20 * 0.05

    def test_zero_som(self):
        """SOM=0 should result in 0 addressable kg."""
        tam = {"italy": 1000}
        sam = {"italy": 0.25}
        som = {("2026-01", "italy"): 0.0}
        result = calculate_addressable_kg(tam, sam, som)
        assert result[("2026-01", "italy")] == 0


class TestCapacityConstraint:
    """Tests for apply_capacity_constraint function."""

    def test_no_capacity(self):
        """No capacity should return original potential."""
        potential = {"2026-06": 100}
        result = apply_capacity_constraint(potential, None)
        assert result["2026-06"] == 100

    def test_capacity_above_potential(self):
        """Capacity above potential should return potential."""
        potential = {"2026-06": 100}
        capacity = {"2026-06": 150}
        result = apply_capacity_constraint(potential, capacity)
        assert result["2026-06"] == 100

    def test_capacity_below_potential(self):
        """Capacity below potential should return capacity."""
        potential = {"2026-06": 100}
        capacity = {"2026-06": 80}
        result = apply_capacity_constraint(potential, capacity)
        assert result["2026-06"] == 80


# =============================================================================
# PRICING MODULE TESTS
# =============================================================================

class TestPriceForMonth:
    """Tests for get_price_for_month function."""

    def test_base_price_only(self):
        """No monthly prices should return base price."""
        result = get_price_for_month("2026-06", {}, 10.0)
        assert result == 10.0

    def test_exact_month_match(self):
        """Exact month match should return that price."""
        prices = {"2026-06": 12.0, "2027-01": 11.0}
        result = get_price_for_month("2026-06", prices, 10.0)
        assert result == 12.0

    def test_step_function(self):
        """Should use most recent price."""
        prices = {"2026-01": 12.0, "2027-01": 11.0}
        result = get_price_for_month("2026-06", prices, 10.0)
        assert result == 12.0


class TestNetPrice:
    """Tests for calculate_net_price function."""

    def test_no_discount(self):
        """No discount should return list price."""
        list_prices = {
            "by_product": {
                "biocore": {"base_price": 10.0, "by_month": {}}
            }
        }
        discounts = {"by_product": {}}
        result = calculate_net_price("2026-06", "biocore", "italy", list_prices, discounts)
        assert result == 10.0

    def test_with_discount(self):
        """Discount should be applied correctly."""
        list_prices = {
            "by_product": {
                "biocore": {"base_price": 10.0, "by_month": {}}
            }
        }
        discounts = {
            "by_product": {
                "biocore": {
                    "by_market": {
                        "italy": {
                            "by_month": {"2026-01": 0.10}
                        }
                    }
                }
            }
        }
        result = calculate_net_price("2026-06", "biocore", "italy", list_prices, discounts)
        assert result == 9.0  # 10.0 * (1 - 0.10)


# =============================================================================
# MIX MODULE TESTS
# =============================================================================

class TestMix:
    """Tests for mix allocation."""

    def test_single_product(self):
        """Single product should get 100%."""
        mix_config = {
            "by_market": {
                "italy": {
                    "by_product": {
                        "biocore": {"by_year": {"2026": 1.0}}
                    }
                }
            }
        }
        result = get_mix_for_month("2026-06", "biocore", "italy", mix_config)
        assert result == 1.0

    def test_multiple_products(self):
        """Multiple products should split correctly."""
        mix_config = {
            "by_market": {
                "italy": {
                    "by_product": {
                        "biocore": {"by_year": {"2026": 0.6}},
                        "runcover": {"by_year": {"2026": 0.4}}
                    }
                }
            }
        }
        assert get_mix_for_month("2026-06", "biocore", "italy", mix_config) == 0.6
        assert get_mix_for_month("2026-06", "runcover", "italy", mix_config) == 0.4


class TestMixValidation:
    """Tests for mix validation."""

    def test_valid_mix(self):
        """Mix summing to 1 should pass."""
        mix_config = {
            "by_market": {
                "italy": {
                    "by_product": {
                        "biocore": {"by_year": {"2026": 0.6}},
                        "runcover": {"by_year": {"2026": 0.4}}
                    }
                }
            }
        }
        errors = validate_mix(
            ["2026-01", "2026-06"],
            ["italy"],
            ["biocore", "runcover"],
            mix_config
        )
        assert len(errors) == 0

    def test_invalid_mix(self):
        """Mix not summing to 1 should fail."""
        mix_config = {
            "by_market": {
                "italy": {
                    "by_product": {
                        "biocore": {"by_year": {"2026": 0.6}},
                        "runcover": {"by_year": {"2026": 0.3}}
                    }
                }
            }
        }
        errors = validate_mix(
            ["2026-01"],
            ["italy"],
            ["biocore", "runcover"],
            mix_config
        )
        assert len(errors) > 0


# =============================================================================
# REVENUE ENGINE TESTS
# =============================================================================

class TestGenerateMonths:
    """Tests for generate_months function."""

    def test_single_year(self):
        """Should generate correct months within a year."""
        result = generate_months("2026-01", "2026-03")
        assert result == ["2026-01", "2026-02", "2026-03"]

    def test_across_years(self):
        """Should handle year boundary."""
        result = generate_months("2026-11", "2027-02")
        assert result == ["2026-11", "2026-12", "2027-01", "2027-02"]


class TestRevenueEngine:
    """Tests for the main revenue engine."""

    def test_zero_som_zero_revenue(self):
        """Zero SOM should result in zero revenue."""
        assumptions = {
            "time_horizon": {"start_month": "2026-01", "end_month": "2026-03"},
            "products": [{"product_id": "biocore", "product_name": "BioCore", "unit": "kg"}],
            "markets": [{"market_id": "italy", "geo": "IT", "activation_month": "2027-01"}],
            "volume": {
                "tam": {"per_market_kg": {"italy": 1000}},
                "sam_share": {"per_market_pct": {"italy": 0.25}},
                "som_share": {
                    "per_market_pct": {"italy": 0.10},
                    "ramp": {"by_market": {"italy": {"duration_months": 24}}}
                },
                "capacity": {"enabled": False}
            },
            "mix": {
                "by_market": {
                    "italy": {
                        "by_product": {
                            "biocore": {"by_year": {"2026": 1.0}}
                        }
                    }
                }
            },
            "pricing": {
                "list_price": {
                    "by_product": {
                        "biocore": {"base_price": 10.0, "by_month": {}}
                    }
                },
                "discounts": {"by_product": {}}
            }
        }
        result = revenue_engine(assumptions)

        # All revenue should be 0 (market not activated yet)
        for month, rev in result.revenue_total.items():
            assert rev == 0.0


class TestRevenueOutputValidation:
    """Tests for revenue output validation."""

    def test_valid_output(self):
        """Valid output should have no errors."""
        from models.revenue import RevenueOutput
        output = RevenueOutput(
            units_kg={("2026-06", "biocore", "italy"): 100},
            net_prices={("2026-06", "biocore", "italy"): 10.0},
            revenue={("2026-06", "biocore", "italy"): 1000}
        )
        errors = validate_revenue_output(output)
        assert len(errors) == 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestRevenueIntegration:
    """Integration tests for full revenue calculation."""

    def test_simple_scenario(self):
        """Test simple single-product single-market scenario."""
        assumptions = {
            "time_horizon": {"start_month": "2026-06", "end_month": "2026-06"},
            "products": [{"product_id": "biocore", "product_name": "BioCore", "unit": "kg"}],
            "markets": [{"market_id": "italy", "geo": "IT", "activation_month": "2026-01"}],
            "volume": {
                "tam": {"per_market_kg": {"italy": 1000}},
                "sam_share": {"per_market_pct": {"italy": 0.25}},
                "som_share": {
                    "per_market_pct": {"italy": 0.10},
                    "ramp": {"by_market": {"italy": {"start_month": "2026-01", "duration_months": 0}}}
                },
                "capacity": {"enabled": False}
            },
            "mix": {
                "by_market": {
                    "italy": {
                        "by_product": {
                            "biocore": {"by_year": {"2026": 1.0}}
                        }
                    }
                }
            },
            "pricing": {
                "list_price": {
                    "by_product": {
                        "biocore": {"base_price": 10.0, "by_month": {}}
                    }
                },
                "discounts": {"by_product": {}}
            }
        }
        result = revenue_engine(assumptions)

        # Expected: 1000 * 0.25 * 0.10 = 25 kg @ 10 EUR/kg = 250 EUR
        assert result.units_kg[("2026-06", "biocore", "italy")] == 25
        assert result.revenue[("2026-06", "biocore", "italy")] == 250
        assert result.revenue_total["2026-06"] == 250


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
