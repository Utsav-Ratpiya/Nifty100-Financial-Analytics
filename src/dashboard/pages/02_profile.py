"""
src/dashboard/pages/02_profile.py — Nifty 100 Analytics
Sprint 4 / Day 23 deliverable.
"""
import os
import sys

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_companies, get_pl, get_ratios, get_pros_cons  # noqa: E402

st.set_page_config(page_title="Company Profile — Nifty 100 Analytics", layout="wide")
st.title("Company Profile")

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

# --- 6 KPI tiles (latest year) ---
ratios_fy = ratios[ratios["year"] != "TTM"].copy()
if not ratios_fy.empty:
    ratios_fy["_cal_year"] = ratios_fy["year"].str.split("-").str[1].astype(int)
    latest = ratios_fy.sort_values("_cal_year").iloc[-1]

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("ROE", f"{latest['return_on_equity_pct']:.1f}%" if pd.notna(latest["return_on_equity_pct"]) else "N/A")
    k2.metric("ROCE", f"{latest['roce_pct']:.1f}%" if pd.notna(latest["roce_pct"]) else "N/A")
    k3.metric("Net Profit Margin", f"{latest['net_profit_margin_pct']:.1f}%" if pd.notna(latest["net_profit_margin_pct"]) else "N/A")
    k4.metric("D/E", f"{latest['debt_to_equity']:.2f}" if pd.notna(latest["debt_to_equity"]) else "N/A")
    k5.metric("Revenue CAGR (5yr)", f"{latest['revenue_cagr_5yr']:.1f}%" if pd.notna(latest["revenue_cagr_5yr"]) else latest.get("revenue_cagr_5yr_flag", "N/A"))
    k6.metric("FCF (latest yr)", f"₹{latest['free_cash_flow_cr']:,.0f} Cr" if pd.notna(latest["free_cash_flow_cr"]) else "N/A")
else:
    st.warning("No fiscal-year ratio data available for this company.")

st.divider()

# --- 10-year Revenue and Net Profit bar chart ---
pl_fy = pl[pl["year"] != "TTM"].copy()
if not pl_fy.empty:
    pl_fy["_cal_year"] = pl_fy["year"].str.split("-").str[1].astype(int)
    pl_fy = pl_fy.sort_values("_cal_year").tail(10)

    col_a, col_b = st.columns(2)
    with col_a:
        fig = go.Figure()
        fig.add_bar(x=pl_fy["year"], y=pl_fy["sales"], name="Revenue")
        fig.add_bar(x=pl_fy["year"], y=pl_fy["net_profit"], name="Net Profit")
        fig.update_layout(title="Revenue & Net Profit (₹ Cr)", barmode="group", height=380)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        if not ratios_fy.empty:
            ratios_10 = ratios_fy.sort_values("_cal_year").tail(10)
            fig2 = make_subplots(specs=[[{"secondary_y": True}]])
            fig2.add_trace(go.Scatter(x=ratios_10["year"], y=ratios_10["return_on_equity_pct"], name="ROE %"), secondary_y=False)
            fig2.add_trace(go.Scatter(x=ratios_10["year"], y=ratios_10["roce_pct"], name="ROCE %"), secondary_y=True)
            fig2.update_layout(title="ROE vs ROCE (10yr)", height=380)
            st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("No 10-year P&L history available for this company.")

st.divider()

# --- Pros and cons ---
st.subheader("Pros & Cons")
pc1, pc2 = st.columns(2)
if not pros_cons.empty:
    pros_text = pros_cons.iloc[0].get("pros")
    cons_text = pros_cons.iloc[0].get("cons")
    with pc1:
        st.markdown("**Pros**")
        if pd.notna(pros_text) and str(pros_text).strip():
            for line in str(pros_text).split("\n"):
                if line.strip():
                    st.markdown(f"\u2705 {line.strip()}")
        else:
            st.caption("No pros listed.")
    with pc2:
        st.markdown("**Cons**")
        if pd.notna(cons_text) and str(cons_text).strip():
            for line in str(cons_text).split("\n"):
                if line.strip():
                    st.markdown(f"\u274C {line.strip()}")
        else:
            st.caption("No cons listed.")
else:
    st.caption("No pros/cons data available for this company.")
