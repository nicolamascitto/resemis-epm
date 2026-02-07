from __future__ import annotations

import copy
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yaml

from models.assumptions import load_scenario_assumptions, validate_assumptions
from models.cashflow import cashflow_engine
from models.cogs import cogs_engine
from models.opex import opex_engine
from models.revenue import revenue_engine
from models.scenario import ScenarioResult
from models.valuation import valuation_engine
from models.working_capital import working_capital_engine
from ui.dashboard_data import DashboardSnapshot, build_snapshot


st.set_page_config(
    page_title="ReSemis EPM",
    page_icon="R",
    layout="wide",
    initial_sidebar_state="expanded",
)


THEMES: Dict[str, Dict[str, str]] = {
    "light": {
        "bg": "#F4F7FB",
        "surface": "#FFFFFF",
        "surface_alt": "#EEF3F9",
        "text": "#101828",
        "text_muted": "#475467",
        "border": "#D4DCE7",
        "primary": "#165DFF",
        "success": "#117A37",
        "warning": "#B54708",
        "critical": "#B42318",
        "grid": "#DFE6F0",
        "shadow": "0 10px 28px rgba(15, 23, 42, 0.09)",
    },
    "dark": {
        "bg": "#061529",
        "surface": "#0E223E",
        "surface_alt": "#132A4A",
        "text": "#E7EEF8",
        "text_muted": "#A3B4CC",
        "border": "#2A4265",
        "primary": "#4A9EFF",
        "success": "#2FC277",
        "warning": "#F0A646",
        "critical": "#FF6B6B",
        "grid": "#2D4469",
        "shadow": "0 14px 34px rgba(2, 6, 23, 0.45)",
    },
}


def _qp_value(key: str, default: str) -> str:
    value = st.query_params.get(key, default)
    if isinstance(value, list):
        return value[0] if value else default
    return str(value)


def _set_query(section: str, theme: str) -> None:
    st.query_params["section"] = section.lower()
    st.query_params["theme"] = theme


def _fmt_currency(value: float) -> str:
    return f"EUR {value:,.0f}"


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _safe_pct(num: float, den: float) -> float:
    return (num / den) if den else 0.0


def _month_sort(values: Iterable[str]) -> List[str]:
    return sorted(values, key=lambda m: (int(str(m)[:4]), int(str(m)[5:7])))


def _to_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return default


def _to_int(value, default: int = 0) -> int:
    return int(round(_to_float(value, float(default))))


def _clean_id(value, prefix: str) -> str:
    raw = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    cleaned = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in raw)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_")
    return cleaned or prefix


def _years_from_assumptions(assumptions: Dict) -> List[int]:
    horizon = assumptions.get("time_horizon", {})
    start = str(horizon.get("start_month", "2026-01"))
    end = str(horizon.get("end_month", "2030-12"))
    try:
        y0 = int(start[:4])
        y1 = int(end[:4])
        if y1 < y0:
            raise ValueError
        return list(range(y0, y1 + 1))
    except Exception:
        return [2026, 2027, 2028, 2029, 2030]


def _january_months(years: Iterable[int]) -> List[str]:
    return [f"{int(year)}-01" for year in years]


def _step_value(by_month: Dict[str, float], month: str, default: float = 0.0) -> float:
    if not by_month:
        return default
    if month in by_month:
        return _to_float(by_month.get(month), default)
    value = default
    for key in _month_sort(by_month.keys()):
        if key <= month:
            value = _to_float(by_month.get(key), value)
        else:
            break
    return value


def _apply_theme(theme: str) -> None:
    t = THEMES[theme]
    st.markdown(
        f"""
<style>
    :root {{
        --bg: {t['bg']};
        --surface: {t['surface']};
        --surface-alt: {t['surface_alt']};
        --text: {t['text']};
        --text-muted: {t['text_muted']};
        --border: {t['border']};
        --primary: {t['primary']};
        --success: {t['success']};
        --warning: {t['warning']};
        --critical: {t['critical']};
        --shadow: {t['shadow']};
    }}

    .stApp {{
        background: var(--bg);
        color: var(--text);
        transition: background-color 0.25s ease, color 0.25s ease;
    }}

    [data-testid="stHeader"] {{
        background: var(--bg);
        border-bottom: 1px solid var(--border);
    }}

    [data-testid="stSidebar"] {{
        background: var(--surface);
        border-right: 1px solid var(--border);
    }}

    [data-testid="stSidebar"] * {{
        color: var(--text);
    }}

    [data-testid="stSidebar"] [data-baseweb="select"] > div {{
        background: var(--surface-alt) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
    }}

    [data-testid="stSidebar"] [data-baseweb="select"] span {{
        color: var(--text) !important;
    }}

    [data-testid="stSidebar"] [data-baseweb="select"] svg {{
        fill: var(--text-muted) !important;
    }}

    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] .stNumberInput input,
    [data-testid="stSidebar"] .stTextArea textarea {{
        background: var(--surface-alt) !important;
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }}

    [data-testid="stSidebar"] .stButton button {{
        background: var(--surface-alt) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
    }}

    [data-testid="stSidebar"] .stButton button:hover {{
        border-color: var(--primary) !important;
    }}

    div[role="listbox"] {{
        background: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
    }}

    div[role="option"] {{
        color: var(--text) !important;
    }}

    div[role="option"][aria-selected="true"] {{
        background: var(--surface-alt) !important;
    }}

    .epm-topbar {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 16px 20px;
        box-shadow: var(--shadow);
        margin-bottom: 16px;
        transition: all 0.25s ease;
    }}

    .epm-kpi {{
        background: linear-gradient(145deg, var(--surface), var(--surface-alt));
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: var(--shadow);
        min-height: 118px;
        transition: all 0.25s ease;
    }}

    .epm-kpi:hover {{
        transform: translateY(-2px);
        border-color: var(--primary);
    }}

    .epm-kpi-title {{
        color: var(--text-muted);
        font-size: 12px;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        font-weight: 600;
        margin-bottom: 8px;
    }}

    .epm-kpi-value {{
        color: var(--text);
        font-size: 30px;
        line-height: 1.1;
        font-weight: 760;
    }}

    .epm-kpi-delta {{
        margin-top: 8px;
        font-size: 13px;
        font-weight: 620;
    }}

    .epm-panel-title {{
        color: var(--text);
        font-size: 16px;
        font-weight: 680;
        margin-bottom: 8px;
    }}

    .epm-right-panel {{
        position: sticky;
        top: 10px;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: var(--shadow);
    }}

    .epm-badge {{
        display: inline-block;
        border-radius: 999px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.02em;
        border: 1px solid var(--border);
        background: var(--surface-alt);
        color: var(--text-muted);
        margin-right: 6px;
        margin-bottom: 6px;
    }}

    .epm-note {{
        color: var(--text-muted);
        font-size: 13px;
    }}
</style>
""",
        unsafe_allow_html=True,
    )


def _chart_palette(theme: str) -> List[str]:
    if theme == "dark":
        return ["#4A9EFF", "#2FC277", "#F0A646", "#FF6B6B", "#79D3FF", "#C7A7FF"]
    return ["#165DFF", "#1F9F5A", "#C68A00", "#D64545", "#0F766E", "#7C3AED"]


def _style_figure(fig, theme: str, height: int = 320):
    t = THEMES[theme]
    fig.update_layout(
        height=height,
        margin=dict(l=14, r=14, t=18, b=14),
        paper_bgcolor=t["surface"],
        plot_bgcolor=t["surface_alt"],
        font=dict(color=t["text"]),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=t["text"])),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor=t["grid"],
        zerolinecolor=t["grid"],
        tickfont=dict(color=t["text_muted"]),
        title_font=dict(color=t["text"]),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=t["grid"],
        zerolinecolor=t["grid"],
        tickfont=dict(color=t["text_muted"]),
        title_font=dict(color=t["text"]),
    )
    return fig


