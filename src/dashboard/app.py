"""
src/dashboard/app.py — Nifty 100 Analytics
Sprint 4 / Day 22-23 deliverable.

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

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "utils"))
from db import get_companies, get_universe  # noqa: E402

st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="\U0001F4C8",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("\U0001F4C8 Nifty 100 Analytics")
st.caption(
    "Fundamentals, screener, peer comparison, sector trends, capital allocation, "
    "and annual reports for 92 Nifty 100 companies. Use the sidebar to navigate."
)

try:
    companies = get_companies()
    universe = get_universe()
    n_companies = len(companies)
    n_sectors = companies["broad_sector"].nunique()
    debt_free = (universe["debt_to_equity"] == 0).sum() if "debt_to_equity" in universe.columns else None

    c1, c2, c3 = st.columns(3)
    c1.metric("Companies tracked", n_companies)
    c2.metric("Sectors", n_sectors)
    if debt_free is not None:
        c3.metric("Debt-free companies", int(debt_free))
except Exception as exc:  # keep the landing page usable even if the DB/build has an issue
    st.warning(f"Could not load summary metrics right now: {exc}")

st.divider()
st.subheader("Screens")

screens = [
    ("Home", "pages/01_home.py", "Portfolio-wide KPI tiles, sector mix, and top-quality companies."),
    ("Company Profile", "pages/02_profile.py", "Search any company for its full fundamental profile."),
    ("Screener", "pages/03_screener.py", "Filter all 92 companies by 10+ metrics, or use a preset."),
    ("Peer Comparison", "pages/04_peers.py", "Compare a company against its peer group with percentile ranks."),
    ("Trend Analysis", "pages/05_trends.py", "Overlay up to 3 metrics for one company across 10 years."),
    ("Sector Analysis", "pages/06_sectors.py", "Bubble chart and median KPIs for any sector."),
    ("Capital Allocation Map", "pages/07_capital.py", "Treemap of all 92 companies by capital allocation pattern."),
    ("Annual Reports", "pages/08_reports.py", "Links to each company's available annual reports."),
]

cols = st.columns(2)
for i, (label, path, desc) in enumerate(screens):
    with cols[i % 2]:
        with st.container(border=True):
            st.page_link(path, label=f"**{label}**", icon="\u27A1\uFE0F")
            st.caption(desc)

st.divider()
st.caption(
    "Simulated datasets (stock_prices, market_cap) are used for illustration. "
    "See each screen for details."
)
