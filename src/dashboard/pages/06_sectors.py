"""
src/dashboard/pages/06_sectors.py — Nifty 100 Analytics
Sprint 4 / Day 25 deliverable.
"""
import os
import sys

import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_universe  # noqa: E402

st.set_page_config(page_title="Sector Analysis — Nifty 100 Analytics", layout="wide")
st.title("Sector Analysis")

universe = get_universe()
sectors = sorted(universe["broad_sector"].dropna().unique().tolist())
sector = st.selectbox("Sector", sectors)

sector_df = universe[universe["broad_sector"] == sector].copy()
sector_df = sector_df.dropna(subset=["sales", "return_on_equity_pct"])

if sector_df.empty:
    st.info("Not enough data to plot this sector.")
    st.stop()

st.subheader(f"{sector} — Revenue vs ROE (bubble = market cap)")
fig = px.scatter(
    sector_df, x="sales", y="return_on_equity_pct",
    size=sector_df["market_cap_crore"].clip(lower=1).fillna(1),
    color="sub_sector", hover_name="company_name",
    labels={"sales": "Revenue (₹ Cr)", "return_on_equity_pct": "ROE %", "sub_sector": "Sub-sector"},
    size_max=60,
)
fig.update_layout(height=520)
st.plotly_chart(fig, use_container_width=True)

st.subheader(f"{sector} — median KPIs")
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

bar_fig = px.bar(x=medians.index, y=medians.values, labels={"x": "", "y": "Median value"})
bar_fig.update_layout(height=380)
st.plotly_chart(bar_fig, use_container_width=True)

with st.expander(f"All companies in {sector}"):
    show_cols = [c for c in ["company_id", "company_name", "sub_sector", "return_on_equity_pct",
                              "debt_to_equity", "sales", "market_cap_crore"] if c in sector_df.columns]
    st.dataframe(sector_df[show_cols], hide_index=True, use_container_width=True)
