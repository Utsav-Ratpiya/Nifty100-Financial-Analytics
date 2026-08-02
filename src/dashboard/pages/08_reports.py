"""
src/dashboard/pages/08_reports.py — Nifty 100 Analytics
Sprint 4 / Day 25 deliverable.
"""
import os
import sys
import urllib.request
import urllib.error

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_companies, _connect  # noqa: E402

st.set_page_config(page_title="Annual Reports — Nifty 100 Analytics", layout="wide")
st.title("Annual Reports")

companies = get_companies()
options = [f"{row.company_id} — {row.company_name}" for row in companies.itertuples()]
search = st.selectbox("Company", options, index=None, placeholder="Search by company name or ticker...")

if search is None:
    st.info("Search for a company above to see its available annual reports.")
    st.stop()

ticker = search.split(" — ")[0]

import pandas as pd  # noqa: E402

conn = _connect()
docs = pd.read_sql(
    "SELECT year, annual_report_url FROM documents WHERE company_id = ? ORDER BY year DESC",
    conn, params=(ticker,),
)
conn.close()

if docs.empty:
    st.error("Ticker not found — please try another")
    st.stop()


@st.cache_data(ttl=600)
def check_url(url: str) -> bool:
    """Best-effort HEAD/GET request to confirm the BSE PDF link resolves.
    Any network error, timeout, or non-2xx/3xx status is treated as
    unavailable (fails safe -> shows the red badge rather than a broken link)."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 400
    except urllib.error.HTTPError as e:
        return 200 <= e.code < 400
    except Exception:
        return False


st.subheader(f"Annual reports — {ticker}")
for _, row in docs.iterrows():
    col1, col2 = st.columns([1, 4])
    with col1:
        st.markdown(f"**FY {row['year']}**")
    with col2:
        url = row["annual_report_url"]
        if not isinstance(url, str) or not url:
            st.markdown(":red[Report unavailable]")
            continue
        is_valid = check_url(url)
        if is_valid:
            st.markdown(f"[View annual report (PDF)]({url})")
        else:
            st.markdown(f":red[Report unavailable] — {url}")
