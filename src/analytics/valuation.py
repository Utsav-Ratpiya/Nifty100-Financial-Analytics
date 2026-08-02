"""
src/analytics/valuation.py — Nifty 100 Analytics
Sprint 4 / Day 26 deliverable.

Uses data/market_cap.xlsx (already loaded into the `market_cap` table by
Sprint 3's screener universe work) plus financial_ratios' free_cash_flow_cr
to compute:

    - FCF Yield %          = FCF / market_cap_crore x 100
    - 5yr median P/E        = median of the company's own trailing 5 years
                               of pe_ratio (from market_cap)
    - Sector median P/E    = median of the LATEST-year pe_ratio across all
                               companies in the same broad_sector
    - Valuation flag:
        P/E > sector_median x 1.5   -> "Caution"
        P/E < sector_median x 0.7   -> "Discount"
        otherwise                   -> "Fair"

Outputs:
    output/valuation_summary.xlsx  — all 92 companies
    output/valuation_flags.csv     — only Caution/Discount rows

Usage:
    python3 src/analytics/valuation.py
"""
from __future__ import annotations

import os
import sqlite3
import sys

import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

sys.path.insert(0, os.path.join(BASE_DIR, "src", "screener"))

CAUTION_MULTIPLE = 1.5
DISCOUNT_MULTIPLE = 0.7


def five_year_median_pe(conn: sqlite3.Connection) -> pd.Series:
    """Median of each company's own trailing-5-year P/E history from the
    market_cap table (indexed by company_id)."""
    mc = pd.read_sql("SELECT company_id, year, pe_ratio FROM market_cap", conn)
    mc = mc.sort_values(["company_id", "year"])
    trailing5 = mc.groupby("company_id").tail(5)
    return trailing5.groupby("company_id")["pe_ratio"].median()


def sector_median_pe(universe: pd.DataFrame) -> pd.Series:
    """Median of the LATEST-year P/E across companies in the same
    broad_sector (indexed by broad_sector)."""
    return universe.groupby("broad_sector")["pe_ratio"].median()


def classify_valuation(pe: float | None, sector_median: float | None) -> str:
    """Fair / Caution / Discount classification vs the sector median P/E.
    Returns "Not Rated" if either input is missing (e.g. loss-making
    company with no meaningful P/E)."""
    if pe is None or sector_median is None or pd.isna(pe) or pd.isna(sector_median) or sector_median == 0:
        return "Not Rated"
    if pe > sector_median * CAUTION_MULTIPLE:
        return "Caution"
    if pe < sector_median * DISCOUNT_MULTIPLE:
        return "Discount"
    return "Fair"


def fcf_yield_pct(fcf_cr: float | None, market_cap_cr: float | None) -> float | None:
    if fcf_cr is None or market_cap_cr is None or pd.isna(fcf_cr) or pd.isna(market_cap_cr) or market_cap_cr == 0:
        return None
    return fcf_cr / market_cap_cr * 100.0


def build_valuation_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    from universe import build_universe  # src/screener/universe.py — single source of truth

    universe = build_universe(conn)

    median_pe_5yr = five_year_median_pe(conn)
    sector_median = sector_median_pe(universe)

    df = universe[[
        "company_id", "company_name", "broad_sector",
        "pe_ratio", "pb_ratio", "ev_ebitda", "free_cash_flow_cr", "market_cap_crore",
    ]].copy()

    df["FCF_yield_pct"] = df.apply(
        lambda r: fcf_yield_pct(r["free_cash_flow_cr"], r["market_cap_crore"]), axis=1
    )
    df["5yr_median_PE"] = df["company_id"].map(median_pe_5yr)
    df["sector_median_PE"] = df["broad_sector"].map(sector_median)
    df["PE_vs_sector_median_pct"] = df.apply(
        lambda r: ((r["pe_ratio"] / r["sector_median_PE"] - 1) * 100.0)
        if pd.notna(r["pe_ratio"]) and pd.notna(r["sector_median_PE"]) and r["sector_median_PE"] != 0
        else None,
        axis=1,
    )
    df["flag"] = df.apply(lambda r: classify_valuation(r["pe_ratio"], r["sector_median_PE"]), axis=1)

    df = df.rename(columns={
        "broad_sector": "sector",
        "pe_ratio": "P/E",
        "pb_ratio": "P/B",
        "ev_ebitda": "EV/EBITDA",
    })

    return df[[
        "company_id", "company_name", "sector", "P/E", "P/B", "EV/EBITDA",
        "FCF_yield_pct", "5yr_median_PE", "PE_vs_sector_median_pct", "flag",
    ]]


def run() -> dict:
    print("Nifty 100 Analytics — Sprint 4 Valuation Module starting...")
    conn = sqlite3.connect(DB_PATH)

    summary = build_valuation_summary(conn)

    summary_path = os.path.join(OUTPUT_DIR, "valuation_summary.xlsx")
    summary.to_excel(summary_path, index=False)
    print(f"  wrote {summary_path} ({len(summary)} rows)")

    flagged = summary[summary["flag"].isin(["Caution", "Discount"])].copy()
    flags_path = os.path.join(OUTPUT_DIR, "valuation_flags.csv")
    flagged.to_csv(flags_path, index=False)
    print(f"  wrote {flags_path} ({len(flagged)} flagged companies)")

    conn.close()
    return {"total_rows": len(summary), "flagged_rows": len(flagged)}


if __name__ == "__main__":
    result = run()
    status = "OK" if result["total_rows"] >= 92 else "CHECK"
    print(f"\n[{status}] valuation_summary.xlsx has {result['total_rows']} rows (need >= 92)")
