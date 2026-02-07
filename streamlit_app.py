from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from models.scenario import run_scenario
from ui.dashboard_data import DashboardSnapshot, build_snapshot


st.set_page_config(
    page_title="ReSemis EPM Dashboard",
    page_icon="R",
    layout="wide",
    initial_sidebar_state="expanded",
)


THEMES: Dict[str, Dict[str, str]] = {
    "light": {
        "bg": "#F4F7FB",
        "surface": "#FFFFFF",
        "surface_alt": "#EEF3FA",
        "text": "#0F172A",
        "text_muted": "#475569",
        "border": "#DCE4EF",
        "primary": "#0B6EF3",
        "success": "#15803D",
        "warning": "#B45309",
        "critical": "#B42318",
        "shadow": "0 8px 24px rgba(15, 23, 42, 0.08)",
    },
    "dark": {
        "bg": "#081021",
        "surface": "#111C33",
        "surface_alt": "#162742",
        "text": "#E6EEF9",
        "text_muted": "#A5B4CF",
        "border": "#2B3D62",
        "primary": "#5AA9FF",
        "success": "#3FBF72",
        "warning": "#F2A93B",
        "critical": "#FF6E6E",
        "shadow": "0 10px 28px rgba(2, 6, 23, 0.45)",
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

    [data-testid="stSidebar"] {{
        background: var(--surface);
        border-right: 1px solid var(--border);
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
        min-height: 120px;
        transition: all 0.25s ease;
    }}

    .epm-kpi:hover {{
        transform: translateY(-2px);
        border-color: var(--primary);
        box-shadow: 0 14px 34px rgba(11, 110, 243, 0.22);
    }}

    .epm-kpi-title {{
        color: var(--text-muted);
        font-size: 12px;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        font-weight: 600;
        margin-bottom: 10px;
    }}

    .epm-kpi-value {{
        color: var(--text);
        font-size: 30px;
        line-height: 1.1;
        font-weight: 700;
    }}

    .epm-kpi-delta {{
        margin-top: 8px;
        font-size: 13px;
        font-weight: 600;
    }}

    .epm-panel {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: var(--shadow);
        transition: all 0.25s ease;
    }}

    .epm-panel:hover {{
        border-color: var(--primary);
    }}

    .epm-panel-title {{
        color: var(--text);
        font-size: 16px;
        font-weight: 650;
        margin-bottom: 6px;
    }}

    .epm-right-panel {{
        position: sticky;
        top: 12px;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: var(--shadow);
        transition: all 0.25s ease;
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
    }}

    .epm-note {{
        color: var(--text-muted);
        font-size: 13px;
    }}
</style>
""",
        unsafe_allow_html=True,
    )


def _fmt_currency(value: float) -> str:
    return f"EUR {value:,.0f}"


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def _kpi_tile(title: str, value: str, delta: str, tone: str = "neutral") -> None:
    color_map = {
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
  <div class="epm-kpi-delta" style="color:{color_map.get(tone, color_map['neutral'])};">{delta}</div>
</div>
""",
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def _load_snapshot(scenario_id: str, assumptions_dir: str) -> Tuple[DashboardSnapshot, object]:
    result = run_scenario(scenario_id, Path(assumptions_dir))
    snapshot = build_snapshot(result)
    return snapshot, result


def _filter_monthly(monthly: pd.DataFrame, year_filter: str) -> pd.DataFrame:
    if year_filter == "All":
        return monthly
    return monthly[monthly["year"] == int(year_filter)].copy()


def _chart_template(theme: str) -> str:
    return "plotly_dark" if theme == "dark" else "plotly_white"


def _chart_colors(theme: str) -> Iterable[str]:
    if theme == "dark":
        return ["#5AA9FF", "#2DD4BF", "#F59E0B", "#F87171", "#A78BFA"]
    return ["#0B6EF3", "#14B8A6", "#F59E0B", "#EF4444", "#8B5CF6"]


def _render_paginated_table(df: pd.DataFrame, key: str, display_columns: Iterable[str]) -> pd.DataFrame:
    page_size = st.selectbox("Rows", [5, 10, 15], index=0, key=f"{key}_size")
    pages = max(1, int((len(df) + page_size - 1) / page_size))
    page = st.number_input("Page", min_value=1, max_value=pages, value=1, step=1, key=f"{key}_page")
    start = (page - 1) * page_size
    end = start + page_size
    slice_df = df.iloc[start:end].copy()
    st.dataframe(slice_df[list(display_columns)], width="stretch", hide_index=True)
    return slice_df


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
    st.markdown('<p class="epm-note">Tip: use filters and table selections to update this context panel.</p>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_overview(snapshot: DashboardSnapshot, result, monthly: pd.DataFrame, theme: str) -> None:
    total_revenue = float(monthly["revenue"].sum())
    total_ebitda = float(monthly["ebitda"].sum())
    margin = (total_ebitda / total_revenue * 100.0) if total_revenue else 0.0
    ending_cash = float(monthly["cash_balance"].iloc[-1]) if len(monthly) else 0.0

    prior_period = snapshot.monthly[snapshot.monthly["year"] < monthly["year"].min()] if len(monthly) else pd.DataFrame()
    prior_revenue = float(prior_period["revenue"].sum()) if len(prior_period) else total_revenue
    revenue_delta = ((total_revenue - prior_revenue) / prior_revenue * 100.0) if prior_revenue else 0.0

    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        _kpi_tile("Total Revenue", _fmt_currency(total_revenue), f"{revenue_delta:+.1f}% vs previous span", "good" if revenue_delta >= 0 else "bad")
    with kpi_cols[1]:
        _kpi_tile("EBITDA Margin", _fmt_pct(margin), "Operational efficiency", "good" if margin >= 0 else "bad")
    with kpi_cols[2]:
        _kpi_tile("Ending Cash", _fmt_currency(ending_cash), "Liquidity position", "good" if ending_cash >= 0 else "warn")
    with kpi_cols[3]:
        _kpi_tile("Enterprise Value", _fmt_currency(float(result.enterprise_value)), "DCF estimate", "neutral")

    content, context = st.columns([4, 1.5], gap="large")

    with content:
        chart_cols = st.columns([2, 1], gap="large")
        with chart_cols[0]:
            st.markdown('<div class="epm-panel-title">Financial Trend (Monthly)</div>', unsafe_allow_html=True)
            trend_df = monthly.melt(
                id_vars=["month"],
                value_vars=["revenue", "cogs", "opex", "ebitda"],
                var_name="metric",
                value_name="amount",
            )
            fig = px.line(
                trend_df,
                x="month",
                y="amount",
                color="metric",
                template=_chart_template(theme),
                color_discrete_sequence=list(_chart_colors(theme)),
            )
            fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")

        with chart_cols[1]:
            st.markdown('<div class="epm-panel-title">Revenue Mix by Product</div>', unsafe_allow_html=True)
            fig = px.pie(
                snapshot.revenue_by_product,
                names="product",
                values="revenue",
                template=_chart_template(theme),
                color_discrete_sequence=list(_chart_colors(theme)),
                hole=0.58,
            )
            fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")

        lower_cols = st.columns([1, 1], gap="large")
        with lower_cols[0]:
            st.markdown('<div class="epm-panel-title">Revenue by Market</div>', unsafe_allow_html=True)
            fig = px.bar(
                snapshot.revenue_by_market,
                x="market",
                y="revenue",
                template=_chart_template(theme),
                color="market",
                color_discrete_sequence=list(_chart_colors(theme)),
            )
            fig.update_layout(showlegend=False, height=300, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")

        with lower_cols[1]:
            st.markdown('<div class="epm-panel-title">Top Team Signals</div>', unsafe_allow_html=True)
            signals = snapshot.teams.sort_values(["risk_level", "performance_score"], ascending=[True, False]).copy()
            st.dataframe(
                signals[["team", "manager", "performance_score", "goal_progress_pct", "risk_level"]],
                width="stretch",
                hide_index=True,
            )

    with context:
        team = st.selectbox("Context Team", snapshot.teams["team"].tolist(), key="ctx_overview_team")
        row = snapshot.teams[snapshot.teams["team"] == team].iloc[0]
        _render_right_panel(
            "Team Context",
            {
                "Manager": row["manager"],
                "Focus Area": row["focus_area"],
                "Performance Score": f"{row['performance_score']:.1f}",
                "Engagement Index": f"{row['engagement_index']:.1f}",
                "Goal Progress": f"{row['goal_progress_pct']:.1f}%",
            },
            badges=[f"Risk: {row['risk_level']}"],
        )


def _render_teams(snapshot: DashboardSnapshot, theme: str) -> None:
    teams = snapshot.teams.copy()
    avg_perf = teams["performance_score"].mean()
    avg_progress = teams["goal_progress_pct"].mean()
    high_risk = int((teams["risk_level"] == "High").sum())

    kpi_cols = st.columns(3)
    with kpi_cols[0]:
        _kpi_tile("Team Performance", f"{avg_perf:.1f}", "Average score", "good")
    with kpi_cols[1]:
        _kpi_tile("Goal Completion", f"{avg_progress:.1f}%", "Across teams", "good" if avg_progress >= 75 else "warn")
    with kpi_cols[2]:
        _kpi_tile("High Risk Teams", str(high_risk), "Needs intervention", "bad" if high_risk else "neutral")

    left, right = st.columns([4, 1.5], gap="large")
    with left:
        st.markdown('<div class="epm-panel-title">Team Score Distribution</div>', unsafe_allow_html=True)
        fig = px.bar(
            teams.sort_values("performance_score", ascending=False),
            x="team",
            y="performance_score",
            color="risk_level",
            template=_chart_template(theme),
            color_discrete_map={"Low": "#16A34A", "Medium": "#F59E0B", "High": "#EF4444"},
        )
        fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")

        st.markdown('<div class="epm-panel-title">Team Table</div>', unsafe_allow_html=True)
        filtered = teams.copy()
        risk_filter = st.multiselect("Risk filter", ["Low", "Medium", "High"], default=["Low", "Medium", "High"])
        filtered = filtered[filtered["risk_level"].isin(risk_filter)]
        page_slice = _render_paginated_table(
            filtered,
            key="teams_table",
            display_columns=["team", "manager", "focus_area", "performance_score", "goal_progress_pct", "risk_level"],
        )
    with right:
        selected = st.selectbox("Selected Team", page_slice["team"].tolist() if len(page_slice) else teams["team"].tolist(), key="team_selected")
        row = teams[teams["team"] == selected].iloc[0]
        _render_right_panel(
            "Manager Detail",
            {
                "Team": row["team"],
                "Manager": row["manager"],
                "Focus Area": row["focus_area"],
                "Performance": f"{row['performance_score']:.1f}",
                "Goal Progress": f"{row['goal_progress_pct']:.1f}%",
                "Engagement": f"{row['engagement_index']:.1f}",
            },
            badges=[f"Risk {row['risk_level']}"],
        )


def _render_individuals(snapshot: DashboardSnapshot, theme: str) -> None:
    people = snapshot.individuals.copy()

    left, right = st.columns([4, 1.5], gap="large")
    with left:
        filter_cols = st.columns(2)
        with filter_cols[0]:
            team = st.selectbox("Team scope", ["All"] + sorted(people["team"].unique().tolist()), key="ind_team_filter")
        with filter_cols[1]:
            status = st.selectbox("Review status", ["All"] + sorted(people["review_status"].unique().tolist()), key="ind_status_filter")

        filtered = people.copy()
        if team != "All":
            filtered = filtered[filtered["team"] == team]
        if status != "All":
            filtered = filtered[filtered["review_status"] == status]

        kpi_cols = st.columns(3)
        with kpi_cols[0]:
            _kpi_tile("People in Scope", str(len(filtered)), "Current filters", "neutral")
        with kpi_cols[1]:
            _kpi_tile("Avg Performance", f"{filtered['performance_score'].mean():.1f}", "Weighted equally", "good")
        with kpi_cols[2]:
            at_risk = int((filtered["flight_risk"] == "High").sum())
            _kpi_tile("Flight Risk High", str(at_risk), "Retention signal", "bad" if at_risk else "neutral")

        st.markdown('<div class="epm-panel-title">Performance vs Potential</div>', unsafe_allow_html=True)
        fig = px.scatter(
            filtered,
            x="performance_score",
            y="potential_score",
            color="flight_risk",
            hover_name="employee",
            template=_chart_template(theme),
            color_discrete_map={"Low": "#16A34A", "Medium": "#F59E0B", "High": "#EF4444"},
        )
        fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")

        st.markdown('<div class="epm-panel-title">Individual Table</div>', unsafe_allow_html=True)
        page_slice = _render_paginated_table(
            filtered.sort_values("performance_score", ascending=False),
            key="individuals_table",
            display_columns=["employee", "team", "role", "performance_score", "potential_score", "review_status", "flight_risk"],
        )

    with right:
        selected = st.selectbox(
            "Selected Employee",
            page_slice["employee"].tolist() if len(page_slice) else people["employee"].tolist(),
            key="employee_selected",
        )
        row = people[people["employee"] == selected].iloc[0]
        _render_right_panel(
            "Employee Context",
            {
                "Role": row["role"],
                "Team": row["team"],
                "Manager": row["manager"],
                "Performance Score": f"{row['performance_score']:.1f}",
                "Potential Score": f"{row['potential_score']:.1f}",
                "Reviews Completed": str(row["reviews_completed"]),
                "Goals Completed": str(row["goals_completed"]),
            },
            badges=[f"Risk {row['flight_risk']}", row["review_status"]],
        )


def _render_goals(snapshot: DashboardSnapshot, theme: str) -> None:
    goals = snapshot.goals.copy()

    left, right = st.columns([4, 1.5], gap="large")
    with left:
        status = st.radio("Status chips", ["All", "On Track", "At Risk", "Completed"], horizontal=True, key="goal_status")
        filtered = goals if status == "All" else goals[goals["status"] == status]

        kpi_cols = st.columns(3)
        with kpi_cols[0]:
            _kpi_tile("Goals in Scope", str(len(filtered)), "Active filters", "neutral")
        with kpi_cols[1]:
            _kpi_tile("Avg Progress", f"{filtered['progress_pct'].mean():.1f}%", "Completion signal", "good")
        with kpi_cols[2]:
            blocked = int((filtered["status"] == "At Risk").sum())
            _kpi_tile("At Risk Goals", str(blocked), "Needs manager action", "bad" if blocked else "neutral")

        charts = st.columns([1, 1], gap="large")
        with charts[0]:
            fig = px.pie(
                filtered.groupby("status", as_index=False)["goal_id"].count().rename(columns={"goal_id": "count"}),
                names="status",
                values="count",
                template=_chart_template(theme),
                color_discrete_map={"On Track": "#0EA5E9", "At Risk": "#EF4444", "Completed": "#16A34A"},
                hole=0.58,
            )
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")
        with charts[1]:
            team_progress = filtered.groupby("team", as_index=False)["progress_pct"].mean().sort_values("progress_pct", ascending=False)
            fig = px.bar(
                team_progress,
                x="team",
                y="progress_pct",
                template=_chart_template(theme),
                color="progress_pct",
                color_continuous_scale="Blues",
            )
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), coloraxis_showscale=False)
            st.plotly_chart(fig, width="stretch")

        page_slice = _render_paginated_table(
            filtered.sort_values("progress_pct", ascending=False),
            key="goals_table",
            display_columns=["goal_id", "owner", "team", "goal", "progress_pct", "status", "due_month"],
        )

    with right:
        selected = st.selectbox("Selected Goal", page_slice["goal_id"].tolist() if len(page_slice) else goals["goal_id"].tolist(), key="goal_selected")
        row = goals[goals["goal_id"] == selected].iloc[0]
        _render_right_panel(
            "Goal Detail",
            {
                "Owner": row["owner"],
                "Team": row["team"],
                "Goal": row["goal"],
                "Progress": f"{row['progress_pct']:.1f}%",
                "Due Month": row["due_month"],
            },
            badges=[row["status"]],
        )


def _render_reviews(snapshot: DashboardSnapshot, theme: str) -> None:
    reviews = snapshot.reviews.copy()

    left, right = st.columns([4, 1.5], gap="large")
    with left:
        kpi_cols = st.columns(3)
        with kpi_cols[0]:
            _kpi_tile("Current Cycle", reviews.iloc[-1]["cycle"], "Latest review cycle", "neutral")
        with kpi_cols[1]:
            completion = reviews.iloc[-1]["completed_reviews"] / (reviews.iloc[-1]["completed_reviews"] + reviews.iloc[-1]["pending_reviews"]) * 100
            _kpi_tile("Completion Rate", f"{completion:.1f}%", "Review throughput", "good" if completion >= 75 else "warn")
        with kpi_cols[2]:
            _kpi_tile("Calibration", f"{reviews.iloc[-1]['calibration_consistency']:.1f}", "Consistency index", "good")

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=reviews["cycle"],
                y=reviews["completed_reviews"],
                name="Completed",
                marker_color="#16A34A",
            )
        )
        fig.add_trace(
            go.Bar(
                x=reviews["cycle"],
                y=reviews["pending_reviews"],
                name="Pending",
                marker_color="#F59E0B",
            )
        )
        fig.update_layout(
            template=_chart_template(theme),
            barmode="group",
            height=320,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, width="stretch")

        st.dataframe(reviews, width="stretch", hide_index=True)

    with right:
        latest = reviews.iloc[-1]
        _render_right_panel(
            "Cycle Context",
            {
                "Cycle": latest["cycle"],
                "Completed": str(int(latest["completed_reviews"])),
                "Pending": str(int(latest["pending_reviews"])),
                "Calibration": f"{latest['calibration_consistency']:.1f}",
            },
            badges=["Review Ops"],
        )


