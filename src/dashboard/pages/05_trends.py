"""
src/dashboard/pages/05_trends.py — Nifty 100 Analytics
Sprint 4 / Day 25 deliverable + visual-enhancement pass: a "years to
show" slider (was a fixed 10yr tail), 3 KPI tiles per selected metric,
and a new YoY % bar chart alongside the original overlay line chart.
"""
import os
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_companies, get_pl, get_ratios  # noqa: E402
from theme import animated_title, inject_global_css, section_header  # noqa: E402

st.set_page_config(page_title="Trend Analysis — Nifty 100 Analytics", layout="wide")
inject_global_css()
animated_title("Trend Analysis", icon="\U0001F4C8")

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

# --- years-to-show slider (new; was a fixed 10yr tail) ---
available_years = max(len(pl), len(ratios)) if not (pl.empty and ratios.empty) else 10
max_years = min(10, available_years) if available_years else 10
years_to_show = st.slider("Years to show", min_value=min(3, max_years), max_value=max(max_years, 3),
                           value=max_years, step=1)

fig = go.Figure()
yoy_records = []
for metric_label in selected_metrics:
    source, col = METRIC_OPTIONS[metric_label]
    frame = pl if source == "pl" else ratios
    if frame.empty or col not in frame.columns:
        continue
    series = frame.sort_values("_cal_year").tail(years_to_show)
    yoy = series[col].pct_change() * 100

    fig.add_trace(go.Scatter(
        x=series["year"], y=series[col], mode="lines+markers", name=metric_label,
        text=[f"{v:+.1f}% YoY" if pd.notna(v) else "" for v in yoy],
        textposition="top center",
    ))
    for yr, chg in zip(series["year"], yoy):
        if pd.notna(chg):
            yoy_records.append({"year": yr, "metric": metric_label, "yoy_pct": chg})

fig.update_layout(title=f"{ticker} — {years_to_show}yr trend", height=480, hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)
st.caption("Hover over a point to see its year-over-year % change.")

# --- 3 KPI tiles for the first selected metric (new) ---
primary_label = selected_metrics[0]
source, col = METRIC_OPTIONS[primary_label]
frame = pl if source == "pl" else ratios
if not frame.empty and col in frame.columns:
    series = frame.sort_values("_cal_year").tail(years_to_show)
    latest_val = series[col].iloc[-1] if not series.empty else None
    first_val = series[col].iloc[0] if not series.empty else None
    yoy_latest = series[col].pct_change().iloc[-1] * 100 if len(series) > 1 else None
    period_cagr = None
    if pd.notna(first_val) and pd.notna(latest_val) and first_val > 0 and len(series) > 1:
        n_periods = len(series) - 1
        period_cagr = ((latest_val / first_val) ** (1 / n_periods) - 1) * 100

    m1, m2, m3 = st.columns(3)
    m1.metric(f"Latest {primary_label}", f"{latest_val:,.1f}" if pd.notna(latest_val) else "N/A")
    m2.metric("Latest YoY change", f"{yoy_latest:+.1f}%" if pd.notna(yoy_latest) else "N/A")
    m3.metric(f"{years_to_show}yr CAGR", f"{period_cagr:.1f}%" if pd.notna(period_cagr) else "N/A")

st.divider()
section_header("Year-over-year % change")
if yoy_records:
    yoy_df = pd.DataFrame(yoy_records)
    bar_fig = px.bar(
        yoy_df, x="year", y="yoy_pct", color="metric", barmode="group",
        labels={"yoy_pct": "YoY %", "year": "Year"},
    )
    bar_fig.update_layout(height=360)
    st.plotly_chart(bar_fig, use_container_width=True)
else:
    st.info("Not enough history to compute year-over-year change for the selected metrics.")
