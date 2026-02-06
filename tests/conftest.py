# =============================================================================
# RESEMIS EPM ENGINE - PYTEST CONFIGURATION
# =============================================================================
# Shared fixtures and configuration for all tests.
# =============================================================================

import pytest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def assumptions_dir(project_root):
    """Get assumptions directory."""
    return project_root / "assumptions"


@pytest.fixture
def base_assumptions():
    """Load base assumptions for testing."""
    return {
        "time_horizon": {"start_month": "2026-06", "end_month": "2026-12"},
        "products": [
            {"product_id": "biocore", "product_name": "BioCore", "unit": "kg"}
        ],
        "markets": [
            {"market_id": "italy", "geo": "IT", "activation_month": "2026-06"}
        ],
        "volume": {
            "tam": {"per_market_kg": {"italy": 100000}},
            "sam_share": {"per_market_pct": {"italy": 0.25}},
            "som_share": {
                "per_market_pct": {"italy": 0.10},
                "ramp": {"by_market": {"italy": {"start_month": "2026-06", "duration_months": 12}}}
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
        },
        "bom": {
            "by_product": {
                "biocore": {
                    "inputs": [
                        {"input_id": "rm1", "input_name": "Raw Material 1",
                         "qty_per_kg": 0.6, "input_type": "raw_material"},
                        {"input_id": "rm2", "input_name": "Raw Material 2",
                         "qty_per_kg": 0.5, "input_type": "raw_material"}
                    ]
                }
            }
        },
        "input_prices": {
            "by_input": {
                "rm1": {"base_price": 1.50, "by_month": {}},
                "rm2": {"base_price": 1.00, "by_month": {}}
            }
        },
        "fixed_cogs": {
            "base_monthly": 5000,
            "ramp": {"by_month": {}}
        },
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
        },
        "working_capital": {
            "dso_days": 45,
            "dio_days": 30,
            "dpo_days": 60
        },
        "capex": {
            "base_monthly": 1000,
            "milestones": {"by_month": {}}
        },
        "funding": {
            "initial_cash": 100000,
            "equity": {"by_month": {}},
            "debt": {"interest_rate": 0.05, "by_month": {}}
        },
        "valuation": {
            "discount_rate": 0.15,
            "terminal_growth_rate": 0.02,
            "terminal_method": "gordon",
            "exit_year": 2026,
            "equity": {"ownership_pct": 1.0, "invested": {"by_month": {}}}
        }
    }


@pytest.fixture
def simple_bom():
    """Simple BOM for testing."""
    from models.bom import BOMInput, ProductBOM
    return {
        "biocore": ProductBOM(
            product_id="biocore",
            inputs=[
                BOMInput("rm1", "Raw Material 1", 0.6, "raw_material"),
                BOMInput("rm2", "Raw Material 2", 0.5, "raw_material")
            ]
        )
    }


@pytest.fixture
def time_range():
    """Generate standard time range for testing."""
    from models.revenue import generate_months
    return generate_months("2026-06", "2026-12")


@pytest.fixture
def sample_revenue_output(base_assumptions):
    """Run revenue engine and return output."""
    from models.revenue import revenue_engine
    return revenue_engine(base_assumptions)


@pytest.fixture
def sample_cogs_output(base_assumptions, sample_revenue_output):
    """Run COGS engine and return output."""
    from models.cogs import cogs_engine
    return cogs_engine(base_assumptions, sample_revenue_output.units_kg)
