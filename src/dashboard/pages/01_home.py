"""
src/dashboard/pages/01_home.py — Nifty 100 Analytics
Sprint 4 / Day 23 deliverable.
"""
import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_companies, get_universe_for_year  # noqa: E402

st.set_page_config(page_title="Home — Nifty 100 Analytics", layout="wide")
st.title("Home")

years = list(range(2019, 2025))
selected_year = st.sidebar.selectbox("Year", years, index=len(years) - 1)
st.sidebar.caption("All tiles and tables below reflect data as of the selected fiscal year.")

universe = get_universe_for_year(selected_year)
companies = get_companies()

if universe.empty:
    st.warning(f"No data available for {selected_year} yet.")
    st.stop()

# --- 6 summary KPI tiles ---
avg_roe = universe["return_on_equity_pct"].mean()
median_pe = universe["pe_ratio"].median()
median_de = universe["debt_to_equity"].median()
total_companies = len(universe)
median_rev_cagr = universe["revenue_cagr_5yr"].median()
debt_free_count = int((universe["debt_to_equity"] == 0).sum())

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Average ROE", f"{avg_roe:.1f}%" if pd.notna(avg_roe) else "N/A")
c2.metric("Median P/E", f"{median_pe:.1f}x" if pd.notna(median_pe) else "N/A")
c3.metric("Median D/E", f"{median_de:.2f}" if pd.notna(median_de) else "N/A")
c4.metric("Total Companies", total_companies)
c5.metric("Median Rev CAGR (5yr)", f"{median_rev_cagr:.1f}%" if pd.notna(median_rev_cagr) else "N/A")
c6.metric("Debt-Free Companies", debt_free_count)

st.divider()

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Sector breakdown")
    sector_counts = companies["broad_sector"].value_counts().reset_index()
    sector_counts.columns = ["broad_sector", "company_count"]
    fig = px.pie(
        sector_counts, names="broad_sector", values="company_count", hole=0.5,
        title=f"{sector_counts['broad_sector'].nunique()} sectors, {sector_counts['company_count'].sum()} companies",
    )
    fig.update_traces(textinfo="label+value")
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("Top 5 by composite quality score")
    if "composite_quality_score" in universe.columns:
        top5 = (
            universe.dropna(subset=["composite_quality_score"])
            .sort_values("composite_quality_score", ascending=False)
            .head(5)
        )
        display_cols = ["company_id", "company_name", "broad_sector", "composite_quality_score",
                         "return_on_equity_pct", "debt_to_equity"]
        display_cols = [c for c in display_cols if c in top5.columns]
        st.dataframe(
            top5[display_cols].rename(columns={
                "company_id": "Ticker", "company_name": "Company", "broad_sector": "Sector",
                "composite_quality_score": "Composite Score", "return_on_equity_pct": "ROE %",
                "debt_to_equity": "D/E",
            }),
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("Composite quality score not available for this year.")

st.caption(
    "Simulated datasets (stock_prices, market_cap) are used for illustration purposes in this dashboard."
)
