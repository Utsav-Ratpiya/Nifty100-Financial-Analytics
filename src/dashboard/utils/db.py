"""
src/dashboard/utils/db.py — Nifty 100 Analytics
Sprint 4 / Day 22 deliverable.

Every function that touches nifty100.db is wrapped with
@st.cache_data(ttl=600) so repeated navigation between screens doesn't
re-hit SQLite on every rerun. Cache keys are the function's own arguments
(ticker, year, group_name, ...), which is why every function takes plain,
hashable arguments rather than a shared connection object.
"""
from __future__ import annotations

import os
import sqlite3
import sys

import pandas as pd
import streamlit as st

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

sys.path.insert(0, os.path.join(BASE_DIR, "src", "screener"))
sys.path.insert(0, os.path.join(BASE_DIR, "src", "analytics"))


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


@st.cache_data(ttl=600)
def get_companies() -> pd.DataFrame:
    """All 92 companies with sector + headline KPI fields for list/search views."""
    conn = _connect()
    df = pd.read_sql(
        """
        SELECT c.company_id, c.company_name, c.about_company, c.website,
               c.nse_profile, c.bse_profile, c.face_value, c.book_value,
               c.roce_percentage, c.roe_percentage,
               s.broad_sector, s.sub_sector, s.market_cap_category
        FROM companies c
        LEFT JOIN sectors s ON s.company_id = c.company_id
        ORDER BY c.company_id
        """,
        conn,
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_ratios(ticker: str, year: str | None = None) -> pd.DataFrame:
    """All computed KPIs for one company, optionally filtered to one year."""
    conn = _connect()
    if year:
        df = pd.read_sql(
            "SELECT * FROM financial_ratios WHERE company_id = ? AND year = ?",
            conn, params=(ticker, year),
        )
    else:
        df = pd.read_sql(
            "SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year",
            conn, params=(ticker,),
        )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_pl(ticker: str) -> pd.DataFrame:
    """Full P&L history for one company."""
    conn = _connect()
    df = pd.read_sql(
        "SELECT * FROM profitandloss WHERE company_id = ? ORDER BY year", conn, params=(ticker,)
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_bs(ticker: str) -> pd.DataFrame:
    """Full balance sheet history for one company."""
    conn = _connect()
    df = pd.read_sql(
        "SELECT * FROM balancesheet WHERE company_id = ? ORDER BY year", conn, params=(ticker,)
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_cf(ticker: str) -> pd.DataFrame:
    """Full cash flow history for one company."""
    conn = _connect()
    df = pd.read_sql(
        "SELECT * FROM cashflow WHERE company_id = ? ORDER BY year", conn, params=(ticker,)
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_sectors() -> pd.DataFrame:
    """One row per broad_sector with company_count + median headline ratios,
    computed from the latest fiscal year per company (via the screener
    universe, so it stays consistent with the Screener/Peer screens)."""
    universe = get_universe()
    grouped = universe.groupby("broad_sector").agg(
        company_count=("company_id", "count"),
        median_roe=("return_on_equity_pct", "median"),
        median_pe=("pe_ratio", "median"),
        median_de=("debt_to_equity", "median"),
    ).reset_index()
    return grouped.sort_values("company_count", ascending=False)


@st.cache_data(ttl=600)
def get_peers(group_name: str) -> pd.DataFrame:
    """All companies + percentile ranks for one peer group, wide-formatted
    (one row per company, one column per metric's percentile_rank)."""
    conn = _connect()
    long = pd.read_sql(
        "SELECT * FROM peer_percentiles WHERE peer_group_name = ?", conn, params=(group_name,)
    )
    members = pd.read_sql(
        "SELECT company_id, is_benchmark FROM peer_groups WHERE peer_group_name = ?",
        conn, params=(group_name,),
    )
    companies = pd.read_sql("SELECT company_id, company_name FROM companies", conn)
    conn.close()

    if long.empty:
        return pd.DataFrame()

    wide_value = long.pivot_table(index="company_id", columns="metric", values="value", aggfunc="first")
    wide_pct = long.pivot_table(index="company_id", columns="metric", values="percentile_rank", aggfunc="first")
    wide_pct.columns = [f"{c}_percentile" for c in wide_pct.columns]

    wide = wide_value.join(wide_pct).reset_index()
    wide = wide.merge(members, on="company_id", how="left")
    wide = wide.merge(companies, on="company_id", how="left")
    return wide


@st.cache_data(ttl=600)
def get_valuation(ticker: str) -> pd.DataFrame:
    """Valuation multiples + flag for one company (from output/valuation_summary.xlsx,
    produced by src/analytics/valuation.py -- Day 26)."""
    path = os.path.join(OUTPUT_DIR, "valuation_summary.xlsx")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_excel(path)
    return df[df["company_id"] == ticker]


@st.cache_data(ttl=600)
def get_universe() -> pd.DataFrame:
    """The shared latest-fiscal-year, one-row-per-company screener universe
    (financial_ratios + sales/net_profit + market_cap + sector/company
    display fields). Reused across Home, Screener, Sector, and Peer screens
    so every screen agrees on the same numbers. Falls back to an empty
    frame with the expected columns if the universe builder errors out."""
    from universe import build_universe  # src/screener/universe.py

    conn = _connect()
    df = build_universe(conn)
    conn.close()

    val_path = os.path.join(OUTPUT_DIR, "valuation_summary.xlsx")
    if os.path.exists(val_path):
        val = pd.read_excel(val_path)
        cols = [c for c in ["company_id", "flag", "fcf_yield_pct", "pe_vs_sector_median_pct"] if c in val.columns]
        if cols:
            df = df.merge(val[cols], on="company_id", how="left")
    return df


@st.cache_data(ttl=600)
def get_universe_for_year(year: int) -> pd.DataFrame:
    """Same shape as get_universe(), but pinned to a specific calendar year
    (2019-2024) instead of always using each company's latest year. Used by
    the Home screen's year selector. If a company has no fiscal-year row in
    the requested year, it falls back to the closest earlier year available
    for that company; if none exists at all, the company is dropped for
    that year (rather than showing stale/future data)."""
    conn = _connect()
    fr = pd.read_sql("SELECT * FROM financial_ratios WHERE year != 'TTM'", conn)
    fr["_cal_year"] = fr["year"].str.split("-").str[1].astype(int)
    fr = fr[fr["_cal_year"] <= year]
    idx = fr.groupby("company_id")["_cal_year"].idxmax()
    fr_year = fr.loc[idx].drop(columns="_cal_year")

    pl = pd.read_sql("SELECT company_id, year, sales, net_profit FROM profitandloss WHERE year != 'TTM'", conn)
    pl["_cal_year"] = pl["year"].str.split("-").str[1].astype(int)
    pl = pl[pl["_cal_year"] <= year]
    pl_idx = pl.groupby("company_id")["_cal_year"].idxmax()
    pl_year = pl.loc[pl_idx][["company_id", "sales", "net_profit"]]

    mc = pd.read_sql("SELECT * FROM market_cap WHERE year <= ?", conn, params=(year,))
    mc_idx = mc.groupby("company_id")["year"].idxmax()
    mc_year = mc.loc[mc_idx]

    sectors = pd.read_sql("SELECT company_id, sub_sector, market_cap_category FROM sectors", conn)
    companies = pd.read_sql("SELECT company_id, company_name FROM companies", conn)
    conn.close()

    df = fr_year.merge(pl_year, on="company_id", how="left")
    df = df.merge(
        mc_year[["company_id", "market_cap_crore", "enterprise_value_crore", "pe_ratio", "pb_ratio", "ev_ebitda", "dividend_yield_pct"]],
        on="company_id", how="left",
    )
    df = df.merge(sectors, on="company_id", how="left")
    df = df.merge(companies, on="company_id", how="left")
    return df


@st.cache_data(ttl=600)
def get_pros_cons(ticker: str) -> pd.DataFrame:
    """Pros/cons for one company, ranked by confidence (highest first).

    The raw `prosandcons` DB table only covers 4 of the 92 companies (it's
    the untouched Sprint 1 source-spreadsheet load), which is why most
    company profiles showed an empty Pros & Cons section. The Sprint 5
    NLP rule engine (src/nlp/pros_cons_generator.py) generates a pro AND
    a con for every one of the 92 companies with a confidence score, and
    already ran -- its output lives at output/pros_cons_generated.csv.
    That's the source used here so every company has something to show;
    falls back to an empty frame (not an error) if the file is missing.
    """
    path = os.path.join(OUTPUT_DIR, "pros_cons_generated.csv")
    if not os.path.exists(path):
        return pd.DataFrame(columns=["type", "text", "confidence_pct"])
    df = pd.read_csv(path)
    df = df[df["company_id"] == ticker].sort_values("confidence_pct", ascending=False)
    return df[["type", "text", "confidence_pct"]].reset_index(drop=True)
