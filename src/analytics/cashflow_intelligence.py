"""
src/analytics/cashflow_intelligence.py — Nifty 100 Analytics
Sprint 5 / Day 31: distress signal + deleveraging flag detection, built on
top of the Sprint 2 cashflow_kpis.py functions (CFO quality, CapEx
intensity already exist there).
"""
from __future__ import annotations

import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from cashflow_kpis import cfo_quality_score, capex_intensity, free_cash_flow, fcf_conversion_rate  # noqa: E402
from cagr import cagr_with_flag  # noqa: E402

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def _company_cf_series(conn, company_id):
    fr = pd.read_sql(
        "SELECT company_id, year, free_cash_flow_cr, cfo_quality_score, cfo_quality_label, "
        "capex_intensity_pct, capex_label, capital_allocation_label, "
        "total_debt_cr, fcf_conversion_pct FROM financial_ratios "
        "WHERE company_id = ? AND year != 'TTM'", conn, params=(company_id,))
    cf = pd.read_sql(
        "SELECT year, operating_activity, investing_activity, financing_activity FROM cashflow "
        "WHERE company_id = ? AND year != 'TTM'", conn, params=(company_id,))
    pl = pd.read_sql("SELECT year, net_profit FROM profitandloss WHERE company_id = ? AND year != 'TTM'",
                      conn, params=(company_id,))

    merged = fr.merge(cf, on="year", how="left").merge(pl, on="year", how="left")
    merged["_cal_year"] = merged["year"].str.split("-").str[1].astype(int)
    return merged.sort_values("_cal_year").reset_index(drop=True)


def detect_distress(latest_row) -> bool:
    """CFO < 0 AND CFF > 0 in latest year (raising cash from financing
    while operations burn cash)."""
    cfo, cff = latest_row.get("operating_activity"), latest_row.get("financing_activity")
    if pd.isna(cfo) or pd.isna(cff):
        return False
    return cfo < 0 and cff > 0


def detect_deleveraging(g: pd.DataFrame) -> bool:
    """CFF < 0 AND borrowings declining YoY in the latest year."""
    if len(g) < 2:
        return False
    latest, prior = g.iloc[-1], g.iloc[-2]
    cff = latest.get("financing_activity")
    debt_latest, debt_prior = latest.get("total_debt_cr"), prior.get("total_debt_cr")
    if pd.isna(cff) or pd.isna(debt_latest) or pd.isna(debt_prior):
        return False
    return cff < 0 and debt_latest < debt_prior


def fcf_cagr_5yr(g: pd.DataFrame):
    series = g["free_cash_flow_cr"].tolist()
    if len(series) < 6:
        return None
    value, _flag = cagr_with_flag(series[-6], series[-1], 5)
    return value


def run():
    conn = sqlite3.connect(DB_PATH)
    companies = pd.read_sql("SELECT company_id FROM companies", conn)["company_id"].tolist()
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn).set_index("company_id")["broad_sector"]

    rows = []
    distress_rows = []
    pattern_change_rows = []

    for cid in companies:
        g = _company_cf_series(conn, cid)
        if g.empty:
            continue
        latest = g.iloc[-1]
        sector = sectors.get(cid, "Unknown")

        distress = detect_distress(latest)
        delever = detect_deleveraging(g)
        fcf_cagr = fcf_cagr_5yr(g)

        rows.append({
            "company_id": cid,
            "sector": sector,
            "cfo_quality_score": latest.get("cfo_quality_score"),
            "cfo_quality_label": latest.get("cfo_quality_label"),
            "capex_intensity_pct": latest.get("capex_intensity_pct"),
            "capex_label": latest.get("capex_label"),
            "fcf_cagr_5yr": fcf_cagr,
            "fcf_conversion_pct": latest.get("fcf_conversion_pct"),
            "distress_flag": distress,
            "deleveraging_flag": delever,
            "capital_allocation_label": latest.get("capital_allocation_label"),
        })

        if distress:
            distress_rows.append({
                "company_id": cid, "sector": sector,
                "cfo": latest.get("operating_activity"), "cff": latest.get("financing_activity"),
                "latest_net_profit": latest.get("net_profit"),
            })

        # pattern changes YoY (latest vs prior)
        if len(g) >= 2:
            prior_label = g.iloc[-2].get("capital_allocation_label")
            latest_label = latest.get("capital_allocation_label")
            if pd.notna(prior_label) and pd.notna(latest_label) and prior_label != latest_label:
                pattern_change_rows.append({
                    "company_id": cid, "from_pattern": prior_label, "to_pattern": latest_label,
                    "year": latest.get("year"),
                })

    result_df = pd.DataFrame(rows)
    for col in ["distress_flag", "deleveraging_flag"]:
        result_df[col] = result_df[col].astype(bool)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    xlsx_path = os.path.join(OUTPUT_DIR, "cashflow_intelligence.xlsx")
    result_df.to_excel(xlsx_path, index=False)
    print(f"wrote {xlsx_path} ({len(result_df)} rows)")

    distress_df = pd.DataFrame(distress_rows)
    distress_path = os.path.join(OUTPUT_DIR, "distress_alerts.csv")
    distress_df.to_csv(distress_path, index=False)
    print(f"wrote {distress_path} ({len(distress_df)} companies flagged)")

    pattern_df = pd.DataFrame(pattern_change_rows)
    pattern_path = os.path.join(OUTPUT_DIR, "pattern_changes.csv")
    pattern_df.to_csv(pattern_path, index=False)
    print(f"wrote {pattern_path} ({len(pattern_df)} YoY pattern changes)")

    # Distribution summary: count of companies per capital allocation pattern, latest year
    dist_summary = result_df["capital_allocation_label"].value_counts()
    print("\nCapital allocation pattern distribution (latest year):")
    print(dist_summary.to_string())

    conn.close()
    return result_df, distress_df, pattern_df


if __name__ == "__main__":
    run()