def _kpi_tile(title: str, value: str, delta: str, tone: str = "neutral") -> None:
    tone_color = {
        "good": "var(--success)",
        "warn": "var(--warning)",
        "bad": "var(--critical)",
        "neutral": "var(--text-muted)",
    }
    st.markdown(
        f"""
<div class="epm-kpi">
  <div class="epm-kpi-title">{title}</div>
  <div class="epm-kpi-value">{value}</div>
  <div class="epm-kpi-delta" style="color:{tone_color.get(tone, tone_color['neutral'])};">{delta}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_right_panel(title: str, rows: Dict[str, str], badges: Iterable[str] = ()) -> None:
    st.markdown('<div class="epm-right-panel">', unsafe_allow_html=True)
    st.markdown(f"### {title}")
    if badges:
        st.markdown(
            "".join([f'<span class="epm-badge">{badge}</span>' for badge in badges]),
            unsafe_allow_html=True,
        )
    for label, value in rows.items():
        st.markdown(f"**{label}**  \n{value}")
    st.markdown(
        '<p class="epm-note">Context updates dynamically with filters, scenario choice, and stress assumptions.</p>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def _ensure_defaults(assumptions: Dict) -> None:
    assumptions.setdefault("meta", {})
    assumptions.setdefault("time_horizon", {"start_month": "2026-01", "end_month": "2030-12"})
    assumptions.setdefault("products", [])
    assumptions.setdefault("markets", [])

    if not assumptions["products"]:
        assumptions["products"] = [{"product_id": "product_a", "product_name": "Product A", "unit": "kg"}]
    if not assumptions["markets"]:
        assumptions["markets"] = [{"market_id": "global", "geo": "EU", "activation_month": "2026-01"}]

    assumptions.setdefault("volume", {})
    assumptions["volume"].setdefault("tam", {}).setdefault("per_market_kg", {})
    assumptions["volume"].setdefault("sam_share", {}).setdefault("per_market_pct", {})
    assumptions["volume"].setdefault("som_share", {}).setdefault("per_market_pct", {})
    assumptions["volume"]["som_share"].setdefault("ramp", {}).setdefault("by_market", {})

    assumptions.setdefault("pricing", {})
    assumptions["pricing"].setdefault("list_price", {}).setdefault("by_product", {})
    assumptions["pricing"].setdefault("discounts", {}).setdefault("by_product", {})

    assumptions.setdefault("mix", {})
    assumptions["mix"].setdefault("by_market", {})

    assumptions.setdefault("bom", {})
    assumptions["bom"].setdefault("by_product", {})

    assumptions.setdefault("input_prices", {})
    assumptions["input_prices"].setdefault("by_input", {})

    assumptions.setdefault("opex", {})
    assumptions["opex"].setdefault("fixed", {}).setdefault("by_category", {})
    assumptions["opex"].setdefault("variable", {}).setdefault("by_driver", {})
    assumptions["opex"].setdefault("sales_marketing", {}).setdefault("fixed_base", 0.0)
    assumptions["opex"]["sales_marketing"].setdefault("ramp", {}).setdefault("by_month", {})
    assumptions["opex"]["sales_marketing"].setdefault("cac", {}).setdefault("by_market", {})

    assumptions.setdefault("working_capital", {})
    assumptions["working_capital"].setdefault("dso_days", 60)
    assumptions["working_capital"].setdefault("dio_days", 45)
    assumptions["working_capital"].setdefault("dpo_days", 45)

    assumptions.setdefault("capex", {})
    assumptions["capex"].setdefault("base_monthly", 0.0)
    assumptions["capex"].setdefault("milestones", {}).setdefault("by_month", {})

    assumptions.setdefault("funding", {})
    assumptions["funding"].setdefault("initial_cash", 0.0)
    assumptions["funding"].setdefault("equity", {}).setdefault("by_month", {})
    assumptions["funding"].setdefault("debt", {}).setdefault("interest_rate", 0.0)
    assumptions["funding"]["debt"].setdefault("by_month", {})

    assumptions.setdefault("valuation", {})
    assumptions["valuation"].setdefault("discount_rate", 0.2)
    assumptions["valuation"].setdefault("terminal_growth_rate", 0.03)
    assumptions["valuation"].setdefault("terminal_method", "gordon")
    assumptions["valuation"].setdefault("terminal_multiple", 3.0)
    assumptions["valuation"].setdefault("exit_year", _years_from_assumptions(assumptions)[-1])
    assumptions["valuation"].setdefault("equity", {}).setdefault("ownership_pct", 1.0)
    assumptions["valuation"]["equity"].setdefault("invested", {}).setdefault("by_month", {})

    _sync_structures(assumptions)


def _sync_structures(assumptions: Dict) -> None:
    years = _years_from_assumptions(assumptions)
    jan_months = _january_months(years)

    product_ids = [_clean_id(p.get("product_id"), f"product_{i+1}") for i, p in enumerate(assumptions.get("products", []))]
    market_ids = [_clean_id(m.get("market_id"), f"market_{i+1}") for i, m in enumerate(assumptions.get("markets", []))]

    normalized_products = []
    for i, p in enumerate(assumptions.get("products", [])):
        product_id = product_ids[i]
        normalized_products.append(
            {
                "product_id": product_id,
                "product_name": str(p.get("product_name", product_id)).strip() or product_id,
                "unit": str(p.get("unit", "kg")).strip() or "kg",
            }
        )
    assumptions["products"] = normalized_products

    normalized_markets = []
    for i, m in enumerate(assumptions.get("markets", [])):
        market_id = market_ids[i]
        normalized_markets.append(
            {
                "market_id": market_id,
                "geo": str(m.get("geo", "EU")).strip() or "EU",
                "activation_month": str(m.get("activation_month", f"{years[0]}-01")),
            }
        )
    assumptions["markets"] = normalized_markets

    tam = assumptions["volume"]["tam"]["per_market_kg"]
    sam = assumptions["volume"]["sam_share"]["per_market_pct"]
    som = assumptions["volume"]["som_share"]["per_market_pct"]
    ramp = assumptions["volume"]["som_share"]["ramp"]["by_market"]

    for key in list(tam.keys()):
        if key not in market_ids:
            tam.pop(key, None)
    for key in list(sam.keys()):
        if key not in market_ids:
            sam.pop(key, None)
    for key in list(som.keys()):
        if key not in market_ids:
            som.pop(key, None)
    for key in list(ramp.keys()):
        if key not in market_ids:
            ramp.pop(key, None)

    activation_by_market = {m["market_id"]: m.get("activation_month", f"{years[0]}-01") for m in normalized_markets}
    for market_id in market_ids:
        tam.setdefault(market_id, 1_000_000.0)
        sam.setdefault(market_id, 1.0)
        som.setdefault(market_id, 1.0)
        ramp.setdefault(
            market_id,
            {
                "start_month": activation_by_market.get(market_id, f"{years[0]}-01"),
                "duration_months": 0,
                "curve": "linear",
            },
        )

    list_price = assumptions["pricing"]["list_price"]["by_product"]
    discounts = assumptions["pricing"]["discounts"]["by_product"]
    for key in list(list_price.keys()):
        if key not in product_ids:
            list_price.pop(key, None)
    for key in list(discounts.keys()):
        if key not in product_ids:
            discounts.pop(key, None)
    for product_id in product_ids:
        entry = list_price.setdefault(product_id, {})
        by_month = entry.setdefault("by_month", {})
        fallback = _step_value(by_month, jan_months[0], 1.0)
        for month in jan_months:
            by_month.setdefault(month, fallback)

        discount_entry = discounts.setdefault(product_id, {}).setdefault("by_market", {})
        for market_id in list(discount_entry.keys()):
            if market_id not in market_ids:
                discount_entry.pop(market_id, None)
        for market_id in market_ids:
            discount_entry.setdefault(market_id, {}).setdefault("by_month", {})

    mix_by_market = assumptions["mix"]["by_market"]
    for key in list(mix_by_market.keys()):
        if key not in market_ids:
            mix_by_market.pop(key, None)
    for market_id in market_ids:
        market_mix = mix_by_market.setdefault(market_id, {}).setdefault("by_product", {})
        for key in list(market_mix.keys()):
            if key not in product_ids:
                market_mix.pop(key, None)
        for product_id in product_ids:
            market_mix.setdefault(product_id, {}).setdefault("by_year", {})

        for year in years:
            year_key = str(year)
            shares = [max(0.0, _to_float(market_mix[p]["by_year"].get(year_key), 0.0)) for p in product_ids]
            total_share = sum(shares)
            if total_share <= 0:
                equal_share = 1.0 / max(len(product_ids), 1)
                for product_id in product_ids:
                    market_mix[product_id]["by_year"][year_key] = equal_share
            else:
                for idx, product_id in enumerate(product_ids):
                    market_mix[product_id]["by_year"][year_key] = shares[idx] / total_share

    bom_by_product = assumptions["bom"]["by_product"]
    for key in list(bom_by_product.keys()):
        if key not in product_ids:
            bom_by_product.pop(key, None)
    for product_id in product_ids:
        product_bom = bom_by_product.setdefault(product_id, {})
        inputs = product_bom.setdefault("inputs", [])
        normalized_inputs = []
        for i, item in enumerate(inputs):
            input_id = _clean_id(item.get("input_id"), f"input_{i+1}")
            normalized_inputs.append(
                {
                    "input_id": input_id,
                    "input_name": str(item.get("input_name", input_id)).strip() or input_id,
                    "qty_per_kg": max(0.0, _to_float(item.get("qty_per_kg"), 0.0)),
                    "input_type": str(item.get("input_type", "raw_material")).strip() or "raw_material",
                }
            )
        if not normalized_inputs:
            normalized_inputs = [
                {
                    "input_id": f"rm_{product_id}",
                    "input_name": f"Raw material {product_id}",
                    "qty_per_kg": 1.0,
                    "input_type": "raw_material",
                }
            ]
        qty_total = sum(max(0.0, _to_float(row.get("qty_per_kg"), 0.0)) for row in normalized_inputs)
        if qty_total < 1.0:
            normalized_inputs[0]["qty_per_kg"] = _to_float(normalized_inputs[0].get("qty_per_kg"), 0.0) + (1.0 - qty_total)
        product_bom["inputs"] = normalized_inputs

    input_ids = sorted(
        set(
            str(item["input_id"])
            for product in bom_by_product.values()
            for item in product.get("inputs", [])
            if item.get("input_id")
        )
    )
    input_prices = assumptions["input_prices"]["by_input"]
    for key in list(input_prices.keys()):
        if key not in input_ids:
            input_prices.pop(key, None)
    for input_id in input_ids:
        entry = input_prices.setdefault(input_id, {})
        entry.setdefault("base_price", 0.0)
        by_month = entry.setdefault("by_month", {})
        fallback = _step_value(by_month, jan_months[0], _to_float(entry.get("base_price"), 0.0))
        for month in jan_months:
            by_month.setdefault(month, fallback)

    fixed_categories = assumptions["opex"]["fixed"]["by_category"]
    if not fixed_categories:
        fixed_categories["management_ga"] = {"base_monthly": 0.0, "ramp": {"by_month": {jan_months[0]: 1.0}}}
    for category in fixed_categories.values():
        ramp_by_month = category.setdefault("ramp", {}).setdefault("by_month", {})
        fallback = _step_value(ramp_by_month, jan_months[0], 1.0)
        for month in jan_months:
            ramp_by_month.setdefault(month, fallback)

    capex_milestones = assumptions["capex"]["milestones"]["by_month"]
    for month in jan_months:
        capex_milestones.setdefault(month, _step_value(capex_milestones, month, 0.0))

    equity_by_month = assumptions["funding"]["equity"]["by_month"]
    for month in jan_months:
        equity_by_month.setdefault(month, _step_value(equity_by_month, month, 0.0))

    invested_by_month = assumptions["valuation"]["equity"]["invested"]["by_month"]
    for month in jan_months:
        invested_by_month.setdefault(month, _step_value(equity_by_month, month, 0.0))

    cac_by_market = assumptions["opex"]["sales_marketing"]["cac"]["by_market"]
    for market in list(cac_by_market.keys()):
        if market not in market_ids:
            cac_by_market.pop(market, None)
    for market in market_ids:
        cac_by_market.setdefault(market, 0.0)


def _products_df(assumptions: Dict) -> pd.DataFrame:
    return pd.DataFrame(assumptions.get("products", []), columns=["product_id", "product_name", "unit"])


def _apply_products_df(assumptions: Dict, frame: pd.DataFrame) -> None:
    rows = []
    for i, row in frame.iterrows():
        product_id = _clean_id(row.get("product_id"), f"product_{i+1}")
        rows.append(
            {
                "product_id": product_id,
                "product_name": str(row.get("product_name", product_id)).strip() or product_id,
                "unit": str(row.get("unit", "kg")).strip() or "kg",
            }
        )
    assumptions["products"] = rows


def _markets_df(assumptions: Dict) -> pd.DataFrame:
    return pd.DataFrame(assumptions.get("markets", []), columns=["market_id", "geo", "activation_month"])


def _apply_markets_df(assumptions: Dict, frame: pd.DataFrame) -> None:
    years = _years_from_assumptions(assumptions)
    rows = []
    for i, row in frame.iterrows():
        market_id = _clean_id(row.get("market_id"), f"market_{i+1}")
        rows.append(
            {
                "market_id": market_id,
                "geo": str(row.get("geo", "EU")).strip() or "EU",
                "activation_month": str(row.get("activation_month", f"{years[0]}-01")),
            }
        )
    assumptions["markets"] = rows


def _volume_df(assumptions: Dict) -> pd.DataFrame:
    rows = []
    tam = assumptions["volume"]["tam"]["per_market_kg"]
    sam = assumptions["volume"]["sam_share"]["per_market_pct"]
    som = assumptions["volume"]["som_share"]["per_market_pct"]
    ramp = assumptions["volume"]["som_share"]["ramp"]["by_market"]
    for market in assumptions.get("markets", []):
        market_id = market["market_id"]
        market_ramp = ramp.get(market_id, {})
        rows.append(
            {
                "market_id": market_id,
                "tam_kg": _to_float(tam.get(market_id), 0.0),
                "sam_share": _to_float(sam.get(market_id), 1.0),
                "som_share": _to_float(som.get(market_id), 1.0),
                "ramp_start_month": str(market_ramp.get("start_month", market.get("activation_month", "2026-01"))),
                "ramp_duration_months": _to_int(market_ramp.get("duration_months"), 0),
                "ramp_curve": str(market_ramp.get("curve", "linear")),
            }
        )
    return pd.DataFrame(rows)


def _apply_volume_df(assumptions: Dict, frame: pd.DataFrame) -> None:
    tam = assumptions["volume"]["tam"]["per_market_kg"]
    sam = assumptions["volume"]["sam_share"]["per_market_pct"]
    som = assumptions["volume"]["som_share"]["per_market_pct"]
    ramp = assumptions["volume"]["som_share"]["ramp"]["by_market"]
    for _, row in frame.iterrows():
        market_id = _clean_id(row.get("market_id"), "market")
        tam[market_id] = max(0.0, _to_float(row.get("tam_kg"), 0.0))
        sam[market_id] = min(1.0, max(0.0, _to_float(row.get("sam_share"), 1.0)))
        som[market_id] = min(1.0, max(0.0, _to_float(row.get("som_share"), 1.0)))
        ramp[market_id] = {
            "start_month": str(row.get("ramp_start_month", "2026-01")),
            "duration_months": max(0, _to_int(row.get("ramp_duration_months"), 0)),
            "curve": str(row.get("ramp_curve", "linear")) or "linear",
        }


def _clients_df(assumptions: Dict) -> pd.DataFrame:
    clients = assumptions.get("clients")
    if clients:
        return pd.DataFrame(clients)
    rows = []
    tam = assumptions["volume"]["tam"]["per_market_kg"]
    for market in assumptions.get("markets", []):
        market_id = market["market_id"]
        rows.append(
            {
                "client_id": f"baseline_{market_id}",
                "market_id": market_id,
                "annual_demand_kg": _to_float(tam.get(market_id), 0.0),
                "price_adj_pct": 0.0,
                "active": True,
            }
        )
    return pd.DataFrame(rows)


def _apply_clients_df(assumptions: Dict, frame: pd.DataFrame) -> None:
    valid_markets = {m["market_id"] for m in assumptions.get("markets", [])}
    rows = []
    for i, row in frame.iterrows():
        market_id = _clean_id(row.get("market_id"), "market")
        if market_id not in valid_markets:
            continue
        rows.append(
            {
                "client_id": _clean_id(row.get("client_id"), f"client_{i+1}"),
                "market_id": market_id,
                "annual_demand_kg": max(0.0, _to_float(row.get("annual_demand_kg"), 0.0)),
                "price_adj_pct": max(-0.95, min(2.0, _to_float(row.get("price_adj_pct"), 0.0))),
                "active": bool(row.get("active", True)),
            }
        )
    assumptions["clients"] = rows

    if rows:
        tam_by_market = {market_id: 0.0 for market_id in valid_markets}
        for row in rows:
            if row["active"]:
                tam_by_market[row["market_id"]] += row["annual_demand_kg"]
        if any(value > 0 for value in tam_by_market.values()):
            assumptions["volume"]["tam"]["per_market_kg"].update(tam_by_market)


def _pricing_df(assumptions: Dict) -> pd.DataFrame:
    years = _years_from_assumptions(assumptions)
    jan_months = _january_months(years)
    by_product = assumptions["pricing"]["list_price"]["by_product"]
    rows = []
    for product in assumptions.get("products", []):
        product_id = product["product_id"]
        by_month = by_product.get(product_id, {}).get("by_month", {})
        row = {"product_id": product_id}
        for year, month in zip(years, jan_months):
            row[str(year)] = _step_value(by_month, month, 0.0)
        rows.append(row)
    columns = ["product_id"] + [str(year) for year in years]
    return pd.DataFrame(rows, columns=columns)


def _apply_pricing_df(assumptions: Dict, frame: pd.DataFrame) -> None:
    years = _years_from_assumptions(assumptions)
    by_product = assumptions["pricing"]["list_price"]["by_product"]
    for _, row in frame.iterrows():
        product_id = _clean_id(row.get("product_id"), "product")
        entry = by_product.setdefault(product_id, {})
        by_month = entry.setdefault("by_month", {})
        for year in years:
            by_month[f"{year}-01"] = max(0.0, _to_float(row.get(str(year)), 0.0))


def _mix_df(assumptions: Dict) -> pd.DataFrame:
    years = _years_from_assumptions(assumptions)
    mix_by_market = assumptions["mix"]["by_market"]
    rows = []
    for market in assumptions.get("markets", []):
        market_id = market["market_id"]
        by_product = mix_by_market.get(market_id, {}).get("by_product", {})
        for product in assumptions.get("products", []):
            product_id = product["product_id"]
            row = {"market_id": market_id, "product_id": product_id}
            by_year = by_product.get(product_id, {}).get("by_year", {})
            for year in years:
                row[str(year)] = _to_float(by_year.get(str(year)), 0.0)
            rows.append(row)
    columns = ["market_id", "product_id"] + [str(year) for year in years]
    return pd.DataFrame(rows, columns=columns)


def _apply_mix_df(assumptions: Dict, frame: pd.DataFrame) -> None:
    years = _years_from_assumptions(assumptions)
    mix_by_market = assumptions["mix"]["by_market"]
    for _, row in frame.iterrows():
        market_id = _clean_id(row.get("market_id"), "market")
        product_id = _clean_id(row.get("product_id"), "product")
        by_product = mix_by_market.setdefault(market_id, {}).setdefault("by_product", {})
        by_year = by_product.setdefault(product_id, {}).setdefault("by_year", {})
        for year in years:
            by_year[str(year)] = max(0.0, _to_float(row.get(str(year)), 0.0))

    product_ids = [p["product_id"] for p in assumptions.get("products", [])]
    market_ids = [m["market_id"] for m in assumptions.get("markets", [])]
    for market_id in market_ids:
        by_product = mix_by_market.setdefault(market_id, {}).setdefault("by_product", {})
        for product_id in product_ids:
            by_product.setdefault(product_id, {}).setdefault("by_year", {})
        for year in years:
            year_key = str(year)
            shares = [max(0.0, _to_float(by_product[p]["by_year"].get(year_key), 0.0)) for p in product_ids]
            total_share = sum(shares)
            if total_share <= 0:
                equal = 1.0 / max(len(product_ids), 1)
                for product_id in product_ids:
                    by_product[product_id]["by_year"][year_key] = equal
            else:
                for idx, product_id in enumerate(product_ids):
                    by_product[product_id]["by_year"][year_key] = shares[idx] / total_share


def _bom_df(assumptions: Dict) -> pd.DataFrame:
    rows = []
    for product_id, product in assumptions["bom"]["by_product"].items():
        for item in product.get("inputs", []):
            rows.append(
                {
                    "product_id": product_id,
                    "input_id": item.get("input_id", ""),
                    "input_name": item.get("input_name", ""),
                    "qty_per_kg": _to_float(item.get("qty_per_kg"), 0.0),
                    "input_type": item.get("input_type", "raw_material"),
                }
            )
    return pd.DataFrame(rows, columns=["product_id", "input_id", "input_name", "qty_per_kg", "input_type"])


def _apply_bom_df(assumptions: Dict, frame: pd.DataFrame) -> None:
    product_ids = {p["product_id"] for p in assumptions.get("products", [])}
    by_product: Dict[str, Dict[str, List[Dict]]] = {product_id: {"inputs": []} for product_id in product_ids}
    for i, row in frame.iterrows():
        product_id = _clean_id(row.get("product_id"), "product")
        if product_id not in product_ids:
            continue
        input_id = _clean_id(row.get("input_id"), f"input_{i+1}")
        by_product[product_id]["inputs"].append(
            {
                "input_id": input_id,
                "input_name": str(row.get("input_name", input_id)).strip() or input_id,
                "qty_per_kg": max(0.0, _to_float(row.get("qty_per_kg"), 0.0)),
                "input_type": str(row.get("input_type", "raw_material")).strip() or "raw_material",
            }
        )
    for product_id in list(by_product.keys()):
        if not by_product[product_id]["inputs"]:
            by_product[product_id]["inputs"] = [
                {
                    "input_id": f"rm_{product_id}",
                    "input_name": f"Raw material {product_id}",
                    "qty_per_kg": 1.0,
                    "input_type": "raw_material",
                }
            ]
        qty_total = sum(_to_float(item.get("qty_per_kg"), 0.0) for item in by_product[product_id]["inputs"])
        if qty_total < 1.0:
            by_product[product_id]["inputs"][0]["qty_per_kg"] += 1.0 - qty_total
    assumptions["bom"]["by_product"] = by_product


def _input_prices_df(assumptions: Dict) -> pd.DataFrame:
    years = _years_from_assumptions(assumptions)
    jan_months = _january_months(years)
    name_map: Dict[str, str] = {}
    for product in assumptions["bom"]["by_product"].values():
        for item in product.get("inputs", []):
            input_id = str(item.get("input_id", ""))
            if input_id:
                name_map[input_id] = str(item.get("input_name", input_id))

    rows = []
    by_input = assumptions["input_prices"]["by_input"]
    for input_id, entry in by_input.items():
        row = {
            "input_id": input_id,
            "input_name": name_map.get(input_id, input_id),
            "base_price": _to_float(entry.get("base_price"), 0.0),
        }
        by_month = entry.get("by_month", {})
        for year, month in zip(years, jan_months):
            row[str(year)] = _step_value(by_month, month, _to_float(entry.get("base_price"), 0.0))
        rows.append(row)
    columns = ["input_id", "input_name", "base_price"] + [str(year) for year in years]
    return pd.DataFrame(rows, columns=columns)


def _apply_input_prices_df(assumptions: Dict, frame: pd.DataFrame) -> None:
    years = _years_from_assumptions(assumptions)
    updated: Dict[str, Dict] = {}
    for i, row in frame.iterrows():
        input_id = _clean_id(row.get("input_id"), f"input_{i+1}")
        base_price = max(0.0, _to_float(row.get("base_price"), 0.0))
        entry = {"base_price": base_price, "by_month": {}}
        for year in years:
            entry["by_month"][f"{year}-01"] = max(0.0, _to_float(row.get(str(year)), base_price))
        updated[input_id] = entry
    assumptions["input_prices"]["by_input"] = updated


def _opex_fixed_df(assumptions: Dict) -> pd.DataFrame:
    years = _years_from_assumptions(assumptions)
    rows = []
    for category_id, category in assumptions["opex"]["fixed"]["by_category"].items():
        by_month = category.get("ramp", {}).get("by_month", {})
        row = {"category_id": category_id, "base_monthly": _to_float(category.get("base_monthly"), 0.0)}
        for year in years:
            row[str(year)] = _step_value(by_month, f"{year}-01", 1.0)
        rows.append(row)
    columns = ["category_id", "base_monthly"] + [str(year) for year in years]
    return pd.DataFrame(rows, columns=columns)


def _apply_opex_fixed_df(assumptions: Dict, frame: pd.DataFrame) -> None:
    years = _years_from_assumptions(assumptions)
    updated = {}
    for i, row in frame.iterrows():
        category_id = _clean_id(row.get("category_id"), f"category_{i+1}")
        updated[category_id] = {"base_monthly": max(0.0, _to_float(row.get("base_monthly"), 0.0)), "ramp": {"by_month": {}}}
        for year in years:
            updated[category_id]["ramp"]["by_month"][f"{year}-01"] = max(0.0, _to_float(row.get(str(year)), 1.0))
    assumptions["opex"]["fixed"]["by_category"] = updated


def _capex_df(assumptions: Dict) -> pd.DataFrame:
    years = _years_from_assumptions(assumptions)
    capex = assumptions["capex"]["milestones"]["by_month"]
    row = {"series": "capex_milestones"}
    for year in years:
        row[str(year)] = _step_value(capex, f"{year}-01", 0.0)
    return pd.DataFrame([row], columns=["series"] + [str(year) for year in years])


def _equity_df(assumptions: Dict) -> pd.DataFrame:
    years = _years_from_assumptions(assumptions)
    equity = assumptions["funding"]["equity"]["by_month"]
    row = {"series": "equity_raises"}
    for year in years:
        row[str(year)] = _step_value(equity, f"{year}-01", 0.0)
    return pd.DataFrame([row], columns=["series"] + [str(year) for year in years])


def _apply_capex_equity_df(assumptions: Dict, capex_df: pd.DataFrame, equity_df: pd.DataFrame) -> None:
    years = _years_from_assumptions(assumptions)
    capex_row = capex_df.iloc[0] if len(capex_df) else pd.Series({})
    equity_row = equity_df.iloc[0] if len(equity_df) else pd.Series({})
    for year in years:
        assumptions["capex"]["milestones"]["by_month"][f"{year}-01"] = max(0.0, _to_float(capex_row.get(str(year)), 0.0))
        equity_value = max(0.0, _to_float(equity_row.get(str(year)), 0.0))
        assumptions["funding"]["equity"]["by_month"][f"{year}-01"] = equity_value
        assumptions["valuation"]["equity"]["invested"]["by_month"][f"{year}-01"] = equity_value


def _run_from_assumptions(assumptions: Dict, scenario_id: str = "custom") -> ScenarioResult:
    result = ScenarioResult(scenario_id=scenario_id, description=str(assumptions.get("description", "")))
    validation_errors = validate_assumptions(assumptions)
    if validation_errors:
        result.errors.extend(validation_errors)
        return result

    result.revenue = revenue_engine(assumptions)
    result.errors.extend(result.revenue.errors)
    result.cogs = cogs_engine(assumptions, result.revenue.units_kg)
    result.errors.extend(result.cogs.errors)
    result.opex = opex_engine(assumptions, result.revenue)
    result.errors.extend(result.opex.errors)
    result.working_capital = working_capital_engine(assumptions, result.revenue.revenue_total, result.cogs.total_cogs)
    result.errors.extend(result.working_capital.errors)
    result.cashflow = cashflow_engine(
        assumptions,
        result.revenue.revenue_total,
        result.cogs.total_cogs,
        result.opex.total_opex,
        result.working_capital.delta_wc,
    )
    result.warnings.extend(result.cashflow.funding_gaps)

    units_kg_total = {
        month: sum(kg for (m, _, _), kg in result.revenue.units_kg.items() if m == month)
        for month in result.revenue.revenue_total.keys()
    }
    result.valuation = valuation_engine(
        assumptions,
        result.cashflow.free_cf,
        result.cashflow.ebitda,
        result.cashflow.cash_balance,
        result.cashflow.debt_balance,
        revenue_total=result.revenue.revenue_total,
        cogs_total=result.cogs.total_cogs,
        variable_cogs_total=result.cogs.variable_cogs_total,
        opex_total=result.opex.total_opex,
        variable_opex_total=result.opex.total_variable,
        units_kg_total=units_kg_total,
    )
    result.warnings.extend(result.valuation.warnings)

    result.total_revenue = sum(result.revenue.revenue_total.values())
    result.total_cogs = sum(result.cogs.total_cogs.values())
    result.total_opex = sum(result.opex.total_opex.values())
    result.final_ebitda = list(result.cashflow.ebitda.values())[-1] if result.cashflow.ebitda else 0.0
    result.cumulative_fcf = sum(result.cashflow.free_cf.values())
    result.enterprise_value = result.valuation.enterprise_value
    result.equity_value = result.valuation.equity_value
    result.irr = result.valuation.irr
    result.moic = result.valuation.moic
    return result


@st.cache_data(show_spinner=False)
def _run_file_snapshot(scenario_id: str, assumptions_dir: str) -> Tuple[DashboardSnapshot, object, dict]:
    assumptions = load_scenario_assumptions(scenario_id, Path(assumptions_dir))
    _ensure_defaults(assumptions)
    result = _run_from_assumptions(assumptions, scenario_id=scenario_id)
    if result.errors:
        snapshot = DashboardSnapshot(
            monthly=pd.DataFrame(),
            annual=pd.DataFrame(),
            revenue_by_product=pd.DataFrame(),
            units_by_product=pd.DataFrame(),
            revenue_by_market=pd.DataFrame(),
            cogs_by_input=pd.DataFrame(),
            opex_by_category=pd.DataFrame(),
            pricing_latest=pd.DataFrame(),
            risks=pd.DataFrame(),
        )
    else:
        snapshot = build_snapshot(result, assumptions)
    return snapshot, result, assumptions


def _header(section: str, scenario: str) -> None:
    st.markdown(
        f"""
<div class="epm-topbar">
  <div style="display:flex; justify-content:space-between; align-items:center; gap:16px;">
    <div>
      <div style="font-size:12px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em;">Investor-Focused Enterprise Performance Management</div>
      <div style="font-size:30px; font-weight:760; color:var(--text); line-height:1.1;">{section}</div>
    </div>
    <div style="text-align:right;">
      <div style="color:var(--text-muted); font-size:12px;">Working Scenario</div>
      <div style="font-size:20px; font-weight:740; color:var(--primary);">{scenario.title()}</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _filter_monthly(snapshot: DashboardSnapshot, year_filter: str) -> pd.DataFrame:
    if year_filter == "All" or snapshot.monthly.empty:
        return snapshot.monthly.copy()
    return snapshot.monthly[snapshot.monthly["year"] == int(year_filter)].copy()


def _apply_shocks(
    assumptions: Dict,
    volume_factor: float,
    price_factor: float,
    input_cost_factor: float,
    opex_factor: float,
    capex_factor: float,
) -> Dict:
    shocked = copy.deepcopy(assumptions)
    for market_id in list(shocked["volume"]["tam"]["per_market_kg"].keys()):
        shocked["volume"]["tam"]["per_market_kg"][market_id] *= volume_factor
    for market_id in list(shocked["volume"]["som_share"]["per_market_pct"].keys()):
        new_som = shocked["volume"]["som_share"]["per_market_pct"][market_id] * volume_factor
        shocked["volume"]["som_share"]["per_market_pct"][market_id] = min(1.0, max(0.0, new_som))

    for product in shocked["pricing"]["list_price"]["by_product"].values():
        by_month = product.get("by_month", {})
        for month in list(by_month.keys()):
            by_month[month] = max(0.0, _to_float(by_month[month]) * price_factor)

    for input_item in shocked["input_prices"]["by_input"].values():
        input_item["base_price"] = max(0.0, _to_float(input_item.get("base_price"), 0.0) * input_cost_factor)
        by_month = input_item.get("by_month", {})
        for month in list(by_month.keys()):
            by_month[month] = max(0.0, _to_float(by_month[month], 0.0) * input_cost_factor)

    for category in shocked["opex"]["fixed"]["by_category"].values():
        category["base_monthly"] = max(0.0, _to_float(category.get("base_monthly"), 0.0) * opex_factor)

    sm = shocked["opex"]["sales_marketing"]
    sm["fixed_base"] = max(0.0, _to_float(sm.get("fixed_base"), 0.0) * opex_factor)
    for market_id in list(sm.get("cac", {}).get("by_market", {}).keys()):
        sm["cac"]["by_market"][market_id] = max(0.0, _to_float(sm["cac"]["by_market"][market_id], 0.0) * opex_factor)

    shocked["capex"]["base_monthly"] = max(0.0, _to_float(shocked["capex"].get("base_monthly"), 0.0) * capex_factor)
    for month in list(shocked["capex"]["milestones"]["by_month"].keys()):
        shocked["capex"]["milestones"]["by_month"][month] = max(
            0.0, _to_float(shocked["capex"]["milestones"]["by_month"][month], 0.0) * capex_factor
        )
    return shocked


def _metric_value(result, snapshot: DashboardSnapshot, metric: str) -> float:
    if metric == "Enterprise Value":
        return _to_float(result.enterprise_value, 0.0)
    if metric == "Ending Cash":
        return _to_float(snapshot.monthly["cash_balance"].iloc[-1], 0.0) if not snapshot.monthly.empty else 0.0
    if metric == "EBITDA (Exit Year)":
        return _to_float(snapshot.annual["ebitda"].iloc[-1], 0.0) if not snapshot.annual.empty else 0.0
    return _to_float(result.total_revenue, 0.0)


def _render_overview(snapshot: DashboardSnapshot, result, assumptions: Dict, year_filter: str, theme: str) -> None:
    monthly = _filter_monthly(snapshot, year_filter)
    if monthly.empty:
        st.warning("No monthly data available for the selected time filter.")
        return

    revenue_total = float(monthly["revenue"].sum())
    ebitda_total = float(monthly["ebitda"].sum())
    ebitda_margin = _safe_pct(ebitda_total, revenue_total)
    ending_cash = float(monthly["cash_balance"].iloc[-1])
    previous = snapshot.monthly[snapshot.monthly["year"] < int(monthly["year"].min())] if year_filter != "All" else pd.DataFrame()
    previous_revenue = float(previous["revenue"].sum()) if not previous.empty else revenue_total
    revenue_delta = _safe_pct(revenue_total - previous_revenue, previous_revenue)

    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        _kpi_tile("Revenue", _fmt_currency(revenue_total), f"{revenue_delta:+.1%} vs prior span", "good" if revenue_delta >= 0 else "bad")
    with kpi_cols[1]:
        _kpi_tile("EBITDA Margin", _fmt_pct(ebitda_margin), "Operating quality", "good" if ebitda_margin >= 0.15 else "warn")
    with kpi_cols[2]:
        _kpi_tile("Ending Cash", _fmt_currency(ending_cash), "Liquidity floor", "good" if ending_cash >= 0 else "bad")
    with kpi_cols[3]:
        _kpi_tile("Enterprise Value", _fmt_currency(float(result.enterprise_value)), "Valuation baseline", "neutral")

    left, right = st.columns([4, 1.5], gap="large")
    with left:
        top = st.columns([2, 1], gap="large")
        with top[0]:
            st.markdown('<div class="epm-panel-title">Financial Trajectory (Monthly)</div>', unsafe_allow_html=True)
            trend_df = monthly.melt(
                id_vars=["month"],
                value_vars=["revenue", "cogs", "opex", "ebitda"],
                var_name="metric",
                value_name="amount",
            )
            fig = px.line(trend_df, x="month", y="amount", color="metric", markers=False, color_discrete_sequence=_chart_palette(theme))
            fig = _style_figure(fig, theme, height=340)
            st.plotly_chart(fig, width="stretch")

        with top[1]:
            st.markdown('<div class="epm-panel-title">Revenue Mix by Product</div>', unsafe_allow_html=True)
            fig = px.pie(snapshot.revenue_by_product, names="product", values="revenue", hole=0.58, color_discrete_sequence=_chart_palette(theme))
            fig = _style_figure(fig, theme, height=340)
            st.plotly_chart(fig, width="stretch")

        bottom = st.columns([1, 1], gap="large")
        with bottom[0]:
            st.markdown('<div class="epm-panel-title">Annual Performance Stack</div>', unsafe_allow_html=True)
            annual = snapshot.annual.copy()
            stack = annual.melt(id_vars=["year"], value_vars=["revenue", "cogs", "opex", "ebitda"], var_name="metric", value_name="amount")
            fig = px.bar(stack, x="year", y="amount", color="metric", barmode="group", color_discrete_sequence=_chart_palette(theme))
            fig = _style_figure(fig, theme, height=320)
            st.plotly_chart(fig, width="stretch")

        with bottom[1]:
            st.markdown('<div class="epm-panel-title">Cash and Free Cash Flow</div>', unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=monthly["month"], y=monthly["free_cf"], name="Free CF", marker_color=_chart_palette(theme)[2], opacity=0.65))
            fig.add_trace(
                go.Scatter(x=monthly["month"], y=monthly["cash_balance"], mode="lines", name="Cash balance", line=dict(color=_chart_palette(theme)[0], width=3))
            )
            fig = _style_figure(fig, theme, height=320)
            st.plotly_chart(fig, width="stretch")

        st.markdown('<div class="epm-panel-title">Revenue by Market</div>', unsafe_allow_html=True)
        st.dataframe(
            snapshot.revenue_by_market.assign(
                revenue=lambda df: df["revenue"].map(lambda value: _fmt_currency(float(value))),
                share_pct=lambda df: df["share_pct"].map(lambda value: f"{value * 100:.1f}%"),
            ),
            width="stretch",
            hide_index=True,
        )

    with right:
        top_product = snapshot.revenue_by_product.iloc[0] if not snapshot.revenue_by_product.empty else pd.Series({"product": "n/a", "share_pct": 0.0})
        wc = assumptions.get("working_capital", {})
        _render_right_panel(
            "Executive Context",
            {
                "Model Horizon": f"{assumptions['time_horizon']['start_month']} to {assumptions['time_horizon']['end_month']}",
                "Top Product": f"{top_product.get('product', 'n/a')} ({top_product.get('share_pct', 0.0) * 100:.1f}% share)",
                "Cash Cycle Proxy": f"{_to_float(wc.get('dso_days')) + _to_float(wc.get('dio_days')) - _to_float(wc.get('dpo_days')):.0f} days",
                "Discount Rate": f"{_to_float(assumptions.get('valuation', {}).get('discount_rate'), 0.0) * 100:.1f}%",
                "Terminal Method": str(assumptions.get('valuation', {}).get('terminal_method', 'gordon')).title(),
            },
            badges=[f"IRR {result.irr * 100:.1f}%" if result.irr is not None else "IRR n/a", f"MOIC {result.moic:.2f}x"],
        )


