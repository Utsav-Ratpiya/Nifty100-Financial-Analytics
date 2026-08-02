"""
src/dashboard/pages/05_trends.py — Nifty 100 Analytics
Sprint 4 / Day 25 deliverable.
"""
import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_companies, get_pl, get_ratios  # noqa: E402

st.set_page_config(page_title="Trend Analysis — Nifty 100 Analytics", layout="wide")
st.title("Trend Analysis")

companies = get_companies()
options = [f"{row.company_id} — {row.company_name}" for row in companies.itertuples()]
search = st.selectbox("Company", options, index=None, placeholder="Search by company name or ticker...")

if search is None:
    st.info("Search for a company above to see its trend chart.")
    st.stop()

ticker = search.split(" — ")[0]

METRIC_OPTIONS = {
    "Revenue (₹ Cr)": ("pl", "sales"),
    "Net Profit (₹ Cr)": ("pl", "net_profit"),
    "ROE %": ("ratios", "return_on_equity_pct"),
    "ROCE %": ("ratios", "roce_pct"),
    "Net Profit Margin %": ("ratios", "net_profit_margin_pct"),
    "Operating Profit Margin %": ("ratios", "operating_profit_margin_pct"),
    "Debt-to-Equity": ("ratios", "debt_to_equity"),
    "Free Cash Flow (₹ Cr)": ("ratios", "free_cash_flow_cr"),
    "Asset Turnover": ("ratios", "asset_turnover"),
    "EPS": ("pl", "eps"),
}

selected_metrics = st.multiselect(
    "Metrics to overlay (up to 3)", list(METRIC_OPTIONS.keys()),
    default=["Revenue (₹ Cr)", "Net Profit (₹ Cr)"], max_selections=3,
)

if not selected_metrics:
    st.info("Pick at least one metric.")
    st.stop()

pl = get_pl(ticker)
ratios = get_ratios(ticker)

pl = pl[pl["year"] != "TTM"].copy()
ratios = ratios[ratios["year"] != "TTM"].copy()
if pl.empty and ratios.empty:
    st.error("Ticker not found — please try another")
    st.stop()

pl["_cal_year"] = pl["year"].str.split("-").str[1].astype(int) if not pl.empty else None
ratios["_cal_year"] = ratios["year"].str.split("-").str[1].astype(int) if not ratios.empty else None

fig = go.Figure()
for metric_label in selected_metrics:
    source, col = METRIC_OPTIONS[metric_label]
    frame = pl if source == "pl" else ratios
    if frame.empty or col not in frame.columns:
        continue
    series = frame.sort_values("_cal_year").tail(10)
    yoy = series[col].pct_change() * 100

    fig.add_trace(go.Scatter(
        x=series["year"], y=series[col], mode="lines+markers", name=metric_label,
        text=[f"{v:+.1f}% YoY" if pd.notna(v) else "" for v in yoy],
        textposition="top center",
    ))

fig.update_layout(title=f"{ticker} — 10 year trend", height=520, hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)
st.caption("Hover over a point to see its year-over-year % change.")
