"""
src/dashboard/pages/08_reports.py — Nifty 100 Analytics
Sprint 4 / Day 25 deliverable + visual-enhancement pass: 3 KPI tiles
summarising report availability, a year-range slider, and coloured
status badges (was plain red/blue text) for each row.
"""
import os
import sys
import urllib.request
import urllib.error

import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from db import get_companies, _connect  # noqa: E402
from theme import animated_title, badge, inject_global_css, section_header  # noqa: E402

st.set_page_config(page_title="Annual Reports — Nifty 100 Analytics", layout="wide")
inject_global_css()
animated_title("Annual Reports", icon="\U0001F4C4")

companies = get_companies()
options = [f"{row.company_id} — {row.company_name}" for row in companies.itertuples()]
search = st.selectbox("Company", options, index=None, placeholder="Search by company name or ticker...")

if search is None:
    st.info("Search for a company above to see its available annual reports.")
    st.stop()

ticker = search.split(" — ")[0]

import pandas as pd  # noqa: E402

conn = _connect()
docs_all = pd.read_sql(
    "SELECT year, annual_report_url FROM documents WHERE company_id = ? ORDER BY year DESC",
    conn, params=(ticker,),
)
conn.close()

if docs_all.empty:
    st.error("Ticker not found — please try another")
    st.stop()


# BSE (and most exchange/CDN hosts) reject plain urllib requests that have
# no User-Agent — the previous version sent none, so *every* link came
# back as "Unavailable" even when it opened fine in a browser. Also many
# hosts return 405/403 on HEAD even though GET works, so HEAD failures
# fall back to a small ranged GET instead of giving up immediately.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


def _try_request(url: str, method: str, extra_headers: dict | None = None, timeout: int = 10) -> bool:
    headers = dict(_BROWSER_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return 200 <= resp.status < 400


@st.cache_data(ttl=600)
def check_url(url: str) -> bool:
    """Confirms a report link resolves. Tries HEAD first (cheap); if the
    host doesn't support HEAD (405/403/empty response) it retries with a
    1-byte ranged GET, which almost every file host honours. Any genuine
    network error or 4xx/5xx after both attempts is treated as
    unavailable (fails safe -> shows the red badge rather than a broken
    link)."""
    try:
        return _try_request(url, "HEAD")
    except urllib.error.HTTPError as e:
        if e.code not in (405, 403, 501):
            return False
    except Exception:
        pass  # fall through to the GET retry below

    try:
        return _try_request(url, "GET", extra_headers={"Range": "bytes=0-0"})
    except urllib.error.HTTPError as e:
        # A 206 Partial Content or plain 200 both mean the file exists;
        # anything else (404, 410, ...) means it genuinely isn't there.
        return 200 <= e.code < 400
    except Exception:
        return False


# --- year-range slider (new) ---
years_numeric = sorted({int(str(y)[:4]) for y in docs_all["year"] if str(y)[:4].isdigit()})
if len(years_numeric) > 1:
    yr_lo, yr_hi = st.select_slider(
        "Year range", options=years_numeric, value=(years_numeric[0], years_numeric[-1]),
    )
    docs = docs_all[docs_all["year"].apply(lambda y: yr_lo <= int(str(y)[:4]) <= yr_hi if str(y)[:4].isdigit() else True)]
else:
    docs = docs_all

refresh_col, _ = st.columns([1, 4])
with refresh_col:
    if st.button("\U0001F504 Recheck link status", help="Clears the cached availability check and re-tests every link."):
        check_url.clear()

docs = docs.reset_index(drop=True)
docs["_has_link"] = docs["annual_report_url"].apply(lambda u: isinstance(u, str) and bool(u))
docs["_available"] = [check_url(u) if has_link else False for u, has_link in zip(docs["annual_report_url"], docs["_has_link"])]

# --- KPI tiles ---
k1, k2, k3, k4 = st.columns(4)
k1.metric("Reports listed", len(docs))
k2.metric("Available", int(docs["_available"].sum()))
k3.metric("Unavailable", int((~docs["_available"]).sum()))
k4.metric("No link on file", int((~docs["_has_link"]).sum()))

st.divider()

# --- status filter (new) + availability-by-year chart (new) ---
filter_col, chart_col = st.columns([1, 2])
with filter_col:
    section_header("Filter")
    status_filter = st.radio("Show", ["All", "Available only", "Unavailable only"], horizontal=False)
    if status_filter == "Available only":
        docs_view = docs[docs["_available"]]
    elif status_filter == "Unavailable only":
        docs_view = docs[~docs["_available"]]
    else:
        docs_view = docs

with chart_col:
    section_header("Availability by year")
    chart_df = docs.copy()
    chart_df["Status"] = chart_df["_available"].map({True: "Available", False: "Unavailable"})
    fig = px.bar(
        chart_df, x="year", y=[1] * len(chart_df), color="Status",
        color_discrete_map={"Available": "#22C55E", "Unavailable": "#EF4444"},
        labels={"y": "", "year": "Fiscal Year"},
    )
    fig.update_layout(height=280, yaxis=dict(showticklabels=False, title=""), showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

st.divider()
section_header(f"Annual reports — {ticker}")
if docs_view.empty:
    st.info("No reports match this filter.")
for _, row in docs_view.iterrows():
    is_valid = row["_available"]
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        st.markdown(f"**FY {row['year']}**")
    with col2:
        st.markdown(badge("Available", "green") if is_valid else badge("Unavailable", "red"), unsafe_allow_html=True)
    with col3:
        url = row["annual_report_url"]
        if not isinstance(url, str) or not url:
            st.caption("No link on file.")
        elif is_valid:
            st.markdown(f"[View annual report (PDF)]({url})")
        else:
            st.caption(url)