def _render_scenario_lab(assumptions_dir: str, assumptions: Dict, base_result, base_snapshot: DashboardSnapshot, theme: str) -> None:
    rows = []
    for scenario_id in ["conservative", "base", "aggressive"]:
        try:
            scenario_snapshot, scenario_result, _ = _run_file_snapshot(scenario_id, assumptions_dir)
            rows.append(
                {
                    "scenario": scenario_id,
                    "revenue": float(scenario_result.total_revenue),
                    "ebitda": float(scenario_snapshot.annual["ebitda"].sum()) if not scenario_snapshot.annual.empty else 0.0,
                    "ending_cash": float(scenario_snapshot.monthly["cash_balance"].iloc[-1]) if not scenario_snapshot.monthly.empty else 0.0,
                    "enterprise_value": float(scenario_result.enterprise_value),
                    "irr": float(scenario_result.irr) if scenario_result.irr is not None else float("nan"),
                    "moic": float(scenario_result.moic),
                    "status": "ok" if not scenario_result.errors else "error",
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "scenario": scenario_id,
                    "revenue": float("nan"),
                    "ebitda": float("nan"),
                    "ending_cash": float("nan"),
                    "enterprise_value": float("nan"),
                    "irr": float("nan"),
                    "moic": float("nan"),
                    "status": f"error: {exc}",
                }
            )

    rows.append(
        {
            "scenario": "custom",
            "revenue": float(base_result.total_revenue),
            "ebitda": float(base_snapshot.annual["ebitda"].sum()) if not base_snapshot.annual.empty else 0.0,
            "ending_cash": float(base_snapshot.monthly["cash_balance"].iloc[-1]) if not base_snapshot.monthly.empty else 0.0,
            "enterprise_value": float(base_result.enterprise_value),
            "irr": float(base_result.irr) if base_result.irr is not None else float("nan"),
            "moic": float(base_result.moic),
            "status": "working copy",
        }
    )
    scenario_df = pd.DataFrame(rows)

    c1, c2, c3 = st.columns(3)
    with c1:
        _kpi_tile("Best EV", _fmt_currency(scenario_df["enterprise_value"].max(skipna=True)), "Across scenarios", "good")
    with c2:
        worst_cash = scenario_df["ending_cash"].min(skipna=True)
        _kpi_tile("Worst Ending Cash", _fmt_currency(worst_cash), "Downside floor", "warn" if worst_cash >= 0 else "bad")
    with c3:
        spread = scenario_df["enterprise_value"].max(skipna=True) - scenario_df["enterprise_value"].min(skipna=True)
        _kpi_tile("EV Spread", _fmt_currency(spread), "Volatility range", "neutral")

    left, right = st.columns([4, 1.5], gap="large")
    with left:
        metric = st.selectbox("Scenario compare metric", ["revenue", "ebitda", "ending_cash", "enterprise_value", "irr", "moic"], index=3)
        fig = px.bar(scenario_df, x="scenario", y=metric, color="scenario", color_discrete_sequence=_chart_palette(theme))
        fig = _style_figure(fig, theme, height=300)
        st.plotly_chart(fig, width="stretch")

        st.dataframe(
            scenario_df.assign(
                revenue=lambda df: df["revenue"].map(lambda value: _fmt_currency(_to_float(value, 0.0))),
                ebitda=lambda df: df["ebitda"].map(lambda value: _fmt_currency(_to_float(value, 0.0))),
                ending_cash=lambda df: df["ending_cash"].map(lambda value: _fmt_currency(_to_float(value, 0.0))),
                enterprise_value=lambda df: df["enterprise_value"].map(lambda value: _fmt_currency(_to_float(value, 0.0))),
                irr=lambda df: df["irr"].map(lambda value: "n/a" if pd.isna(value) else f"{float(value) * 100:.1f}%"),
                moic=lambda df: df["moic"].map(lambda value: f"{_to_float(value, 0.0):.2f}x"),
            ),
            width="stretch",
            hide_index=True,
        )

        st.markdown('<div class="epm-panel-title">Custom Stress Test</div>', unsafe_allow_html=True)
        controls = st.columns(5)
        with controls[0]:
            volume_factor = st.slider("Volume", min_value=0.7, max_value=1.3, value=1.0, step=0.01)
        with controls[1]:
            price_factor = st.slider("Price", min_value=0.8, max_value=1.2, value=1.0, step=0.01)
        with controls[2]:
            input_cost_factor = st.slider("Input Costs", min_value=0.8, max_value=1.3, value=1.0, step=0.01)
        with controls[3]:
            opex_factor = st.slider("OpEx", min_value=0.8, max_value=1.3, value=1.0, step=0.01)
        with controls[4]:
            capex_factor = st.slider("CapEx", min_value=0.8, max_value=1.5, value=1.0, step=0.01)

        stressed_assumptions = _apply_shocks(
            assumptions,
            volume_factor=volume_factor,
            price_factor=price_factor,
            input_cost_factor=input_cost_factor,
            opex_factor=opex_factor,
            capex_factor=capex_factor,
        )
        stress_result = _run_from_assumptions(stressed_assumptions, scenario_id="stress")
        if stress_result.errors:
            st.error("Stress case generated invalid assumptions. Adjust sliders or fix model inputs.")
            for err in stress_result.errors:
                st.write(f"- {err}")
        else:
            try:
                stress_snapshot = build_snapshot(stress_result, stressed_assumptions)
            except Exception as exc:
                st.error(f"Stress snapshot failed: {type(exc).__name__}: {exc}")
                return
            base_ev = _metric_value(base_result, base_snapshot, "Enterprise Value")
            stress_ev = _metric_value(stress_result, stress_snapshot, "Enterprise Value")
            base_cash = _metric_value(base_result, base_snapshot, "Ending Cash")
            stress_cash = _metric_value(stress_result, stress_snapshot, "Ending Cash")

            metrics = st.columns(2)
            with metrics[0]:
                _kpi_tile(
                    "Stress EV",
                    _fmt_currency(stress_ev),
                    f"{_safe_pct(stress_ev - base_ev, abs(base_ev)):+.1%} vs working case",
                    "warn" if stress_ev >= base_ev * 0.9 else "bad",
                )
            with metrics[1]:
                _kpi_tile(
                    "Stress Ending Cash",
                    _fmt_currency(stress_cash),
                    f"{_safe_pct(stress_cash - base_cash, abs(base_cash) if base_cash != 0 else 1):+.1%} vs working case",
                    "warn" if stress_cash >= 0 else "bad",
                )

            stress_line = pd.DataFrame(
                {"month": base_snapshot.monthly["month"], "Working": base_snapshot.monthly["cash_balance"], "Stress": stress_snapshot.monthly["cash_balance"]}
            ).melt(id_vars=["month"], var_name="scenario", value_name="cash")
            fig = px.line(stress_line, x="month", y="cash", color="scenario", color_discrete_sequence=_chart_palette(theme))
            fig = _style_figure(fig, theme, height=300)
            st.plotly_chart(fig, width="stretch")

            st.markdown('<div class="epm-panel-title">Driver Sensitivity (+/-10%)</div>', unsafe_allow_html=True)
            metric_name = st.selectbox("Sensitivity metric", ["Enterprise Value", "Ending Cash", "EBITDA (Exit Year)", "Total Revenue"])
            base_metric_value = _metric_value(base_result, base_snapshot, metric_name)
            drivers = ["Volume", "Price", "Input Costs", "OpEx", "CapEx"]
            sensitivity_rows = []
            for driver in drivers:
                for direction, factor in [("-10%", 0.9), ("+10%", 1.1)]:
                    kwargs = {
                        "volume_factor": 1.0,
                        "price_factor": 1.0,
                        "input_cost_factor": 1.0,
                        "opex_factor": 1.0,
                        "capex_factor": 1.0,
                    }
                    if driver == "Volume":
                        kwargs["volume_factor"] = factor
                    elif driver == "Price":
                        kwargs["price_factor"] = factor
                    elif driver == "Input Costs":
                        kwargs["input_cost_factor"] = factor
                    elif driver == "OpEx":
                        kwargs["opex_factor"] = factor
                    else:
                        kwargs["capex_factor"] = factor

                    local_assumptions = _apply_shocks(assumptions, **kwargs)
                    local_result = _run_from_assumptions(local_assumptions, scenario_id=f"sens_{driver}_{direction}")
                    if local_result.errors:
                        continue
                    try:
                        local_snapshot = build_snapshot(local_result, local_assumptions)
                    except Exception:
                        continue
                    local_value = _metric_value(local_result, local_snapshot, metric_name)
                    sensitivity_rows.append({"shock": f"{driver} {direction}", "delta": local_value - base_metric_value})

            if sensitivity_rows:
                sensitivity_df = pd.DataFrame(sensitivity_rows).sort_values("delta")
                fig = px.bar(
                    sensitivity_df,
                    x="delta",
                    y="shock",
                    orientation="h",
                    color="delta",
                    color_continuous_scale=[THEMES[theme]["critical"], THEMES[theme]["warning"], THEMES[theme]["success"]],
                )
                fig = _style_figure(fig, theme, height=340)
                fig.update_layout(coloraxis_showscale=False)
                st.plotly_chart(fig, width="stretch")

    with right:
        _render_right_panel(
            "Scenario Readout",
            {
                "Focus": "Downside protection + upside optionality",
                "Stress Controls": "Volume, price, input costs, OpEx, CapEx",
                "Output": "Enterprise value, ending cash, EBITDA, revenue",
                "Method": "Deterministic scenario engine with formula-invariant logic",
            },
            badges=["Investor", "CEO", "CFO"],
        )


