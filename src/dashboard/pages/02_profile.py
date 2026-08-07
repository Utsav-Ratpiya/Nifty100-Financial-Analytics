"""
src/dashboard/pages/02_profile.py — Nifty 100 Analytics
Sprint 4 / Day 23 deliverable + visual-enhancement pass: 12 KPI tiles
(was 6), a "years to show" slider driving the trend charts, and a new
cash flow composition chart alongside the original Revenue/Net Profit
and ROE-vs-ROCE charts.
"""
import os
import sys

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_companies, get_cf, get_pl, get_ratios, get_pros_cons  # noqa: E402
from theme import animated_title, inject_global_css, section_header  # noqa: E402

st.set_page_config(page_title="Company Profile — Nifty 100 Analytics", layout="wide")
inject_global_css()
animated_title("Company Profile", icon="\U0001F3E2")

companies = get_companies()
options = [f"{row.company_id} — {row.company_name}" for row in companies.itertuples()]

search = st.selectbox(
    "Search by company name or ticker",
    options=options,
    index=None,
    placeholder="Start typing a company name or ticker (e.g. TCS, HDFC Bank)...",
)

if search is None:
    st.info("Start typing above to look up a company.")
    st.stop()

ticker = search.split(" — ")[0]
company_row = companies[companies["company_id"] == ticker]

if company_row.empty:
    st.error("Ticker not found — please try another")
    st.stop()

company = company_row.iloc[0]
ratios = get_ratios(ticker)
pl = get_pl(ticker)
cf = get_cf(ticker)
pros_cons = get_pros_cons(ticker)

if ratios.empty and pl.empty:
    st.error("Ticker not found — please try another")
    st.stop()

# --- Company card ---
with st.container(border=True):
    st.subheader(f"{company['company_name']} ({ticker})")
    cc1, cc2, cc3 = st.columns(3)
    cc1.markdown(f"**Sector:** {company.get('broad_sector', 'N/A')}")
    cc2.markdown(f"**Sub-sector:** {company.get('sub_sector', 'N/A')}")
    nse_link = company.get("nse_profile")
    cc3.markdown(f"**NSE Profile:** [{ticker}]({nse_link})" if pd.notna(nse_link) else f"**NSE Ticker:** {ticker}")
    about = company.get("about_company")
    if pd.notna(about):
        st.caption(about)

st.divider()

# --- 12 KPI tiles (latest year, was 6) ---
ratios_fy = ratios[ratios["year"] != "TTM"].copy()
if not ratios_fy.empty:
    ratios_fy["_cal_year"] = ratios_fy["year"].str.split("-").str[1].astype(int)
    latest = ratios_fy.sort_values("_cal_year").iloc[-1]

    def _fmt(col, suffix="%", digits=1):
        val = latest.get(col)
        return f"{val:.{digits}f}{suffix}" if pd.notna(val) else "N/A"

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("ROE", _fmt("return_on_equity_pct"))
    k2.metric("ROCE", _fmt("roce_pct"))
    k3.metric("Net Profit Margin", _fmt("net_profit_margin_pct"))
    k4.metric("D/E", _fmt("debt_to_equity", suffix="", digits=2))
    k5.metric("Revenue CAGR (5yr)", _fmt("revenue_cagr_5yr") if pd.notna(latest.get("revenue_cagr_5yr")) else str(latest.get("revenue_cagr_5yr_flag", "N/A")))
    k6.metric("FCF (latest yr)", f"₹{latest['free_cash_flow_cr']:,.0f} Cr" if pd.notna(latest.get("free_cash_flow_cr")) else "N/A")

    k7, k8, k9, k10, k11, k12 = st.columns(6)
    k7.metric("Interest Coverage", _fmt("interest_coverage", suffix="x") if pd.notna(latest.get("interest_coverage")) else str(latest.get("icr_label", "N/A")))
    k8.metric("CapEx Intensity", _fmt("capex_intensity_pct"))
    k9.metric("FCF Conversion", _fmt("fcf_conversion_pct"))
    k10.metric("EPS CAGR (5yr)", _fmt("eps_cagr_5yr") if pd.notna(latest.get("eps_cagr_5yr")) else str(latest.get("eps_cagr_5yr_flag", "N/A")))
    k11.metric("Dividend Payout", _fmt("dividend_payout_ratio_pct"))
    k12.metric("Book Value / Share", f"₹{latest['book_value_per_share']:,.1f}" if pd.notna(latest.get("book_value_per_share")) else "N/A")
