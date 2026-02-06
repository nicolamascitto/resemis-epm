"""Assumptions loading and validation utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple
import copy

import yaml


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base; lists are replaced, not merged."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_yaml_file(path: Path) -> dict:
    """Load a YAML file and return an object (empty dict for empty files)."""
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_scenario_assumptions(scenario_id: str, assumptions_dir: Path) -> dict:
    """Load base assumptions and merge scenario override if present."""
    base = load_yaml_file(assumptions_dir / "base.yaml")
    if scenario_id == "base":
        return base

    override_path = assumptions_dir / f"{scenario_id}.yaml"
    if override_path.exists():
        return deep_merge(base, load_yaml_file(override_path))
    return base


def _parse_month(month: str) -> Tuple[int, int]:
    parts = month.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid month format: {month}")
    year = int(parts[0])
    mon = int(parts[1])
    if mon < 1 or mon > 12:
        raise ValueError(f"Invalid month value: {month}")
    return year, mon


def _is_before(a: str, b: str) -> bool:
    return _parse_month(a) < _parse_month(b)


def validate_assumptions(assumptions: Dict) -> List[str]:
    """
    Validate assumptions structure and key constraints.

    Keeps compatibility with existing tests by preserving message prefixes
    for required-section and discount-rate validations.
    """
    errors: List[str] = []

    required = ["time_horizon", "products", "markets", "volume", "pricing", "bom"]
    for section in required:
        if section not in assumptions:
            errors.append(f"Missing required section: {section}")

    time_horizon = assumptions.get("time_horizon", {})
    start_month = time_horizon.get("start_month")
    end_month = time_horizon.get("end_month")
    if start_month and end_month:
        try:
            if not _is_before(start_month, end_month) and start_month != end_month:
                errors.append(
                    f"time_horizon invalid: start_month {start_month} must be <= end_month {end_month}"
                )
        except ValueError as exc:
            errors.append(str(exc))

    # Scenario/market timing consistency.
    if start_month:
        for market in assumptions.get("markets", []):
            activation = market.get("activation_month")
            market_id = market.get("market_id", "<unknown>")
            if activation:
                try:
                    if _is_before(activation, start_month):
                        errors.append(
                            f"activation_month invalid for market {market_id}: {activation} < {start_month}"
                        )
                except ValueError as exc:
                    errors.append(str(exc))

    # Percent constraints from schema.
    valuation = assumptions.get("valuation", {})
    discount_rate = valuation.get("discount_rate", 0.15)
    terminal_growth = valuation.get("terminal_growth_rate", 0.02)
    if discount_rate <= terminal_growth:
        errors.append(
            f"discount_rate ({discount_rate}) must be > terminal_growth_rate ({terminal_growth})"
        )

    # Mix must sum to 1 for each market/year.
    mix_by_market = assumptions.get("mix", {}).get("by_market", {})
    for market_id, market_data in mix_by_market.items():
        sums: Dict[str, float] = {}
        for _, product_data in market_data.get("by_product", {}).items():
            for year, pct in product_data.get("by_year", {}).items():
                if pct < 0 or pct > 1:
                    errors.append(
                        f"mix percentage out of range for market={market_id}, year={year}: {pct}"
                    )
                sums[year] = sums.get(year, 0.0) + float(pct)
        for year, total in sums.items():
            if abs(total - 1.0) > 1e-6:
                errors.append(
                    f"mix sum invalid for market={market_id}, year={year}: {total} (must equal 1)"
                )

    # BOM total quantity should cover at least 1kg finished output.
    for product_id, product in assumptions.get("bom", {}).get("by_product", {}).items():
        total_qty = sum(float(i.get("qty_per_kg", 0.0)) for i in product.get("inputs", []))
        if total_qty < 1.0:
            errors.append(
                f"bom total qty_per_kg invalid for product {product_id}: {total_qty} (< 1.0)"
            )

    return errors