def _render_model_inputs(assumptions: Dict, assumptions_dir: str) -> None:
    years = _years_from_assumptions(assumptions)
    st.info(
        "Inputs below are the live model assumptions. You can add/remove clients, products, BOM lines, and financing assumptions, then rerun all views instantly."
    )
    tabs = st.tabs(
        ["Clients & Markets", "Products, Pricing & Mix", "BOM & Input Costs", "OpEx, CapEx & Funding", "Valuation & Sensitivity"]
    )

    with tabs[0]:
        markets_editor = st.data_editor(_markets_df(assumptions), num_rows="dynamic", key="markets_editor")
        volume_editor = st.data_editor(_volume_df(assumptions), num_rows="fixed", key="volume_editor")
        clients_editor = st.data_editor(_clients_df(assumptions), num_rows="dynamic", key="clients_editor")
        if st.button("Apply clients and markets"):
            _apply_markets_df(assumptions, markets_editor)
            _sync_structures(assumptions)
            _apply_volume_df(assumptions, volume_editor)
            _apply_clients_df(assumptions, clients_editor)
            _sync_structures(assumptions)
            st.success("Clients, markets, and demand drivers updated.")
            st.rerun()

    with tabs[1]:
        products_editor = st.data_editor(_products_df(assumptions), num_rows="dynamic", key="products_editor")
        pricing_editor = st.data_editor(_pricing_df(assumptions), num_rows="fixed", key="pricing_editor")
        mix_editor = st.data_editor(_mix_df(assumptions), num_rows="fixed", key="mix_editor")
        if st.button("Apply products, pricing, and mix"):
            _apply_products_df(assumptions, products_editor)
            _sync_structures(assumptions)
            _apply_pricing_df(assumptions, pricing_editor)
            _apply_mix_df(assumptions, mix_editor)
            _sync_structures(assumptions)
            st.success("Product catalog, unit prices, and mix assumptions updated.")
            st.rerun()

    with tabs[2]:
        bom_editor = st.data_editor(_bom_df(assumptions), num_rows="dynamic", key="bom_editor")
        input_price_editor = st.data_editor(_input_prices_df(assumptions), num_rows="dynamic", key="input_prices_editor")
        if st.button("Apply BOM and input costs"):
            _apply_bom_df(assumptions, bom_editor)
            _sync_structures(assumptions)
            _apply_input_prices_df(assumptions, input_price_editor)
            _sync_structures(assumptions)
            st.success("BOM and input-cost assumptions updated.")
            st.rerun()

    with tabs[3]:
        opex_editor = st.data_editor(_opex_fixed_df(assumptions), num_rows="dynamic", key="opex_editor")
        capex_editor = st.data_editor(_capex_df(assumptions), num_rows="fixed", key="capex_editor")
        equity_editor = st.data_editor(_equity_df(assumptions), num_rows="fixed", key="equity_editor")
        c1, c2, c3 = st.columns(3)
        with c1:
            initial_cash = st.number_input("Initial cash (EUR)", min_value=0.0, value=_to_float(assumptions["funding"].get("initial_cash"), 0.0), step=50000.0)
            debt_rate = st.number_input("Debt interest rate", min_value=0.0, max_value=1.0, value=_to_float(assumptions["funding"]["debt"].get("interest_rate"), 0.0), step=0.005)
        with c2:
            dso = st.number_input("DSO (days)", min_value=0, value=int(_to_float(assumptions["working_capital"].get("dso_days"), 60)), step=1)
            dio = st.number_input("DIO (days)", min_value=0, value=int(_to_float(assumptions["working_capital"].get("dio_days"), 45)), step=1)
        with c3:
            dpo = st.number_input("DPO (days)", min_value=0, value=int(_to_float(assumptions["working_capital"].get("dpo_days"), 45)), step=1)
            capex_base = st.number_input("Recurring capex (EUR/month)", min_value=0.0, value=_to_float(assumptions["capex"].get("base_monthly"), 0.0), step=10000.0)

        if st.button("Apply operating and financing assumptions"):
            _apply_opex_fixed_df(assumptions, opex_editor)
            _apply_capex_equity_df(assumptions, capex_editor, equity_editor)
            assumptions["funding"]["initial_cash"] = max(0.0, _to_float(initial_cash, 0.0))
            assumptions["funding"]["debt"]["interest_rate"] = max(0.0, _to_float(debt_rate, 0.0))
            assumptions["working_capital"]["dso_days"] = int(max(0, dso))
            assumptions["working_capital"]["dio_days"] = int(max(0, dio))
            assumptions["working_capital"]["dpo_days"] = int(max(0, dpo))
            assumptions["capex"]["base_monthly"] = max(0.0, _to_float(capex_base, 0.0))
            _sync_structures(assumptions)
            st.success("OpEx, capex, funding, and working-capital assumptions updated.")
            st.rerun()

    with tabs[4]:
        valuation = assumptions.get("valuation", {})
        c1, c2, c3 = st.columns(3)
        with c1:
            discount_rate = st.number_input("Discount rate", min_value=0.01, max_value=0.90, value=_to_float(valuation.get("discount_rate"), 0.2), step=0.005)
            terminal_growth = st.number_input("Terminal growth", min_value=0.0, max_value=0.50, value=_to_float(valuation.get("terminal_growth_rate"), 0.03), step=0.002)
        with c2:
            terminal_method = st.selectbox("Terminal method", ["gordon", "multiple"], index=0 if str(valuation.get("terminal_method", "gordon")) == "gordon" else 1)
            terminal_multiple = st.number_input("Terminal multiple", min_value=0.1, value=_to_float(valuation.get("terminal_multiple"), 3.0), step=0.1)
        with c3:
            exit_year = st.selectbox("Exit year", years, index=len(years) - 1)
            ownership_pct = st.number_input("Investor ownership", min_value=0.01, max_value=1.0, value=_to_float(valuation.get("equity", {}).get("ownership_pct"), 1.0), step=0.01)

        if st.button("Apply valuation assumptions"):
            assumptions["valuation"]["discount_rate"] = _to_float(discount_rate, 0.2)
            assumptions["valuation"]["terminal_growth_rate"] = _to_float(terminal_growth, 0.03)
            assumptions["valuation"]["terminal_method"] = terminal_method
            assumptions["valuation"]["terminal_multiple"] = _to_float(terminal_multiple, 3.0)
            assumptions["valuation"]["exit_year"] = int(exit_year)
            assumptions["valuation"]["equity"]["ownership_pct"] = _to_float(ownership_pct, 1.0)
            _sync_structures(assumptions)
            st.success("Valuation and sensitivity baseline updated.")
            st.rerun()

    st.markdown("---")
    yaml_text = yaml.safe_dump(assumptions, sort_keys=False)
    st.download_button("Download assumptions YAML", yaml_text, file_name="resemis_assumptions_custom.yaml", mime="text/yaml")
    save_cols = st.columns([2, 1])
    with save_cols[0]:
        target_name = st.text_input("Save as scenario file", value="custom_ui.yaml")
    with save_cols[1]:
        if st.button("Save to assumptions directory"):
            target = Path(assumptions_dir) / target_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(yaml_text, encoding="utf-8")
            st.success(f"Saved {target}")


