"""
src/dashboard/app.py — Nifty 100 Analytics
Sprint 4 / Day 22-23 deliverable. Visual-enhancement pass on top of the
original Sprint 4 build: animated gradient title, a bigger KPI wall, a
live "quality" slider, and two extra charts on the landing screen.

Main Streamlit entry point. Run with:
    streamlit run src/dashboard/app.py
    (or: make dashboard)

Streamlit auto-discovers every file under src/dashboard/pages/ and builds
the sidebar navigation from them (ordered by the 01_.. 08_.. filename
prefixes), so this file itself only needs to set global page config and
render a short landing/overview screen — the 8 screens themselves live in
pages/01_home.py through pages/08_reports.py.
"""
import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "utils"))
from db import get_companies, get_universe  # noqa: E402
from theme import animated_title, inject_global_css, section_header  # noqa: E402

st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="\U0001F4C8",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_global_css()

animated_title(
    "Nifty 100 Analytics",
    icon="\U0001F4C8",
    subtitle=(
        "Fundamentals, screener, peer comparison, sector trends, capital allocation, "
        "and annual reports for 92 Nifty 100 companies. Use the sidebar to navigate."
    ),
)

universe = pd.DataFrame()
companies = pd.DataFrame()
try:
    companies = get_companies()
    universe = get_universe()
    n_companies = len(companies)
    n_sectors = companies["broad_sector"].nunique()
    has_de = "debt_to_equity" in universe.columns
    debt_free = int((universe["debt_to_equity"] == 0).sum()) if has_de else None
    avg_roe = universe["return_on_equity_pct"].mean() if "return_on_equity_pct" in universe.columns else None
    median_pe = universe["pe_ratio"].median() if "pe_ratio" in universe.columns else None
    avg_score = universe["composite_quality_score"].mean() if "composite_quality_score" in universe.columns else None
    total_mcap = universe["market_cap_crore"].sum() if "market_cap_crore" in universe.columns else None
    high_lev = int(universe["high_leverage_flag"].fillna(0).astype(bool).sum()) if "high_leverage_flag" in universe.columns else None

    # --- 8-tile KPI wall (was 3 tiles) ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Companies tracked", n_companies)
    c2.metric("Sectors", n_sectors)
    c3.metric("Debt-free companies", debt_free if debt_free is not None else "N/A")
    c4.metric("High-leverage flags", high_lev if high_lev is not None else "N/A")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Average ROE", f"{avg_roe:.1f}%" if pd.notna(avg_roe) else "N/A")
    c6.metric("Median P/E", f"{median_pe:.1f}x" if pd.notna(median_pe) else "N/A")
    c7.metric("Avg composite score", f"{avg_score:.1f}" if pd.notna(avg_score) else "N/A")
    c8.metric("Total market cap", f"₹{total_mcap/1e5:,.1f} L Cr" if pd.notna(total_mcap) else "N/A")
except Exception as exc:  # keep the landing page usable even if the DB/build has an issue
    st.warning(f"Could not load summary metrics right now: {exc}")

st.divider()

# --- live quality-score slider feeding two charts ---
if not universe.empty and "composite_quality_score" in universe.columns:
    section_header("Explore the universe by composite quality score")
    lo, hi = float(universe["composite_quality_score"].min(skipna=True) or 0), float(
        universe["composite_quality_score"].max(skipna=True) or 100
    )
    threshold = st.slider(
        "Minimum composite quality score",
        min_value=round(lo, 1), max_value=round(hi, 1), value=round(lo, 1), step=0.5,
        help="Drag to see how many companies — and which sectors — clear this quality bar.",
    )
    filtered = universe[universe["composite_quality_score"] >= threshold]
    st.caption(f"**{len(filtered)}** of {len(universe)} companies score at or above {threshold:.1f}.")

    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.markdown("**Sector breakdown**")
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
        st.markdown(f"**Sector mix above the {threshold:.1f} quality bar**")
        if not filtered.empty:
            bar_counts = filtered["broad_sector"].value_counts().reset_index()
            bar_counts.columns = ["broad_sector", "company_count"]
            bar_fig = px.bar(
                bar_counts, x="company_count", y="broad_sector", orientation="h",
                color="company_count", color_continuous_scale="Tealgrn",
            )
            bar_fig.update_layout(height=380, yaxis_title="", xaxis_title="Companies", showlegend=False)
            st.plotly_chart(bar_fig, use_container_width=True)
        else:
            st.info("No companies clear this quality bar — try lowering the slider.")

    st.divider()
    section_header("Top 10 by composite quality score")
    top10 = filtered.dropna(subset=["composite_quality_score"]).sort_values(
        "composite_quality_score", ascending=False
    ).head(10)
    display_cols = ["company_id", "company_name", "broad_sector", "composite_quality_score",
                     "return_on_equity_pct", "debt_to_equity", "pe_ratio"]
    display_cols = [c for c in display_cols if c in top10.columns]
    if not top10.empty:
        st.dataframe(
            top10[display_cols].rename(columns={
                "company_id": "Ticker", "company_name": "Company", "broad_sector": "Sector",
                "composite_quality_score": "Composite Score", "return_on_equity_pct": "ROE %",
                "debt_to_equity": "D/E", "pe_ratio": "P/E",
            }),
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("No companies to show at this threshold.")

st.divider()
section_header("Screens")

screens = [
    ("Home", "pages/01_home.py", "Portfolio-wide KPI tiles, sector mix, and top-quality companies.", "\U0001F3E0"),
    ("Company Profile", "pages/02_profile.py", "Search any company for its full fundamental profile.", "\U0001F3E2"),
    ("Screener", "pages/03_screener.py", "Filter all 92 companies by 13+ metrics, or use a preset.", "\U0001F50D"),
    ("Peer Comparison", "pages/04_peers.py", "Compare a company against its peer group with percentile ranks.", "\U0001F91D"),
    ("Trend Analysis", "pages/05_trends.py", "Overlay up to 3 metrics for one company across up to 10 years.", "\U0001F4C8"),
    ("Sector Analysis", "pages/06_sectors.py", "Bubble chart and median KPIs for any sector.", "\U0001F3ED"),
    ("Capital Allocation Map", "pages/07_capital.py", "Treemap of all 92 companies by capital allocation pattern.", "\U0001F4B0"),
    ("Annual Reports", "pages/08_reports.py", "Links to each company's available annual reports.", "\U0001F4C4"),
]

cols = st.columns(2)
for i, (label, path, desc, icon) in enumerate(screens):
    with cols[i % 2]:
        with st.container(border=True):
            st.page_link(path, label=f"{icon} **{label}**", icon="\u27A1\uFE0F")
            st.caption(desc)

st.divider()
st.caption(
    "Simulated datasets (stock_prices, market_cap) are used for illustration. "
    "See each screen for details."
)
