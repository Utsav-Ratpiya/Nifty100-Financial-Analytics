"""
src/dashboard/pages/06_sectors.py — Nifty 100 Analytics
Sprint 4 / Day 25 deliverable + visual-enhancement pass: a min-market-cap
slider, 4 KPI tiles for the selected sector, and a new ROE distribution
histogram alongside the original bubble chart + median-KPI bar chart.
"""
import os
import sys

import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_universe  # noqa: E402
from theme import animated_title, inject_global_css, section_header  # noqa: E402

st.set_page_config(page_title="Sector Analysis — Nifty 100 Analytics", layout="wide")
inject_global_css()
animated_title("Sector Analysis", icon="\U0001F3ED")

universe = get_universe()
sectors = sorted(universe["broad_sector"].dropna().unique().tolist())
sector = st.selectbox("Sector", sectors)

sector_df_all = universe[universe["broad_sector"] == sector].copy()
sector_df_all = sector_df_all.dropna(subset=["sales", "return_on_equity_pct"])

if sector_df_all.empty:
    st.info("Not enough data to plot this sector.")
    st.stop()

# --- min market-cap slider (new) ---
if "market_cap_crore" in sector_df_all.columns and sector_df_all["market_cap_crore"].notna().any():
    mc_max = float(sector_df_all["market_cap_crore"].max())
    min_mc = st.slider(
        "Minimum market cap (₹ Cr)", min_value=0.0, max_value=round(mc_max, 0), value=0.0, step=max(mc_max / 50, 1.0),
        help="Filter out smaller companies from the chart and KPI tiles below.",
    )
    sector_df = sector_df_all[sector_df_all["market_cap_crore"].fillna(0) >= min_mc]
else:
    sector_df = sector_df_all

if sector_df.empty:
    st.info("No companies clear this market-cap filter — try lowering the slider.")
    st.stop()

# --- 4 KPI tiles for the sector (new) ---
k1, k2, k3, k4 = st.columns(4)
k1.metric("Companies", len(sector_df))
k2.metric("Avg ROE", f"{sector_df['return_on_equity_pct'].mean():.1f}%")
k3.metric("Median D/E", f"{sector_df['debt_to_equity'].median():.2f}" if "debt_to_equity" in sector_df.columns else "N/A")
k4.metric("Avg Composite Score", f"{sector_df['composite_quality_score'].mean():.1f}" if "composite_quality_score" in sector_df.columns and sector_df["composite_quality_score"].notna().any() else "N/A")

st.divider()

col_a, col_b = st.columns([1.2, 1])
with col_a:
    section_header(f"{sector} — Revenue vs ROE (bubble = market cap)")
    fig = px.scatter(
        sector_df, x="sales", y="return_on_equity_pct",
        size=sector_df["market_cap_crore"].clip(lower=1).fillna(1),
        color="sub_sector", hover_name="company_name",
        labels={"sales": "Revenue (₹ Cr)", "return_on_equity_pct": "ROE %", "sub_sector": "Sub-sector"},
        size_max=60,
    )
    fig.update_layout(height=460)
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    section_header("ROE distribution")
    hist_fig = px.histogram(
        sector_df, x="return_on_equity_pct", nbins=15,
        color_discrete_sequence=["#A855F7"],
        labels={"return_on_equity_pct": "ROE %"},
    )
    hist_fig.update_layout(height=460, title=f"{sector} — ROE spread")
    st.plotly_chart(hist_fig, use_container_width=True)

section_header(f"{sector} — median KPIs")
kpi_cols = {
    "return_on_equity_pct": "Median ROE %",
    "roce_pct": "Median ROCE %",
    "net_profit_margin_pct": "Median NPM %",
    "debt_to_equity": "Median D/E",
    "revenue_cagr_5yr": "Median Rev CAGR 5yr %",
    "pe_ratio": "Median P/E",
}
kpi_cols = {k: v for k, v in kpi_cols.items() if k in sector_df.columns}
medians = sector_df[list(kpi_cols.keys())].median(numeric_only=True)
medians.index = [kpi_cols[c] for c in medians.index]

bar_fig = px.bar(x=medians.index, y=medians.values, labels={"x": "", "y": "Median value"},
                  color=medians.values, color_continuous_scale="Tealgrn")
bar_fig.update_layout(height=380, showlegend=False, coloraxis_showscale=False)
st.plotly_chart(bar_fig, use_container_width=True)

with st.expander(f"All companies in {sector}"):
    show_cols = [c for c in ["company_id", "company_name", "sub_sector", "return_on_equity_pct",
                              "debt_to_equity", "sales", "market_cap_crore"] if c in sector_df.columns]
    st.dataframe(sector_df[show_cols], hide_index=True, use_container_width=True)