def _render_risk_radar(snapshot: DashboardSnapshot, result, theme: str) -> None:
    risks = snapshot.risks.copy()
    if risks.empty:
        st.info("Risk register is empty for the current assumptions.")
        return
    level_rank = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    risks["rank"] = risks["level"].map(level_rank).fillna(0)
    risks = risks.sort_values(["rank", "risk"], ascending=[False, True])

    c1, c2, c3 = st.columns(3)
    with c1:
        _kpi_tile("Critical Risks", str(int((risks["level"] == "Critical").sum())), "Immediate board attention", "bad")
    with c2:
        _kpi_tile("High Risks", str(int((risks["level"] == "High").sum())), "Monitor weekly", "warn")
    with c3:
        _kpi_tile("Total Risks", str(len(risks)), "Model-derived register", "neutral")

    left, right = st.columns([4, 1.5], gap="large")
    with left:
        level_counts = risks.groupby("level", as_index=False)["risk"].count().rename(columns={"risk": "count"})
        fig = px.bar(level_counts, x="level", y="count", color="level", color_discrete_sequence=_chart_palette(theme))
        fig = _style_figure(fig, theme, height=280)
        st.plotly_chart(fig, width="stretch")
        st.dataframe(risks[["risk", "level", "signal", "mitigation"]], width="stretch", hide_index=True)
    with right:
        highest = risks.iloc[0]
        _render_right_panel(
            "Top Risk",
            {
                "Risk": str(highest["risk"]),
                "Level": str(highest["level"]),
                "Signal": str(highest["signal"]),
                "Mitigation": str(highest["mitigation"]),
                "Enterprise Value": _fmt_currency(float(result.enterprise_value)),
            },
            badges=["Risk Radar"],
        )


