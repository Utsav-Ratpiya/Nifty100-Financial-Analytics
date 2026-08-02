"""
src/nlp/parser.py — Nifty 100 Analytics
Sprint 5 / Day 29: parse the free-text period fields in analysis.xlsx
(compounded_sales_growth, compounded_profit_growth, stock_price_cagr, roe)
using the spec regex: (\\d+)\\s*Years?:?\\s*([\\d.]+)%

Only 5 companies have analysis.xlsx rows at all (HDFCBANK, SBILIFE, TCS,
WIPRO, INFY) — WIPRO is excluded downstream since it's one of the 8
tickers with no matching companies.xlsx record (see Sprint 1 findings).

The regex only matches labels with an explicit digit before "Year(s)"
(e.g. '10 Years: 21%', '1 Year: -2%' -- wait, see below). Labels like
'TTM:' or 'Last Year:' have no leading digit and are intentionally logged
as parse failures rather than guessed at.

IMPORTANT real-data finding: the spec's exact regex value group is
`[\\d.]+`, which has no minus-sign handling. A genuinely negative entry
like '1 Year: -2%' (seen in the real stock_price_cagr data) does NOT
match at all and is logged as a parse failure, not parsed as -2. This is
a faithful implementation of the literal spec regex, documented here
rather than silently "fixed" by adding sign handling the spec didn't ask
for -- see output/parse_failures.csv for these cases.
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys

import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

_PATTERN = re.compile(r"(\d+)\s*Years?:?\s*([\d.]+)%")

FIELD_TO_METRIC_TYPE = {
    "compounded_sales_growth": "revenue_growth",
    "compounded_profit_growth": "profit_growth",
    "stock_price_cagr": "stock_price_cagr",
    "roe": "roe",
}


def parse_period_text(text) -> tuple:
    """Returns (period_years, value_pct) or (None, None) if no match."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None, None
    m = _PATTERN.search(str(text))
    if not m:
        return None, None
    return int(m.group(1)), float(m.group(2))


def run():
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))
    from etl.normaliser import normalize_ticker

    conn = sqlite3.connect(DB_PATH)
    valid_ids = set(pd.read_sql("SELECT company_id FROM companies", conn)["company_id"])

    df = pd.read_excel(os.path.join(DATA_DIR, "analysis.xlsx"), header=1)
    df["company_id"] = df["company_id"].apply(normalize_ticker)

    parsed_rows = []
    failure_rows = []

    for _, row in df.iterrows():
        cid = row["company_id"]
        for field, metric_type in FIELD_TO_METRIC_TYPE.items():
            raw_text = row.get(field)
            period, value = parse_period_text(raw_text)
            if period is None:
                failure_rows.append({
                    "company_id": cid, "field": field, "raw_text": raw_text,
                    "reason": "no digit-prefixed 'N Years:' pattern found",
                })
                continue
            parsed_rows.append({
                "company_id": cid, "metric_type": metric_type,
                "period_years": period, "value_pct": value,
            })

    parsed_df = pd.DataFrame(parsed_rows)
    failures_df = pd.DataFrame(failure_rows)

    # Only companies with a valid companies.xlsx record are analytics-usable;
    # WIPRO (orphan ticker, see Sprint 1) stays in parse output for
    # completeness but is flagged.
    if not parsed_df.empty:
        parsed_df["company_id_valid"] = parsed_df["company_id"].isin(valid_ids)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    parsed_path = os.path.join(OUTPUT_DIR, "analysis_parsed.csv")
    failures_path = os.path.join(OUTPUT_DIR, "parse_failures.csv")
    parsed_df.to_csv(parsed_path, index=False)
    failures_df.to_csv(failures_path, index=False)
    print(f"wrote {parsed_path} ({len(parsed_df)} rows)")
    print(f"wrote {failures_path} ({len(failures_df)} rows)")

    divergences = cross_validate_against_computed_cagr(conn, parsed_df, valid_ids)
    conn.close()
    return parsed_df, failures_df, divergences


def cross_validate_against_computed_cagr(conn, parsed_df: pd.DataFrame, valid_ids: set) -> pd.DataFrame:
    """Cross-check parsed revenue_growth / profit_growth (5yr window) against
    the ratio engine's own revenue_cagr_5yr / pat_cagr_5yr. Flags divergence
    > 5 percentage points for manual review."""
    if parsed_df.empty:
        return pd.DataFrame()

    fr = pd.read_sql(
        "SELECT company_id, year, revenue_cagr_5yr, pat_cagr_5yr FROM financial_ratios WHERE year != 'TTM'",
        conn)
    fr["_cal_year"] = fr["year"].str.split("-").str[1].astype(int)
    latest = fr.sort_values("_cal_year").groupby("company_id").tail(1).set_index("company_id")

    rows = []
    for metric_type, computed_col in [("revenue_growth", "revenue_cagr_5yr"), ("profit_growth", "pat_cagr_5yr")]:
        subset = parsed_df[(parsed_df["metric_type"] == metric_type) & (parsed_df["period_years"] == 5)]
        for _, row in subset.iterrows():
            cid = row["company_id"]
            if cid not in valid_ids or cid not in latest.index:
                continue
            computed = latest.loc[cid, computed_col]
            if pd.isna(computed):
                continue
            diff = abs(row["value_pct"] - computed)
            if diff > 5.0:
                rows.append({
                    "company_id": cid, "metric_type": metric_type,
                    "parsed_5yr_pct": row["value_pct"], "computed_5yr_cagr_pct": round(computed, 2),
                    "divergence_pct_points": round(diff, 2),
                })

    result = pd.DataFrame(rows)
    if not result.empty:
        path = os.path.join(OUTPUT_DIR, "analysis_cagr_divergence.csv")
        result.to_csv(path, index=False)
        print(f"wrote {path} ({len(result)} divergences > 5pt flagged for manual review)")
    return result


if __name__ == "__main__":
    run()