else:
    st.warning("No fiscal-year ratio data available for this company.")

st.divider()

# --- years-to-show slider driving the trend charts (was a fixed 10yr tail) ---
pl_fy = pl[pl["year"] != "TTM"].copy()
if not pl_fy.empty:
    pl_fy["_cal_year"] = pl_fy["year"].str.split("-").str[1].astype(int)
    max_years = min(10, len(pl_fy))
    years_to_show = st.slider("Years to show", min_value=min(3, max_years), max_value=max_years,
                               value=max_years, step=1)
    pl_fy = pl_fy.sort_values("_cal_year").tail(years_to_show)

    col_a, col_b = st.columns(2)
    with col_a:
        fig = go.Figure()
        fig.add_bar(x=pl_fy["year"], y=pl_fy["sales"], name="Revenue")
        fig.add_bar(x=pl_fy["year"], y=pl_fy["net_profit"], name="Net Profit")
        fig.update_layout(title=f"Revenue & Net Profit (₹ Cr) — last {years_to_show}yr", barmode="group", height=380)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        if not ratios_fy.empty:
            ratios_n = ratios_fy.sort_values("_cal_year").tail(years_to_show)
            fig2 = make_subplots(specs=[[{"secondary_y": True}]])
            fig2.add_trace(go.Scatter(x=ratios_n["year"], y=ratios_n["return_on_equity_pct"], name="ROE %"), secondary_y=False)
            fig2.add_trace(go.Scatter(x=ratios_n["year"], y=ratios_n["roce_pct"], name="ROCE %"), secondary_y=True)
            fig2.update_layout(title=f"ROE vs ROCE — last {years_to_show}yr", height=380)
            st.plotly_chart(fig2, use_container_width=True)

    # --- new: cash flow composition chart ---
    cf_fy = cf[cf["year"] != "TTM"].copy() if not cf.empty else cf
    if not cf_fy.empty:
        cf_fy["_cal_year"] = cf_fy["year"].str.split("-").str[1].astype(int)
        cf_fy = cf_fy.sort_values("_cal_year").tail(years_to_show)
        section_header("Cash flow composition")
        cf_fig = go.Figure()
        cf_fig.add_bar(x=cf_fy["year"], y=cf_fy["operating_activity"], name="Operating")
        cf_fig.add_bar(x=cf_fy["year"], y=cf_fy["investing_activity"], name="Investing")
        cf_fig.add_bar(x=cf_fy["year"], y=cf_fy["financing_activity"], name="Financing")
        cf_fig.add_trace(go.Scatter(x=cf_fy["year"], y=cf_fy["net_cash_flow"], name="Net Cash Flow",
                                     mode="lines+markers", line=dict(color="#F5B942", width=3)))
        cf_fig.update_layout(title=f"Cash flow by activity (₹ Cr) — last {years_to_show}yr", barmode="relative", height=380)
        st.plotly_chart(cf_fig, use_container_width=True)
else:
    st.info("No 10-year P&L history available for this company.")

st.divider()

# --- Pros and cons (Sprint 5 NLP rule engine — covers all 92 companies,
# ranked by the rule's own confidence score) ---
section_header("Pros & Cons")
pc1, pc2 = st.columns(2)
if not pros_cons.empty:
    pros_rows = pros_cons[pros_cons["type"] == "pro"]
    cons_rows = pros_cons[pros_cons["type"] == "con"]
    with pc1:
        st.markdown("**Pros**")
        if not pros_rows.empty:
            for _, r in pros_rows.iterrows():
                st.markdown(f"\u2705 {r['text']}  \n:gray[confidence: {r['confidence_pct']:.0f}%]")
        else:
            st.caption("No pros listed.")
    with pc2:
        st.markdown("**Cons**")
        if not cons_rows.empty:
            for _, r in cons_rows.iterrows():
                st.markdown(f"\u274C {r['text']}  \n:gray[confidence: {r['confidence_pct']:.0f}%]")
        else:
            st.caption("No cons listed.")
else:
    st.caption("No pros/cons data available for this company.")
