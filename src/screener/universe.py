"""
src/screener/universe.py — Nifty 100 Analytics
Sprint 3 / Day 15 prerequisite.

Builds the flat, one-row-per-company "screener universe" DataFrame that
src/screener/engine.py filters. Combines:

    financial_ratios  — latest fiscal year (Mar-YYYY), NOT the TTM row,
                         since TTM has no CAGR data (see Sprint 2 retro)
    profitandloss      — sales, net_profit for that same fiscal year
                         (not stored in financial_ratios itself)
    market_cap         — latest available year (2024) — P/E, P/B, EV/EBITDA,
                         dividend yield, market cap
    sectors, companies — broad_sector, company_name, for display/filtering
"""
from __future__ import annotations

import os
import sqlite3

import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")


def _latest_fiscal_year_row(df: pd.DataFrame) -> pd.DataFrame:
    """Pick the latest NON-TTM row per company_id, using calendar year
    extracted from the 'Mon-YYYY' label (TTM sorts last but has no CAGR
    data, so it's excluded from the screener universe)."""
    df = df[df["year"] != "TTM"].copy()
    df["_cal_year"] = df["year"].str.split("-").str[1].astype(int)
    idx = df.groupby("company_id")["_cal_year"].idxmax()
    return df.loc[idx].drop(columns=["_cal_year"])


def build_universe(conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(DB_PATH)

    fr = pd.read_sql("SELECT * FROM financial_ratios", conn)
    fr_latest = _latest_fiscal_year_row(fr)
    fr_latest["_cal_year"] = fr_latest["year"].str.split("-").str[1].astype(int)

    pl = pd.read_sql("SELECT company_id, year, sales, net_profit FROM profitandloss", conn)
    pl["_cal_year"] = pl["year"].where(pl["year"] == "TTM", pl["year"].str.split("-").str[1])
    pl = pl[pl["year"] != "TTM"].copy()
    pl["_cal_year"] = pl["year"].str.split("-").str[1].astype(int)

    universe = fr_latest.merge(
        pl[["company_id", "_cal_year", "sales", "net_profit"]],
        on=["company_id", "_cal_year"], how="left"
    )

    mc_max = pd.read_sql("SELECT company_id, MAX(year) as year FROM market_cap GROUP BY company_id", conn)
    mc_full = pd.read_sql("SELECT * FROM market_cap", conn)
    mc_latest = mc_full.merge(mc_max, on=["company_id", "year"], how="inner")

    universe = universe.merge(
        mc_latest[["company_id", "market_cap_crore", "enterprise_value_crore",
                   "pe_ratio", "pb_ratio", "ev_ebitda", "dividend_yield_pct"]],
        on="company_id", how="left"
    )

    sectors = pd.read_sql("SELECT company_id, sub_sector, market_cap_category FROM sectors", conn)
    companies = pd.read_sql("SELECT company_id, company_name FROM companies", conn)
    universe = universe.merge(sectors, on="company_id", how="left")
    universe = universe.merge(companies, on="company_id", how="left")

    if own_conn:
        conn.close()

    return universe.drop(columns=["_cal_year"], errors="ignore")
