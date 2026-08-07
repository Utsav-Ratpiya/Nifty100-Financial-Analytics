"""
src/dashboard/pages/07_capital.py — Nifty 100 Analytics
Sprint 4 / Day 25 deliverable + visual-enhancement pass: a min-market-cap
slider, 4 KPI tiles, and a new "companies per pattern" bar chart
alongside the original treemap + pattern explorer table.
"""
import os
import sys

import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_universe  # noqa: E402
from theme import animated_title, inject_global_css, section_header  # noqa: E402

st.set_page_config(page_title="Capital Allocation Map — Nifty 100 Analytics", layout="wide")
inject_global_css()
animated_title("Capital Allocation Map", icon="\U0001F4B0")

universe = get_universe()
df_all = universe.dropna(subset=["capital_allocation_label"]).copy()

if df_all.empty:
    st.info("No capital allocation data available.")
    st.stop()

st.caption(
    "Every company's latest fiscal year is classified into one of 8 capital allocation "
    "patterns based on the sign of Operating / Investing / Financing cash flow."
)

# --- min market-cap slider (new) ---
if "market_cap_crore" in df_all.columns and df_all["market_cap_crore"].notna().any():
    mc_max = float(df_all["market_cap_crore"].max())
    min_mc = st.slider(
        "Minimum market cap (₹ Cr)", min_value=0.0, max_value=round(mc_max, 0), value=0.0, step=max(mc_max / 50, 1.0),
    )
    df = df_all[df_all["market_cap_crore"].fillna(0) >= min_mc]
else:
    df = df_all

if df.empty:
    st.info("No companies clear this market-cap filter — try lowering the slider.")
    st.stop()

# --- 4 KPI tiles (new) ---
pattern_counts_all = df["capital_allocation_label"].value_counts()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Companies shown", len(df))
k2.metric("Patterns represented", df["capital_allocation_label"].nunique())
k3.metric("Most common pattern", pattern_counts_all.index[0] if not pattern_counts_all.empty else "N/A")
k4.metric("Avg FCF (₹ Cr)", f"{df['free_cash_flow_cr'].mean():,.0f}" if "free_cash_flow_cr" in df.columns and df["free_cash_flow_cr"].notna().any() else "N/A")

st.divider()

col_a, col_b = st.columns([1.4, 1])
with col_a:
    fig = px.treemap(
        df, path=["capital_allocation_label", "company_id"],
        values=df["market_cap_crore"].clip(lower=1).fillna(1),
        color="capital_allocation_label",
    )
    fig.update_layout(height=520, margin=dict(t=20, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    section_header("Companies per pattern")
    pattern_counts = pattern_counts_all.reset_index()
    pattern_counts.columns = ["Pattern", "Companies"]
    bar_fig = px.bar(
        pattern_counts, x="Companies", y="Pattern", orientation="h",
        color="Companies", color_continuous_scale="Sunset",
    )
    bar_fig.update_layout(height=520, showlegend=False, coloraxis_showscale=False, yaxis_title="")
    st.plotly_chart(bar_fig, use_container_width=True)

st.divider()
section_header("Explore a pattern")
patterns = sorted(df["capital_allocation_label"].unique().tolist())
selected_pattern = st.selectbox("Capital allocation pattern", patterns)

pattern_df = df[df["capital_allocation_label"] == selected_pattern]
st.markdown(f"**{len(pattern_df)} companies** classified as *{selected_pattern}*")

show_cols = [c for c in ["company_id", "company_name", "broad_sector", "free_cash_flow_cr",
                          "cfo_quality_label", "capex_label"] if c in pattern_df.columns]
st.dataframe(
    pattern_df[show_cols].rename(columns={
        "company_id": "Ticker", "company_name": "Company", "broad_sector": "Sector",
        "free_cash_flow_cr": "FCF (Cr)", "cfo_quality_label": "CFO Quality", "capex_label": "CapEx Intensity",
    }),
    hide_index=True, use_container_width=True,
)
