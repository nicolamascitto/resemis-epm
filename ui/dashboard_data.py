"""Transform scenario outputs into dashboard-ready dataframes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd


@dataclass
class DashboardSnapshot:
    monthly: pd.DataFrame
    revenue_by_product: pd.DataFrame
    revenue_by_market: pd.DataFrame
    teams: pd.DataFrame
    individuals: pd.DataFrame
    goals: pd.DataFrame
    reviews: pd.DataFrame


def _month_sort(values: List[str]) -> List[str]:
    return sorted(values, key=lambda m: (int(m[:4]), int(m[5:7])))


def _to_monthly_df(result) -> pd.DataFrame:
    months = _month_sort(list(result.revenue.revenue_total.keys()))
    rows = []
    for month in months:
        rows.append(
            {
                "month": month,
                "year": int(month[:4]),
                "revenue": float(result.revenue.revenue_total.get(month, 0.0)),
                "cogs": float(result.cogs.total_cogs.get(month, 0.0)),
                "opex": float(result.opex.total_opex.get(month, 0.0)),
                "ebitda": float(result.cashflow.ebitda.get(month, 0.0)),
                "free_cf": float(result.cashflow.free_cf.get(month, 0.0)),
                "cash_balance": float(result.cashflow.cash_balance.get(month, 0.0)),
            }
        )
    return pd.DataFrame(rows)


def _agg_revenue_by_product(result) -> pd.DataFrame:
    rows = []
    for (_, product), value in result.revenue.revenue_by_product.items():
        rows.append({"product": product, "revenue": float(value)})
    if not rows:
        return pd.DataFrame(columns=["product", "revenue"])
    return pd.DataFrame(rows).groupby("product", as_index=False)["revenue"].sum().sort_values(
        "revenue", ascending=False
    )


def _agg_revenue_by_market(result) -> pd.DataFrame:
    rows = []
    for (_, market), value in result.revenue.revenue_by_market.items():
        rows.append({"market": market, "revenue": float(value)})
    if not rows:
        return pd.DataFrame(columns=["market", "revenue"])
    return pd.DataFrame(rows).groupby("market", as_index=False)["revenue"].sum().sort_values(
        "revenue", ascending=False
    )


def _build_teams(monthly: pd.DataFrame, by_product: pd.DataFrame, by_market: pd.DataFrame) -> pd.DataFrame:
    # Build deterministic "team" entities for manager-facing views.
    team_names = [
        "Commercial Excellence",
        "Market Expansion",
        "Operations Delivery",
        "Finance Control",
        "People & Culture",
    ]
    manager_names = [
        "Giulia Moretti",
        "Luca Bianchi",
        "Marta Rossi",
        "Andrea Romano",
        "Sara Greco",
    ]
    focus = list(by_product["product"].head(2)) + list(by_market["market"].head(2))
    while len(focus) < len(team_names):
        focus.append("portfolio")

    latest = monthly.iloc[-1]
    cash = float(latest["cash_balance"])
    ebitda_margin = float(latest["ebitda"] / latest["revenue"]) if latest["revenue"] else 0.0

    rows = []
    for idx, team in enumerate(team_names):
        score = 65 + idx * 6 + (3 if cash > 0 else -4)
        engagement = 62 + idx * 5 + (5 if ebitda_margin > 0 else -3)
        goal_progress = min(98, 58 + idx * 8)
        risk = "High" if idx == 0 and cash < 0 else ("Medium" if idx % 2 == 0 else "Low")
        rows.append(
            {
                "team": team,
                "manager": manager_names[idx],
                "focus_area": focus[idx],
                "performance_score": float(score),
                "engagement_index": float(engagement),
                "goal_progress_pct": float(goal_progress),
                "risk_level": risk,
            }
        )
    return pd.DataFrame(rows)


def _build_individuals(teams: pd.DataFrame) -> pd.DataFrame:
    first_names = [
        "Lina",
        "Marco",
        "Elena",
        "Davide",
        "Chiara",
        "Federico",
        "Irene",
        "Tommaso",
        "Alice",
        "Riccardo",
        "Francesca",
        "Matteo",
        "Silvia",
        "Paolo",
        "Valentina",
    ]
    last_names = [
        "Esposito",
        "Conti",
        "Marini",
        "De Luca",
        "Costa",
        "Ferrari",
        "Villa",
        "Gallo",
        "Neri",
        "Serra",
        "Martini",
        "Coppola",
        "Grassi",
        "Mancini",
        "Lombardi",
    ]
    roles = ["Analyst", "Senior Analyst", "Manager", "Lead", "Specialist"]
    review_statuses = ["Draft", "In Review", "Finalized"]

    rows = []
    seed = 0
    for _, team in teams.iterrows():
        for i in range(3):
            seed += 1
            perf = 60 + ((seed * 7) % 35)
            potential = 58 + ((seed * 5) % 38)
            utilization = 72 + ((seed * 11) % 20)
            reviews_done = 2 + (seed % 3)
            rows.append(
                {
                    "employee": f"{first_names[seed % len(first_names)]} {last_names[seed % len(last_names)]}",
                    "team": team["team"],
                    "manager": team["manager"],
                    "role": roles[seed % len(roles)],
                    "performance_score": float(perf),
                    "potential_score": float(potential),
                    "utilization_pct": float(utilization),
                    "review_status": review_statuses[seed % len(review_statuses)],
                    "reviews_completed": int(reviews_done),
                    "goals_completed": int(1 + (seed % 4)),
                    "flight_risk": "High" if perf < 68 else ("Medium" if perf < 78 else "Low"),
                }
            )
    return pd.DataFrame(rows)


def _build_goals(individuals: pd.DataFrame) -> pd.DataFrame:
    goals = []
    statuses = ["On Track", "At Risk", "Completed"]
    for idx, row in individuals.iterrows():
        for g in range(2):
            progress = min(100, 35 + (idx * 9 + g * 17) % 70)
            status = "Completed" if progress >= 95 else statuses[(idx + g) % len(statuses)]
            goals.append(
                {
                    "goal_id": f"G-{idx+1:03d}-{g+1}",
                    "owner": row["employee"],
                    "team": row["team"],
                    "goal": "Increase performance impact" if g == 0 else "Improve operating discipline",
                    "progress_pct": float(progress),
                    "status": status,
                    "due_month": f"2026-{(idx + g) % 12 + 1:02d}",
                }
            )
    return pd.DataFrame(goals)


def _build_reviews(individuals: pd.DataFrame) -> pd.DataFrame:
    cycles = ["2026-H1", "2026-H2", "2027-H1"]
    rows = []
    for cycle_index, cycle in enumerate(cycles):
        completed = int(len(individuals) * (0.45 + cycle_index * 0.2))
        pending = max(0, len(individuals) - completed)
        calibration = 72 + cycle_index * 9
        rows.append(
            {
                "cycle": cycle,
                "completed_reviews": completed,
                "pending_reviews": pending,
                "calibration_consistency": float(calibration),
            }
        )
    return pd.DataFrame(rows)


def build_snapshot(result) -> DashboardSnapshot:
    monthly = _to_monthly_df(result)
    by_product = _agg_revenue_by_product(result)
    by_market = _agg_revenue_by_market(result)
    teams = _build_teams(monthly, by_product, by_market)
    individuals = _build_individuals(teams)
    goals = _build_goals(individuals)
    reviews = _build_reviews(individuals)
    return DashboardSnapshot(
        monthly=monthly,
        revenue_by_product=by_product,
        revenue_by_market=by_market,
        teams=teams,
        individuals=individuals,
        goals=goals,
        reviews=reviews,
    )