def _render_data_room(snapshot: DashboardSnapshot, assumptions: Dict, year_filter: str) -> None:
    tabs = st.tabs(["Monthly", "Annual", "Pricing", "BOM", "Raw YAML"])
    with tabs[0]:
        monthly = _filter_monthly(snapshot, year_filter)
        st.dataframe(monthly, width="stretch", hide_index=True)
        st.download_button("Download monthly CSV", monthly.to_csv(index=False), file_name="resemis_monthly.csv", mime="text/csv")
    with tabs[1]:
        st.dataframe(snapshot.annual, width="stretch", hide_index=True)
        st.download_button("Download annual CSV", snapshot.annual.to_csv(index=False), file_name="resemis_annual.csv", mime="text/csv")
    with tabs[2]:
        st.dataframe(snapshot.pricing_latest, width="stretch", hide_index=True)
        st.download_button("Download pricing CSV", snapshot.pricing_latest.to_csv(index=False), file_name="resemis_pricing.csv", mime="text/csv")
    with tabs[3]:
        bom = _bom_df(assumptions)
        st.dataframe(bom, width="stretch", hide_index=True)
        st.download_button("Download BOM CSV", bom.to_csv(index=False), file_name="resemis_bom.csv", mime="text/csv")
    with tabs[4]:
        st.code(yaml.safe_dump(assumptions, sort_keys=False), language="yaml")