def _render_settings(theme: str) -> None:
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown('<div class="epm-panel-title">Display Preferences</div>', unsafe_allow_html=True)
        st.markdown(
            """
<div class="epm-panel">
  <p><strong>Theme Tokens:</strong> shared semantic variables drive cards, charts, nav, and panel styles.</p>
  <p><strong>Motion:</strong> subtle 250ms transitions are enabled for card hover and theme switch.</p>
  <p><strong>Accessibility:</strong> palette is designed for high contrast in both light and dark modes.</p>
</div>
""",
            unsafe_allow_html=True,
        )
    with right:
        _render_right_panel(
            "Deployment Notes",
            {
                "Recommended Free Hosting": "Streamlit Community Cloud",
                "App Entrypoint": "streamlit_app.py",
                "Branch Strategy": "Use dev branch and PR to main",
            },
            badges=[f"Theme: {theme.title()}"],
        )


def main() -> None:
    sections = ["Overview", "Teams", "Individuals", "Goals", "Reviews", "Settings"]
    qp_section = _qp_value("section", "overview").strip().lower()
    qp_theme = _qp_value("theme", "light").strip().lower()
    initial_section = next((s for s in sections if s.lower() == qp_section), "Overview")
    initial_theme = qp_theme if qp_theme in THEMES else "light"

    with st.sidebar:
        st.markdown("## ReSemis EPM")
        section = st.radio("Navigation", sections, index=sections.index(initial_section))
        dark_mode = st.toggle("Dark mode", value=(initial_theme == "dark"))
        scenario = st.selectbox("Scenario", ["conservative", "base", "aggressive"], index=1)
        assumptions_dir = st.text_input("Assumptions directory", value="assumptions")
        year_filter = st.selectbox("Time range", ["All", "2026", "2027", "2028", "2029", "2030"], index=0)

    theme = "dark" if dark_mode else "light"
    _set_query(section, theme)
    _apply_theme(theme)

    st.markdown(
        f"""
<div class="epm-topbar">
  <div style="display:flex; justify-content:space-between; align-items:center; gap:16px;">
    <div>
      <div style="font-size:13px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em;">Enterprise Performance Management</div>
      <div style="font-size:30px; font-weight:750; color:var(--text); line-height:1.1;">{section}</div>
    </div>
    <div style="text-align:right;">
      <div style="color:var(--text-muted); font-size:12px;">Scenario</div>
      <div style="font-size:20px; font-weight:700; color:var(--primary);">{scenario.title()}</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    snapshot, result = _load_snapshot(scenario, assumptions_dir)
    if result.errors:
        st.error("Scenario execution failed. Check assumptions and engine configuration.")
        for error in result.errors:
            st.write(f"- {error}")
        return

    monthly = _filter_monthly(snapshot.monthly, year_filter)
    if monthly.empty:
        st.warning("No data available for the selected filters.")
        return

    if section == "Overview":
        _render_overview(snapshot, result, monthly, theme)
    elif section == "Teams":
        _render_teams(snapshot, theme)
    elif section == "Individuals":
        _render_individuals(snapshot, theme)
    elif section == "Goals":
        _render_goals(snapshot, theme)
    elif section == "Reviews":
        _render_reviews(snapshot, theme)
    else:
        _render_settings(theme)


if __name__ == "__main__":
    main()

