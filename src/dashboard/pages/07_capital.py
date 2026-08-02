"""
src/dashboard/pages/07_capital.py — Nifty 100 Analytics
Sprint 4 / Day 25 deliverable.
"""
import os
import sys

import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_universe  # noqa: E402

st.set_page_config(page_title="Capital Allocation Map — Nifty 100 Analytics", layout="wide")
st.title("Capital Allocation Map")

universe = get_universe()
df = universe.dropna(subset=["capital_allocation_label"]).copy()

if df.empty:
    st.info("No capital allocation data available.")
    st.stop()

st.caption(
    "Every company's latest fiscal year is classified into one of 8 capital allocation "
    "patterns based on the sign of Operating / Investing / Financing cash flow."
)

fig = px.treemap(
    df, path=["capital_allocation_label", "company_id"],
    values=df["market_cap_crore"].clip(lower=1).fillna(1),
    color="capital_allocation_label",
)
fig.update_layout(height=560, margin=dict(t=20, l=0, r=0, b=0))
st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Explore a pattern")
patterns = sorted(df["capital_allocation_label"].unique().tolist())
selected_pattern = st.selectbox("Capital allocation pattern", patterns)

pattern_df = df[df["capital_allocation_label"] == selected_pattern]
st.markdown(f"**{len(pattern_df)} companies** classified as *{selected_pattern}*")

show_cols = [c for c in ["company_id", "company_name", "broad_sector", "free_cash_flow_cr",
                          "cfo_quality_label", "capex_label"] if c in pattern_df.columns]
st.dataframe(
    pattern_df[show_cols].rename(columns={
        "company_id": "Ticker", "company_name": "Company", "broad_sector": "Sector",
        "free_cash_flow_cr": "FCF (Cr)", "cfo_quality_label": "CFO Quality", "capex_label": "CapEx Intensity",
    }),
    hide_index=True, use_container_width=True,
)
