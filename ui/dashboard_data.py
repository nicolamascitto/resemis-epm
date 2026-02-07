"""Transform scenario outputs into finance-first dashboard structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

import pandas as pd


@dataclass
class DashboardSnapshot:
    monthly: pd.DataFrame
    annual: pd.DataFrame
    revenue_by_product: pd.DataFrame
    units_by_product: pd.DataFrame
    revenue_by_market: pd.DataFrame
    cogs_by_input: pd.DataFrame
    opex_by_category: pd.DataFrame
    pricing_latest: pd.DataFrame
    risks: pd.DataFrame


def _month_key(value) -> str:
    text = str(value)
    if len(text) >= 7:
        return text[:7]
    return text


def _month_sort(values: List[str]) -> List[str]:
    def _parts(value: str):
        text = _month_key(value)
        try:
            return (int(text[:4]), int(text[5:7]))
        except Exception:
            return (9999, 99)

    return sorted([_month_key(value) for value in values], key=_parts)


def _as_float_map(values: Mapping) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key, value in values.items():
        try:
            out[_month_key(key)] = float(value)
        except Exception:
            out[_month_key(key)] = 0.0
    return out


def _safe_pct(num: float, den: float) -> float:
    return (num / den) if den else 0.0


def _to_monthly_df(result) -> pd.DataFrame:
    revenue_total = _as_float_map(getattr(result.revenue, "revenue_total", {}))
    cogs_total = _as_float_map(getattr(result.cogs, "total_cogs", {}))
    opex_total = _as_float_map(getattr(result.opex, "total_opex", {}))
    ebitda_total = _as_float_map(getattr(result.cashflow, "ebitda", {}))
    operating_cf_total = _as_float_map(getattr(result.cashflow, "operating_cf", {}))
    free_cf_total = _as_float_map(getattr(result.cashflow, "free_cf", {}))
    cash_total = _as_float_map(getattr(result.cashflow, "cash_balance", {}))
    debt_total = _as_float_map(getattr(result.cashflow, "debt_balance", {}))
    delta_wc_total = _as_float_map(getattr(result.working_capital, "delta_wc", {}))
    net_wc_total = _as_float_map(getattr(result.working_capital, "net_wc", {}))

    months = _month_sort(list(revenue_total.keys()))
    rows = []
    for month in months:
        revenue = float(revenue_total.get(month, 0.0))
        cogs = float(cogs_total.get(month, 0.0))
        opex = float(opex_total.get(month, 0.0))
        ebitda = float(ebitda_total.get(month, 0.0))
        operating_cf = float(operating_cf_total.get(month, 0.0))
        free_cf = float(free_cf_total.get(month, 0.0))
        cash = float(cash_total.get(month, 0.0))
        debt = float(debt_total.get(month, 0.0))
        delta_wc = float(delta_wc_total.get(month, 0.0))
        net_wc = float(net_wc_total.get(month, 0.0))
        month_year = int(month[:4]) if len(month) >= 4 and str(month[:4]).isdigit() else 0
        rows.append(
            {
                "month": month,
                "year": month_year,
                "revenue": revenue,
                "cogs": cogs,
                "gross_profit": revenue - cogs,
                "opex": opex,
                "ebitda": ebitda,
                "operating_cf": operating_cf,
                "free_cf": free_cf,
                "delta_wc": delta_wc,
                "net_wc": net_wc,
                "cash_balance": cash,
                "debt_balance": debt,
                "gross_margin_pct": _safe_pct(revenue - cogs, revenue),
                "ebitda_margin_pct": _safe_pct(ebitda, revenue),
                "opex_to_revenue_pct": _safe_pct(opex, revenue),
            }
        )
    return pd.DataFrame(rows)


def _to_annual_df(monthly: pd.DataFrame) -> pd.DataFrame:
    if monthly.empty:
        return pd.DataFrame(
            columns=[
                "year",
                "revenue",
                "cogs",
                "gross_profit",
                "opex",
                "ebitda",
                "operating_cf",
                "free_cf",
                "delta_wc",
                "net_wc",
                "cash_balance",
                "debt_balance",
                "gross_margin_pct",
                "ebitda_margin_pct",
            ]
        )

    grouped = (
        monthly.groupby("year", as_index=False)
        .agg(
            revenue=("revenue", "sum"),
            cogs=("cogs", "sum"),
            gross_profit=("gross_profit", "sum"),
            opex=("opex", "sum"),
            ebitda=("ebitda", "sum"),
            operating_cf=("operating_cf", "sum"),
            free_cf=("free_cf", "sum"),
            delta_wc=("delta_wc", "sum"),
            net_wc=("net_wc", "last"),
            cash_balance=("cash_balance", "last"),
            debt_balance=("debt_balance", "last"),
        )
        .sort_values("year")
    )
    grouped["gross_margin_pct"] = grouped.apply(
        lambda row: _safe_pct(float(row["gross_profit"]), float(row["revenue"])), axis=1
    )
    grouped["ebitda_margin_pct"] = grouped.apply(
        lambda row: _safe_pct(float(row["ebitda"]), float(row["revenue"])), axis=1
    )
    return grouped


def _agg_revenue_by_product(result) -> pd.DataFrame:
    rows = []
    for (_, product), value in result.revenue.revenue_by_product.items():
        rows.append({"product": product, "revenue": float(value)})
    if not rows:
        return pd.DataFrame(columns=["product", "revenue", "share_pct"])
    data = pd.DataFrame(rows).groupby("product", as_index=False)["revenue"].sum().sort_values(
        "revenue", ascending=False
    )
    total = float(data["revenue"].sum())
    data["share_pct"] = data["revenue"].apply(lambda value: _safe_pct(float(value), total))
    return data


def _agg_units_by_product(result) -> pd.DataFrame:
    rows = []
    for (_, product, _), value in result.revenue.units_kg.items():
        rows.append({"product": product, "units_kg": float(value)})
    if not rows:
        return pd.DataFrame(columns=["product", "units_kg"])
    return (
        pd.DataFrame(rows)
        .groupby("product", as_index=False)["units_kg"]
        .sum()
        .sort_values("units_kg", ascending=False)
    )


def _agg_revenue_by_market(result) -> pd.DataFrame:
    rows = []
    for (_, market), value in result.revenue.revenue_by_market.items():
        rows.append({"market": market, "revenue": float(value)})
    if not rows:
        return pd.DataFrame(columns=["market", "revenue", "share_pct"])
    data = pd.DataFrame(rows).groupby("market", as_index=False)["revenue"].sum().sort_values(
        "revenue", ascending=False
    )
    total = float(data["revenue"].sum())
    data["share_pct"] = data["revenue"].apply(lambda value: _safe_pct(float(value), total))
    return data


def _input_name_map(assumptions: Dict) -> Dict[str, str]:
    names: Dict[str, str] = {}
    bom = assumptions.get("bom", {}).get("by_product", {})
    if not isinstance(bom, dict):
        return names
    for product in bom.values():
        for item in product.get("inputs", []):
            input_id = str(item.get("input_id", "")).strip()
            if input_id:
                names[input_id] = str(item.get("input_name", input_id))
    return names


def _agg_cogs_by_input(result, assumptions: Dict) -> pd.DataFrame:
    rows = []
    name_map = _input_name_map(assumptions)
    for (_, _, input_id), value in result.cogs.variable_cogs_detailed.items():
        rows.append(
            {
                "input_id": input_id,
                "input_name": name_map.get(input_id, input_id),
                "variable_cogs": float(value),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["input_id", "input_name", "variable_cogs", "share_pct"])
    data = (
        pd.DataFrame(rows)
        .groupby(["input_id", "input_name"], as_index=False)["variable_cogs"]
        .sum()
        .sort_values("variable_cogs", ascending=False)
    )
    total = float(data["variable_cogs"].sum())
    data["share_pct"] = data["variable_cogs"].apply(lambda value: _safe_pct(float(value), total))
    return data


def _agg_opex_by_category(result) -> pd.DataFrame:
    rows = []
    for (_, category), value in result.opex.fixed_opex.items():
        rows.append({"category": category, "fixed_opex": float(value)})
    if not rows:
        return pd.DataFrame(columns=["category", "fixed_opex", "share_pct"])
    data = (
        pd.DataFrame(rows)
        .groupby("category", as_index=False)["fixed_opex"]
        .sum()
        .sort_values("fixed_opex", ascending=False)
    )
    total = float(data["fixed_opex"].sum())
    data["share_pct"] = data["fixed_opex"].apply(lambda value: _safe_pct(float(value), total))
    return data


def _latest_pricing(result) -> pd.DataFrame:
    if not result.revenue.net_prices:
        return pd.DataFrame(columns=["product", "market", "month", "net_price"])
    months = _month_sort(list({month for (month, _, _) in result.revenue.net_prices.keys()}))
    latest_month = months[-1]
    rows = []
    for (month, product, market), price in result.revenue.net_prices.items():
        if month == latest_month:
            rows.append(
                {
                    "product": product,
                    "market": market,
                    "month": month,
                    "net_price": float(price),
                }
            )
    return pd.DataFrame(rows).sort_values(["product", "market"])


def _build_risks(snapshot: DashboardSnapshot, result, assumptions: Dict) -> pd.DataFrame:
    assumptions = assumptions if isinstance(assumptions, dict) else {}
    rows = []
    if snapshot.monthly.empty:
        return pd.DataFrame(columns=["risk", "level", "signal", "mitigation"])

    monthly = snapshot.monthly
    annual = snapshot.annual
    min_cash_row = monthly.loc[monthly["cash_balance"].idxmin()]
    if float(min_cash_row["cash_balance"]) < 0:
        rows.append(
            {
                "risk": "Liquidity shortfall",
                "level": "Critical",
                "signal": f"Cash turns negative in {min_cash_row['month']} ({min_cash_row['cash_balance']:,.0f} EUR).",
                "mitigation": "Bring funding forward, reduce capex milestones, and tighten DSO assumptions.",
            }
        )
    else:
        rows.append(
            {
                "risk": "Liquidity buffer erosion",
                "level": "Medium" if float(min_cash_row["cash_balance"]) < 500000 else "Low",
                "signal": f"Minimum cash buffer is {min_cash_row['cash_balance']:,.0f} EUR in {min_cash_row['month']}.",
                "mitigation": "Track monthly runway and maintain covenant-style minimum cash guardrails.",
            }
        )

    concentration = (
        float(snapshot.revenue_by_product["share_pct"].max()) if not snapshot.revenue_by_product.empty else 0.0
    )
    if concentration >= 0.7:
        level = "High"
    elif concentration >= 0.5:
        level = "Medium"
    else:
        level = "Low"
    rows.append(
        {
            "risk": "Revenue concentration",
            "level": level,
            "signal": f"Top product share is {concentration * 100:.1f}% of total revenue.",
            "mitigation": "Diversify segment mix and monitor concentration thresholds in scenario reviews.",
        }
    )

    wc = assumptions.get("working_capital", {})
    dso = float(wc.get("dso_days", 0))
    dio = float(wc.get("dio_days", 0))
    dpo = float(wc.get("dpo_days", 0))
    cash_cycle = dso + dio - dpo
    rows.append(
        {
            "risk": "Working-capital pressure",
            "level": "High" if cash_cycle >= 75 else ("Medium" if cash_cycle >= 45 else "Low"),
            "signal": f"Cash conversion cycle proxy is {cash_cycle:.0f} days (DSO {dso:.0f} + DIO {dio:.0f} - DPO {dpo:.0f}).",
            "mitigation": "Improve collection terms, inventory turns, and supplier payment strategy.",
        }
    )

    ebitda_margin = float(annual["ebitda_margin_pct"].iloc[-1]) if not annual.empty else 0.0
    rows.append(
        {
            "risk": "Profitability execution",
            "level": "High" if ebitda_margin < 0.1 else ("Medium" if ebitda_margin < 0.2 else "Low"),
            "signal": f"Exit-year EBITDA margin is {ebitda_margin * 100:.1f}%.",
            "mitigation": "Track margin bridge by price, mix, BOM and fixed-cost ramps.",
        }
    )

    valuation = assumptions.get("valuation", {})
    discount_rate = float(valuation.get("discount_rate", 0.0))
    terminal_growth = float(valuation.get("terminal_growth_rate", 0.0))
    rows.append(
        {
            "risk": "Valuation fragility",
            "level": "High" if discount_rate >= 0.25 else ("Medium" if discount_rate >= 0.18 else "Low"),
            "signal": (
                f"Discount rate {discount_rate * 100:.1f}% vs terminal growth {terminal_growth * 100:.1f}% "
                f"with EV {result.enterprise_value:,.0f} EUR."
            ),
            "mitigation": "Use valuation bands and sensitivity cases for board and investor communication.",
        }
    )

    return pd.DataFrame(rows)


def build_snapshot(result, assumptions: Optional[Dict] = None) -> DashboardSnapshot:
    assumptions = assumptions if isinstance(assumptions, dict) else {}
    monthly = _to_monthly_df(result)
    annual = _to_annual_df(monthly)
    revenue_by_product = _agg_revenue_by_product(result)
    units_by_product = _agg_units_by_product(result)
    revenue_by_market = _agg_revenue_by_market(result)
    cogs_by_input = _agg_cogs_by_input(result, assumptions)
    opex_by_category = _agg_opex_by_category(result)
    pricing_latest = _latest_pricing(result)
    snapshot = DashboardSnapshot(
        monthly=monthly,
        annual=annual,
        revenue_by_product=revenue_by_product,
        units_by_product=units_by_product,
        revenue_by_market=revenue_by_market,
        cogs_by_input=cogs_by_input,
        opex_by_category=opex_by_category,
        pricing_latest=pricing_latest,
        risks=pd.DataFrame(),
    )
    snapshot.risks = _build_risks(snapshot, result, assumptions)
    return snapshot
