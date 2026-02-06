import copy
from pathlib import Path

from models.assumptions import (
    deep_merge,
    validate_assumptions,
    load_scenario_assumptions,
)


def _valid_assumptions():
    return {
        "time_horizon": {"start_month": "2026-01", "end_month": "2026-12"},
        "products": [{"product_id": "p1", "product_name": "P1", "unit": "kg"}],
        "markets": [{"market_id": "m1", "geo": "IT", "activation_month": "2026-01"}],
        "volume": {
            "tam": {"per_market_kg": {"m1": 1000}},
            "sam_share": {"per_market_pct": {"m1": 1.0}},
            "som_share": {
                "per_market_pct": {"m1": 1.0},
                "ramp": {"by_market": {"m1": {"start_month": "2026-01", "duration_months": 0}}},
            },
            "capacity": {"enabled": False, "by_month": {}},
        },
        "pricing": {
            "list_price": {"by_product": {"p1": {"by_month": {"2026-01": 1.0}}}},
            "discounts": {"by_product": {"p1": {"by_market": {"m1": {"by_month": {}}}}}},
        },
        "mix": {"by_market": {"m1": {"by_product": {"p1": {"by_year": {"2026": 1.0}}}}}},
        "bom": {
            "by_product": {
                "p1": {"inputs": [{"input_id": "i1", "qty_per_kg": 1.0, "input_name": "I1"}]}
            }
        },
        "valuation": {"discount_rate": 0.2, "terminal_growth_rate": 0.03},
    }


def test_deep_merge_keeps_originals():
    base = {"a": {"x": 1}, "b": 1}
    override = {"a": {"y": 2}}
    merged = deep_merge(base, override)
    assert merged == {"a": {"x": 1, "y": 2}, "b": 1}
    assert base == {"a": {"x": 1}, "b": 1}


def test_validate_assumptions_happy_path():
    assert validate_assumptions(_valid_assumptions()) == []


def test_validate_assumptions_catches_mix_sum():
    bad = copy.deepcopy(_valid_assumptions())
    bad["mix"]["by_market"]["m1"]["by_product"]["p1"]["by_year"]["2026"] = 0.9
    errors = validate_assumptions(bad)
    assert any("mix sum invalid" in err for err in errors)


def test_load_scenario_assumptions_merges_override(tmp_path: Path):
    base = _valid_assumptions()
    override = {"valuation": {"discount_rate": 0.25}}
    (tmp_path / "base.yaml").write_text(
        "valuation:\n  discount_rate: 0.2\n  terminal_growth_rate: 0.03\n"
        "time_horizon:\n  start_month: '2026-01'\n  end_month: '2026-12'\n"
        "products:\n  - product_id: p1\n"
        "markets:\n  - market_id: m1\n"
        "volume: {}\npricing: {}\nbom: {}\n",
        encoding="utf-8",
    )
    (tmp_path / "aggressive.yaml").write_text(
        "valuation:\n  discount_rate: 0.25\n", encoding="utf-8"
    )
    merged = load_scenario_assumptions("aggressive", tmp_path)
    assert merged["valuation"]["discount_rate"] == 0.25
    assert merged["valuation"]["terminal_growth_rate"] == 0.03
