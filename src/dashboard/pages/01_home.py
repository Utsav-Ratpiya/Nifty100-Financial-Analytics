"""
src/dashboard/pages/01_home.py — Nifty 100 Analytics
Sprint 4 / Day 23 deliverable + visual-enhancement pass: 10 KPI tiles
(was 6), a "Top N" slider, and two extra charts (ROE-vs-D/E bubble map,
composite-score distribution) alongside the original pie + top-N table.
"""
import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_companies, get_universe_for_year  # noqa: E402
from theme import animated_title, inject_global_css, section_header  # noqa: E402

st.set_page_config(page_title="Home — Nifty 100 Analytics", layout="wide")
inject_global_css()
animated_title("Home", icon="\U0001F3E0")

years = list(range(2019, 2025))
selected_year = st.sidebar.selectbox("Year", years, index=len(years) - 1)
st.sidebar.caption("All tiles and charts below reflect data as of the selected fiscal year.")

universe = get_universe_for_year(selected_year)
companies = get_companies()

if universe.empty:
    st.warning(f"No data available for {selected_year} yet.")
    st.stop()

# --- 10 summary KPI tiles (was 6) ---
avg_roe = universe["return_on_equity_pct"].mean()
median_pe = universe["pe_ratio"].median()
median_de = universe["debt_to_equity"].median()
total_companies = len(universe)
median_rev_cagr = universe["revenue_cagr_5yr"].median()
debt_free_count = int((universe["debt_to_equity"] == 0).sum())
median_div_yield = universe["dividend_yield_pct"].median() if "dividend_yield_pct" in universe.columns else None
avg_composite = universe["composite_quality_score"].mean() if "composite_quality_score" in universe.columns else None
median_icr = universe["interest_coverage"].median() if "interest_coverage" in universe.columns else None
n_sectors = universe["sub_sector"].nunique() if "sub_sector" in universe.columns else companies["broad_sector"].nunique()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Average ROE", f"{avg_roe:.1f}%" if pd.notna(avg_roe) else "N/A")
c2.metric("Median P/E", f"{median_pe:.1f}x" if pd.notna(median_pe) else "N/A")
c3.metric("Median D/E", f"{median_de:.2f}" if pd.notna(median_de) else "N/A")
c4.metric("Total Companies", total_companies)
c5.metric("Median Rev CAGR (5yr)", f"{median_rev_cagr:.1f}%" if pd.notna(median_rev_cagr) else "N/A")

c6, c7, c8, c9, c10 = st.columns(5)
c6.metric("Debt-Free Companies", debt_free_count)
c7.metric("Median Dividend Yield", f"{median_div_yield:.2f}%" if pd.notna(median_div_yield) else "N/A")
c8.metric("Avg Composite Score", f"{avg_composite:.1f}" if pd.notna(avg_composite) else "N/A")
c9.metric("Median Interest Coverage", f"{median_icr:.1f}x" if pd.notna(median_icr) else "N/A")
c10.metric("Sub-sectors covered", n_sectors)

st.divider()

col_left, col_right = st.columns([1, 1])

with col_left:
    section_header("Sector breakdown")
    sector_counts = companies["broad_sector"].value_counts().reset_index()
    sector_counts.columns = ["broad_sector", "company_count"]
    fig = px.pie(
        sector_counts, names="broad_sector", values="company_count", hole=0.5,
        title=f"{sector_counts['broad_sector'].nunique()} sectors, {sector_counts['company_count'].sum()} companies",
        color_discrete_sequence=px.colors.sequential.Blues_r,
    )
    fig.update_traces(textinfo="label+value")
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    section_header("ROE vs D/E (bubble = market cap)")
    scatter_df = universe.dropna(subset=["return_on_equity_pct", "debt_to_equity"])
    if not scatter_df.empty:
        bubble_fig = px.scatter(
            scatter_df, x="debt_to_equity", y="return_on_equity_pct",
            size=scatter_df["market_cap_crore"].clip(lower=1).fillna(1) if "market_cap_crore" in scatter_df.columns else None,
            color="broad_sector" if "broad_sector" in scatter_df.columns else None,
            hover_name="company_name" if "company_name" in scatter_df.columns else None,
            labels={"debt_to_equity": "D/E", "return_on_equity_pct": "ROE %"},
            size_max=45,
        )
        bubble_fig.update_layout(height=380, legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(bubble_fig, use_container_width=True)
    else:
        st.info("Not enough data to plot ROE vs D/E for this year.")

st.divider()

# --- Top-N slider driving both the table and a distribution chart ---
section_header("Top companies by composite quality score")
if "composite_quality_score" in universe.columns:
    max_n = max(5, min(30, len(universe)))
    top_n = st.slider("Number of companies to show", min_value=5, max_value=max_n, value=min(10, max_n), step=1)

    scored = universe.dropna(subset=["composite_quality_score"])
    topN = scored.sort_values("composite_quality_score", ascending=False).head(top_n)

    col_a, col_b = st.columns([1.3, 1])
    with col_a:
        display_cols = ["company_id", "company_name", "broad_sector", "composite_quality_score",
                         "return_on_equity_pct", "debt_to_equity"]
        display_cols = [c for c in display_cols if c in topN.columns]
        st.dataframe(
            topN[display_cols].rename(columns={
                "company_id": "Ticker", "company_name": "Company", "broad_sector": "Sector",
                "composite_quality_score": "Composite Score", "return_on_equity_pct": "ROE %",
                "debt_to_equity": "D/E",
            }),
            hide_index=True, use_container_width=True,
        )
    with col_b:
        hist_fig = px.histogram(
            scored, x="composite_quality_score", nbins=20,
            color_discrete_sequence=["#22D3EE"],
            labels={"composite_quality_score": "Composite Score"},
        )
        hist_fig.add_vline(x=topN["composite_quality_score"].min(), line_dash="dash", line_color="#F5B942")
        hist_fig.update_layout(height=320, title="Score distribution (gold line = cutoff for the table)")
        st.plotly_chart(hist_fig, use_container_width=True)
else:
    st.info("Composite quality score not available for this year.")

st.caption(
    "Simulated datasets (stock_prices, market_cap) are used for illustration purposes in this dashboard."
)
