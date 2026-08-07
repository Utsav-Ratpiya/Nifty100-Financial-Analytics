"""
src/dashboard/pages/04_peers.py — Nifty 100 Analytics
Sprint 4 / Day 24 deliverable + visual-enhancement pass: 4 KPI tiles for
the peer group, a percentile-highlight slider, and a new composite-score
bar chart ranking every member alongside the original radar + table.
"""
import os
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_peers, get_universe, _connect  # noqa: E402
from theme import animated_title, inject_global_css, section_header  # noqa: E402

st.set_page_config(page_title="Peer Comparison — Nifty 100 Analytics", layout="wide")
inject_global_css()
animated_title("Peer Comparison", icon="\U0001F91D")

conn = _connect()
groups = pd.read_sql("SELECT DISTINCT peer_group_name FROM peer_groups ORDER BY peer_group_name", conn)
conn.close()

group_name = st.selectbox("Peer group", groups["peer_group_name"].tolist())
peers = get_peers(group_name)

if peers.empty:
    st.info("No peer group assigned — this group has no percentile data yet.")
    st.stop()

universe = get_universe()
peers = peers.merge(
    universe[["company_id", "composite_quality_score"]], on="company_id", how="left"
)
valid_scores = peers["composite_quality_score"].dropna()
if len(valid_scores) > 1:
    peers["composite_percentile"] = (
        peers["composite_quality_score"].rank(method="average", ascending=True) - 1
    ) / (len(valid_scores) - 1)
else:
    peers["composite_percentile"] = 0.5

# --- 4 KPI tiles for the group (new) ---
k1, k2, k3, k4 = st.columns(4)
k1.metric("Members", len(peers))
k2.metric("Avg Composite Score", f"{peers['composite_quality_score'].mean():.1f}" if peers["composite_quality_score"].notna().any() else "N/A")
best_row = peers.dropna(subset=["composite_quality_score"]).sort_values("composite_quality_score", ascending=False)
k3.metric("Top performer", best_row.iloc[0]["company_id"] if not best_row.empty else "N/A")
k4.metric("Benchmark", peers.loc[peers.get("is_benchmark", False) == True, "company_id"].iloc[0] if "is_benchmark" in peers.columns and (peers["is_benchmark"] == True).any() else "N/A")

st.divider()

RADAR_AXES = [
    ("ROE_percentile", "ROE"),
    ("ROCE_percentile", "ROCE"),
    ("Net Profit Margin_percentile", "Net Profit Margin"),
    ("D/E_percentile", "D/E (lower is better)"),
    ("FCF_percentile", "FCF"),
    ("PAT CAGR 5yr_percentile", "PAT CAGR 5yr"),
    ("Revenue CAGR 5yr_percentile", "Revenue CAGR 5yr"),
    ("composite_percentile", "Composite Score"),
]
axes_present = [(col, label) for col, label in RADAR_AXES if col in peers.columns]

company_options = [f"{row.company_id} — {row.company_name}" for row in peers.itertuples()]
selected = st.selectbox("Company", company_options)
selected_ticker = selected.split(" — ")[0]

highlight_pct = st.slider(
    "Highlight members at or above this percentile", min_value=0, max_value=100, value=50, step=5,
    help="Rows in the table below are tinted gold once their composite percentile clears this bar.",
)

col_chart, col_table = st.columns([1, 1.4])

with col_chart:
    company_row = peers[peers["company_id"] == selected_ticker].iloc[0]
    company_values = [round((company_row[col] or 0) * 100, 1) for col, _ in axes_present]
    peer_avg_values = [round((peers[col].mean(skipna=True) or 0) * 100, 1) for col, _ in axes_present]
    labels = [label for _, label in axes_present]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=company_values + company_values[:1], theta=labels + labels[:1],
                                   fill="toself", name=selected_ticker))
    fig.add_trace(go.Scatterpolar(r=peer_avg_values + peer_avg_values[:1], theta=labels + labels[:1],
                                   name=f"{group_name} average", line=dict(dash="dash")))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title=f"{selected_ticker} vs {group_name} peer average (percentile rank, 0-100)",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)

with col_table:
    st.subheader(f"{group_name} — all members")
    display_cols = ["company_id", "company_name", "ROE", "ROCE", "Net Profit Margin", "D/E",
                     "FCF", "PAT CAGR 5yr", "Revenue CAGR 5yr", "composite_quality_score", "composite_percentile", "is_benchmark"]
    display_cols = [c for c in display_cols if c in peers.columns]
    table = peers[display_cols].rename(columns={
        "company_id": "Ticker", "company_name": "Company", "composite_quality_score": "Composite Score",
        "composite_percentile": "Composite Percentile",
    })

    def highlight_row(row):
        styles = [""] * len(row)
        if row.get("Composite Percentile", 0) is not None and pd.notna(row.get("Composite Percentile")) and row.get("Composite Percentile") * 100 >= highlight_pct:
            styles = ["background-color: rgba(245,185,66,0.28)"] * len(row)
        if row.get("is_benchmark"):
            styles = ["background-color: #FFD700"] * len(row)
        return styles

    styled_table = table.drop(columns=["is_benchmark"], errors="ignore")
    styled = table.style.apply(highlight_row, axis=1).format(precision=2, subset=[c for c in styled_table.columns if c not in ("Ticker", "Company")])
    st.dataframe(styled, hide_index=True, use_container_width=True)

st.divider()
section_header("Composite score — all members ranked")
rank_df = peers.dropna(subset=["composite_quality_score"]).sort_values("composite_quality_score", ascending=False)
if not rank_df.empty:
    bar_fig = px.bar(
        rank_df, x="composite_quality_score", y="company_id", orientation="h",
        color="composite_quality_score", color_continuous_scale="Bluered_r",
        labels={"composite_quality_score": "Composite Score", "company_id": ""},
    )
    bar_fig.update_layout(height=max(320, 24 * len(rank_df)), showlegend=False)
    st.plotly_chart(bar_fig, use_container_width=True)
else:
    st.info("No composite scores available for this peer group.")