def main() -> None:
    sections = ["Overview", "Scenario Lab", "Model Inputs", "Risk Radar", "Data Room"]
    qp_section = _qp_value("section", "overview").strip().lower()
    qp_theme = _qp_value("theme", "light").strip().lower()
    initial_section = next((item for item in sections if item.lower() == qp_section), "Overview")
    initial_theme = qp_theme if qp_theme in THEMES else "light"

    with st.sidebar:
        st.markdown("## ReSemis EPM")
        section = st.radio("Navigation", sections, index=sections.index(initial_section))
        dark_mode = st.toggle("Dark mode", value=(initial_theme == "dark"))
        scenario_seed = st.selectbox("Scenario seed", ["base", "conservative", "aggressive"], index=0)
        assumptions_dir = st.text_input("Assumptions directory", value="assumptions")
        try:
            seed_assumptions = load_scenario_assumptions(scenario_seed, Path(assumptions_dir))
            _ensure_defaults(seed_assumptions)
            year_values = [str(year) for year in _years_from_assumptions(seed_assumptions)]
        except Exception:
            year_values = ["2026", "2027", "2028", "2029", "2030"]
        year_filter = st.selectbox("Time range", ["All"] + year_values, index=0)
        reload_disk = st.button("Reload scenario from disk")
        reset_edits = st.button("Reset working edits")

    theme = "dark" if dark_mode else "light"
    _set_query(section, theme)
    _apply_theme(theme)

    seed_key = f"{assumptions_dir}|{scenario_seed}"
    if reload_disk or st.session_state.get("assumptions_seed") != seed_key:
        try:
            baseline = load_scenario_assumptions(scenario_seed, Path(assumptions_dir))
            _ensure_defaults(baseline)
        except Exception as exc:
            st.error(f"Failed to load assumptions from {assumptions_dir}: {exc}")
            return
        st.session_state["assumptions_seed"] = seed_key
        st.session_state["baseline_assumptions"] = copy.deepcopy(baseline)
        st.session_state["working_assumptions"] = copy.deepcopy(baseline)

    if "working_assumptions" not in st.session_state:
        st.error("Assumptions are not initialized. Use Reload scenario from disk.")
        return
    if reset_edits:
        st.session_state["working_assumptions"] = copy.deepcopy(st.session_state.get("baseline_assumptions", {}))

    assumptions = st.session_state["working_assumptions"]
    _ensure_defaults(assumptions)
    result = _run_from_assumptions(assumptions, scenario_id=f"ui_{scenario_seed}")
    if result.errors:
        st.error("Model execution failed. Fix assumptions and rerun.")
        for err in result.errors:
            st.write(f"- {err}")
        return
    try:
        snapshot = build_snapshot(result, assumptions)
    except Exception as exc:
        st.error(f"Failed to build dashboard snapshot: {type(exc).__name__}: {exc}")
        st.info("Try `Reload scenario from disk` in the sidebar. If this persists, the active assumptions file is malformed.")
        return
    _header(section, scenario_seed)

    if section == "Overview":
        _render_overview(snapshot, result, assumptions, year_filter, theme)
    elif section == "Scenario Lab":
        _render_scenario_lab(assumptions_dir, assumptions, result, snapshot, theme)
    elif section == "Model Inputs":
        _render_model_inputs(assumptions, assumptions_dir)
    elif section == "Risk Radar":
        _render_risk_radar(snapshot, result, theme)
    else:
        _render_data_room(snapshot, assumptions, year_filter)


if __name__ == "__main__":
    main()
