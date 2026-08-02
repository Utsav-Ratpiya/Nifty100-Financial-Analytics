"""
src/analytics/radar.py — Nifty 100 Analytics
Sprint 3 / Day 19: radar/polar chart per company, 8 axes, peer group average
overlay. Companies with no peer group get a standalone chart vs the full
Nifty 100 average instead.

All 8 axes are put on a comparable 0-100 scale using the same winsorized
scaling as the composite score (raw ROE% vs raw D/E vs raw CAGR% aren't
comparable on one polar plot otherwise).
"""
from __future__ import annotations

import os
import sqlite3
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "screener"))
from composite_score import _winsorized_scale, _de_score  # noqa: E402
from universe import build_universe  # noqa: E402

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ))
OUT_DIR = os.path.join(BASE_DIR, "reports", "radar_charts")

AXES = ["ROE", "ROCE", "NPM", "D/E (inverted)", "FCF Score", "PAT CAGR 5yr", "Revenue CAGR 5yr", "Composite Score"]


def build_axis_frame(universe: pd.DataFrame) -> pd.DataFrame:
    """0-100 scaled values for all 8 radar axes, one row per company."""
    out = pd.DataFrame(index=universe.index)
    out["company_id"] = universe["company_id"]
    out["ROE"] = _winsorized_scale(universe["return_on_equity_pct"])
    out["ROCE"] = _winsorized_scale(universe["roce_pct"])
    out["NPM"] = _winsorized_scale(universe["net_profit_margin_pct"])
    out["D/E (inverted)"] = _de_score(universe["debt_to_equity"])
    out["FCF Score"] = _winsorized_scale(universe["free_cash_flow_cr"])
    out["PAT CAGR 5yr"] = _winsorized_scale(universe["pat_cagr_5yr"])
    out["Revenue CAGR 5yr"] = _winsorized_scale(universe["revenue_cagr_5yr"])
    out["Composite Score"] = universe["composite_quality_score"]
    return out.set_index("company_id")


def _plot_radar(company_values: list, overlay_values: list, overlay_label: str,
                 title: str, path: str):
    n = len(AXES)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    company_plot = company_values + company_values[:1]
    ax.plot(angles, company_plot, color="#1F4E78", linewidth=2, label="Company")
    ax.fill(angles, company_plot, color="#1F4E78", alpha=0.25)

    overlay_plot = overlay_values + overlay_values[:1]
    ax.plot(angles, overlay_plot, color="#C0392B", linewidth=1.5, linestyle="--", label=overlay_label)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(AXES, fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=9)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def generate_all_radar_charts():
    conn = sqlite3.connect(os.path.join(BASE_DIR, "nifty100.db"))
    universe = build_universe(conn)
    peer_groups = pd.read_sql("SELECT company_id, peer_group_name FROM peer_groups", conn)
    companies = pd.read_sql("SELECT company_id, company_name FROM companies", conn).set_index("company_id")
    conn.close()

    axis_df = build_axis_frame(universe)
    nifty_avg = axis_df.mean(numeric_only=True).tolist()

    peer_map = peer_groups.set_index("company_id")["peer_group_name"].to_dict()
    generated, skipped = 0, 0

    for company_id in axis_df.index:
        row_values = [round(v, 1) if pd.notna(v) else 0 for v in axis_df.loc[company_id].tolist()]
        company_name = companies.loc[company_id, "company_name"] if company_id in companies.index else company_id

        group = peer_map.get(company_id)
        if group is not None:
            peer_ids = [cid for cid, g in peer_map.items() if g == group]
            peer_avg_row = axis_df.loc[axis_df.index.isin(peer_ids)].mean(numeric_only=True)
            overlay_values = [round(v, 1) if pd.notna(v) else 0 for v in peer_avg_row.tolist()]
            overlay_label = f"{group} peer avg"
            title = f"{company_name} ({company_id}) vs {group}"
        else:
            overlay_values = [round(v, 1) for v in nifty_avg]
            overlay_label = "Nifty 100 avg"
            title = f"{company_name} ({company_id}) vs Nifty 100 (no peer group assigned)"

        path = os.path.join(OUT_DIR, f"{company_id}_radar.png")
        try:
            _plot_radar(row_values, overlay_values, overlay_label, title, path)
            generated += 1
        except Exception as e:
            print(f"  skipped {company_id}: {e}")
            skipped += 1

    print(f"radar charts generated: {generated} (skipped: {skipped}) -> {OUT_DIR}")
    return generated, skipped


if __name__ == "__main__":
    generate_all_radar_charts()
