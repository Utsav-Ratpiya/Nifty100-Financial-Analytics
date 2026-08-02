"""
src/dashboard/pages/03_screener.py — Nifty 100 Analytics
Sprint 4 / Day 24 deliverable.
"""
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "screener"))
from db import get_universe  # noqa: E402
from engine import load_config, apply_filters, PRESET_NAMES  # noqa: E402

st.set_page_config(page_title="Screener — Nifty 100 Analytics", layout="wide")
st.title("Screener")

config = load_config()
universe = get_universe()

# --- slider metric definitions: (session_state key, screener_config metric name, label, min, max, default, step) ---
SLIDERS = [
    ("min_roe", "ROE min (%)", -20.0, 60.0, 0.0, 0.5),
    ("max_de", "D/E max", 0.0, 10.0, 10.0, 0.1),
    ("min_fcf", "FCF min (₹ Cr)", -5000.0, 5000.0, -5000.0, 50.0),
    ("min_rev_cagr_5yr", "Revenue CAGR 5yr min (%)", -20.0, 50.0, -20.0, 0.5),
    ("min_pat_cagr_5yr", "PAT CAGR 5yr min (%)", -50.0, 80.0, -50.0, 0.5),
    ("min_opm", "OPM min (%)", -20.0, 60.0, -20.0, 0.5),
    ("max_pe", "P/E max", 0.0, 150.0, 150.0, 1.0),
    ("max_pb", "P/B max", 0.0, 30.0, 30.0, 0.1),
    ("min_div_yield", "Dividend Yield min (%)", 0.0, 10.0, 0.0, 0.1),
    ("min_icr", "ICR min", 0.0, 30.0, 0.0, 0.5),
]

PRESET_LABELS = {name: config["presets"][name]["label"] for name in PRESET_NAMES}

if "screener_filters" not in st.session_state:
    st.session_state.screener_filters = {key: default for key, _, _, _, default, _ in SLIDERS}

st.subheader("Presets")
preset_cols = st.columns(len(PRESET_NAMES))
for i, preset_name in enumerate(PRESET_NAMES):
    if preset_cols[i].button(PRESET_LABELS[preset_name], use_container_width=True):
        preset_filters = config["presets"][preset_name]["filters"]
        # Reset every slider to its "no-op" bound, then apply the preset's filters on top.
        reset = {key: default for key, _, _, _, default, _ in SLIDERS}
        reset.update({k: v for k, v in preset_filters.items() if k in reset})
        st.session_state.screener_filters = reset
        st.session_state["_active_preset"] = preset_name

st.divider()
st.subheader("Filters")

slider_cols = st.columns(5)
current = {}
for i, (key, label, lo, hi, default, step) in enumerate(SLIDERS):
    with slider_cols[i % 5]:
        current[key] = st.slider(
            label, min_value=lo, max_value=hi,
            value=float(st.session_state.screener_filters.get(key, default)),
            step=step, key=f"slider_{key}",
        )
st.session_state.screener_filters = current

active_filters = {k: v for k, v in current.items()}

active_preset = st.session_state.get("_active_preset")
extra_filters = {}
if active_preset:
    preset_filters = config["presets"][active_preset]["filters"]
    extra_filters = {k: v for k, v in preset_filters.items() if k not in {s[0] for s in SLIDERS}}
    if active_preset == "turnaround_watch":
        from engine import _apply_de_declining_filter

try:
    results = apply_filters(universe, {**active_filters, **extra_filters}, config)
    if active_preset == "turnaround_watch":
        results = _apply_de_declining_filter(results)
except Exception as exc:
    st.error(f"Could not run screener: {exc}")
    results = pd.DataFrame()

st.divider()
st.markdown(f"**{len(results)} companies match your filters**")

DISPLAY_COLS = [
    ("company_id", "Ticker"), ("company_name", "Company"), ("broad_sector", "Sector"),
    ("composite_quality_score", "Composite Score"), ("return_on_equity_pct", "ROE %"),
    ("debt_to_equity", "D/E"), ("free_cash_flow_cr", "FCF (Cr)"),
    ("revenue_cagr_5yr", "Rev CAGR 5yr %"), ("pat_cagr_5yr", "PAT CAGR 5yr %"),
    ("operating_profit_margin_pct", "OPM %"), ("pe_ratio", "P/E"), ("pb_ratio", "P/B"),
    ("dividend_yield_pct", "Div Yield %"), ("interest_coverage", "ICR"), ("icr_label", "ICR Label"),
]
cols_present = [c for c, _ in DISPLAY_COLS if c in results.columns]
headers = [h for c, h in DISPLAY_COLS if c in results.columns]

if not results.empty:
    display_df = results[cols_present].copy()
    display_df.columns = headers
    st.dataframe(display_df, hide_index=True, use_container_width=True)

    csv_bytes = display_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV", data=csv_bytes, file_name="screener_results.csv",
        mime="text/csv",
    )
else:
    st.info("No companies match the current filters. Try widening a threshold or clearing a preset.")
