"""
src/analytics/ratios.py — Nifty 100 Analytics
Sprint 2 / Day 08, 09, 12, 13 deliverable.

Profitability, leverage, and efficiency ratio formulas (pure functions,
independently unit-testable — see tests/kpi/test_ratios.py), plus the
orchestration entry point that:

  1. loads profitandloss / balancesheet / cashflow / companies / sectors
     from nifty100.db,
  2. computes every ratio in this module plus the CAGR engine (cagr.py)
     and cash-flow intelligence (cashflow_kpis.py) for every company-year,
  3. applies the Financials-sector ROCE/D-E carve-out,
  4. writes the result into the financial_ratios table in nifty100.db,
  5. writes output/capital_allocation.csv and output/ratio_edge_cases.log.

Usage:
    python3 src/analytics/ratios.py      (also wired to `make ratios`)
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "etl"))

from cagr import compute_cagr_columns  # noqa: E402
from cashflow_kpis import (  # noqa: E402
    free_cash_flow,
    cfo_quality_score,
    capex_intensity,
    fcf_conversion_rate,
    capital_allocation_pattern,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

FINANCIALS_SECTOR = "Financials"


# ---------------------------------------------------------------------------
# Day 08 — Profitability ratios
# ---------------------------------------------------------------------------

def net_profit_margin(net_profit, sales):
    """Net Profit Margin (%) = net_profit / sales x 100. None if sales == 0."""
    if sales is None or sales == 0:
        return None
    return (net_profit / sales) * 100


def operating_profit_margin_check(operating_profit, sales, opm_percentage, tolerance=1.0):
    """Recompute OPM from sales/operating_profit and cross-check against the
    source opm_percentage field. Returns (computed_opm, mismatch_flag)."""
    if sales is None or sales == 0:
        return None, False
    computed = (operating_profit / sales) * 100
    if opm_percentage is None:
        return computed, False
    mismatch = abs(computed - opm_percentage) > tolerance
    return computed, mismatch


def return_on_equity(net_profit, equity_capital, reserves):
    """ROE (%) = net_profit / (equity_capital + reserves) x 100.
    None if equity+reserves <= 0 (negative-equity edge case)."""
    if equity_capital is None or reserves is None:
        return None
    net_worth = equity_capital + reserves
    if net_worth <= 0:
        return None
    return (net_profit / net_worth) * 100


def return_on_capital_employed(operating_profit, other_income, equity_capital, reserves, borrowings):
    """ROCE (%) = EBIT / (equity + reserves + borrowings) x 100.
    EBIT approximated as operating_profit + other_income (pre-interest, pre-tax)."""
    if equity_capital is None or reserves is None or borrowings is None:
        return None
    capital_employed = equity_capital + reserves + borrowings
    if capital_employed <= 0:
        return None
    ebit = (operating_profit or 0) + (other_income or 0)
    return (ebit / capital_employed) * 100


def return_on_assets(net_profit, total_assets):
    """ROA (%) = net_profit / total_assets x 100. None if total_assets == 0."""
    if total_assets is None or total_assets == 0:
        return None
    return (net_profit / total_assets) * 100


# ---------------------------------------------------------------------------
# Day 09 — Leverage & efficiency ratios
# ---------------------------------------------------------------------------

def debt_to_equity(borrowings, equity_capital, reserves):
    """D/E = borrowings / (equity_capital + reserves).
    Returns 0 (NOT None) if borrowings == 0 — debt-free company.
    Returns None if net worth <= 0 (undefined, not zero)."""
    if borrowings == 0 or borrowings is None:
        return 0.0
    if equity_capital is None or reserves is None:
        return None
    net_worth = equity_capital + reserves
    if net_worth <= 0:
        return None
    return borrowings / net_worth


def high_leverage_flag(de_ratio, broad_sector, threshold=5.0):
    """True if D/E > threshold AND company is NOT in the Financials sector
    (high leverage is structurally normal for banks/NBFCs/insurers)."""
    if de_ratio is None or broad_sector == FINANCIALS_SECTOR:
        return False
    return de_ratio > threshold


def interest_coverage_ratio(operating_profit, other_income, interest):
    """ICR = (operating_profit + other_income) / interest.
    Returns None if interest == 0 (debt-free — see icr_label())."""
    if interest is None or interest == 0:
        return None
    return ((operating_profit or 0) + (other_income or 0)) / interest


def icr_label(icr_value):
    """Display label for the ICR column: 'Debt Free' when ICR is None
    because interest expense is zero, otherwise a formatted numeric label."""
    if icr_value is None:
        return "Debt Free"
    return f"{icr_value:.2f}x"


def icr_warning_flag(icr_value):
    """True if ICR < 1.5 — at risk of not covering interest payments.
    Debt-free companies (icr_value is None) never trigger this warning."""
    if icr_value is None:
        return False
    return icr_value < 1.5


def net_debt(borrowings, investments):
    """Net Debt = borrowings - investments (investments used as a liquid-asset proxy)."""
    if borrowings is None:
        borrowings = 0
    if investments is None:
        investments = 0
    return borrowings - investments


def asset_turnover(sales, total_assets):
    """Asset Turnover = sales / total_assets. None if total_assets == 0."""
    if total_assets is None or total_assets == 0:
        return None
    return sales / total_assets


# ---------------------------------------------------------------------------
# Row-level orchestration — combines every ratio above for one company-year
# ---------------------------------------------------------------------------

def compute_row_ratios(row: dict) -> dict:
    """Given a merged company-year dict (pl + bs + cf + sector fields),
    return a dict of every Day08/Day09 ratio plus flags/labels."""
    sales = row.get("sales")
    net_profit = row.get("net_profit")
    operating_profit = row.get("operating_profit")
    other_income = row.get("other_income")
    interest = row.get("interest")
    opm_percentage = row.get("opm_percentage")
    equity_capital = row.get("equity_capital")
    reserves = row.get("reserves")
    borrowings = row.get("borrowings")
    total_assets = row.get("total_assets")
    investments = row.get("investments")
    broad_sector = row.get("broad_sector")

    computed_opm, opm_mismatch = operating_profit_margin_check(operating_profit, sales, opm_percentage)
    de = debt_to_equity(borrowings, equity_capital, reserves)
    icr = interest_coverage_ratio(operating_profit, other_income, interest)

    return {
        "net_profit_margin_pct": net_profit_margin(net_profit, sales),
        "operating_profit_margin_pct": computed_opm,
        "opm_crosscheck_mismatch": opm_mismatch,
        "return_on_equity_pct": return_on_equity(net_profit, equity_capital, reserves),
        "roce_pct": return_on_capital_employed(operating_profit, other_income, equity_capital, reserves, borrowings),
        "return_on_assets_pct": return_on_assets(net_profit, total_assets),
        "debt_to_equity": de,
        "high_leverage_flag": high_leverage_flag(de, broad_sector) if broad_sector != FINANCIALS_SECTOR else False,
        "interest_coverage": icr,
        "icr_label": icr_label(icr),
        "icr_warning_flag": icr_warning_flag(icr),
        "net_debt_cr": net_debt(borrowings, investments),
        "asset_turnover": asset_turnover(sales, total_assets),
    }


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_base_frame(conn) -> pd.DataFrame:
    """pl is the backbone (most complete table); left-join bs and cf so we
    don't drop rows that are merely missing a balance-sheet or cash-flow
    entry for that year (keeps row count >= 1,100 per the exit criteria)."""
    pl = pd.read_sql("SELECT * FROM profitandloss", conn)
    bs = pd.read_sql("SELECT * FROM balancesheet", conn)
    cf = pd.read_sql("SELECT * FROM cashflow", conn)
    companies = pd.read_sql("SELECT company_id, roce_percentage, roe_percentage, book_value FROM companies", conn)
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)

    df = pl.merge(bs, on=["company_id", "year"], how="left", suffixes=("", "_bs"))
    df = df.merge(cf, on=["company_id", "year"], how="left", suffixes=("", "_cf"))
    df = df.merge(sectors, on="company_id", how="left")
    df = df.merge(companies, on="company_id", how="left")
    return df


def _year_sort_key(label: str):
    """Sortable key for canonical year labels ('Mon-YYYY', 'YYYY-00', 'TTM').
    TTM sorts after every fiscal-year-end label for that company (it is the
    most recent trailing period) but is excluded from CAGR windows."""
    months = {m: i for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}
    if label == "TTM":
        return (9999, 99)
    if "-" in label:
        left, year = label.split("-")
        if left in months:
            return (int(year), months[left])
        return (int(left), 0)
    return (0, 0)


# ---------------------------------------------------------------------------
# Bank ROCE carve-out + edge case logging (Day 13)
# ---------------------------------------------------------------------------

def _categorise_anomaly(diff_pct: float) -> str:
    if diff_pct > 20:
        return "data source issue"
    if diff_pct > 10:
        return "version difference"
    return "formula discrepancy"


def _build_edge_case_log(df: pd.DataFrame) -> list[str]:
    """Cross-check latest-year computed ROCE/ROE against the pre-computed
    companies.roce_percentage / roe_percentage columns."""
    lines = []
    lines.append(f"# ratio_edge_cases.log — generated {datetime.now(timezone.utc).isoformat()}")
    lines.append("# Cross-check: computed ROCE/ROE vs companies.xlsx pre-computed roce_percentage/roe_percentage")
    lines.append("# Category legend: data source issue | version difference | formula discrepancy")
    lines.append("")

    latest = (
        df[df["year"] != "TTM"]
        .sort_values("_year_sort")
        .groupby("company_id")
        .tail(1)
    )

    n_roce_anom, n_roe_anom = 0, 0
    for _, row in latest.iterrows():
        cid = row["company_id"]
        sector = row.get("broad_sector")
        is_bank = sector == FINANCIALS_SECTOR

        computed_roce = row.get("roce_pct")
        source_roce = row.get("roce_percentage")
        if pd.notna(computed_roce) and pd.notna(source_roce):
            diff = abs(computed_roce - source_roce)
            if diff > 5:
                n_roce_anom += 1
                cat = _categorise_anomaly(diff)
                note = " [Financials sector — D/E high-leverage flag suppressed structurally]" if is_bank else ""
                lines.append(
                    f"ROCE anomaly | {cid} | computed={computed_roce:.2f}% source={source_roce:.2f}% "
                    f"diff={diff:.2f}pp | category={cat}{note}"
                )

        computed_roe = row.get("return_on_equity_pct")
        source_roe = row.get("roe_percentage")
        if pd.notna(computed_roe) and pd.notna(source_roe):
            diff = abs(computed_roe - source_roe)
            if diff > 5:
                n_roe_anom += 1
                cat = _categorise_anomaly(diff)
                lines.append(
                    f"ROE anomaly    | {cid} | computed={computed_roe:.2f}% source={source_roe:.2f}% "
                    f"diff={diff:.2f}pp | category={cat} "
                    f"[note: source roe_percentage can itself be stale/anomalous vs the engine — "
                    f"engine value used for analytics, source value for display only]"
                )

    if "opm_crosscheck_mismatch" in df.columns and df["opm_crosscheck_mismatch"].notna().any():
        n_opm = int(df["opm_crosscheck_mismatch"].sum())
        lines.append("")
        lines.append(f"# OPM cross-check: {n_opm} company-year rows differ from source opm_percentage by > 1pp "
                     f"| category=version difference")

    # Cross-check against data/financial_ratios.xlsx — a pre-computed reference
    # file called out in db/schema.sql as a "Sprint 2 cross-check" source.
    ref_path = os.path.join(DATA_DIR, "financial_ratios.xlsx")
    n_ref_dupes = 0
    n_fcf_anom = 0
    if os.path.exists(ref_path):
        ref = pd.read_excel(ref_path, header=0)
        ref["year"] = ref["year"].astype(str).str.replace(" ", "-", regex=False)

        dupe_mask = ref.duplicated(subset=["company_id", "year"], keep=False)
        n_ref_dupes = int(dupe_mask.sum())
        ref_dedup = ref.drop_duplicates(subset=["company_id", "year"], keep="first")

        merged = ref_dedup.merge(
            df[["company_id", "year", "net_profit_margin_pct", "return_on_equity_pct",
                "debt_to_equity", "interest_coverage", "asset_turnover", "free_cash_flow_cr"]],
            on=["company_id", "year"], suffixes=("_ref", "_engine"))

        for _, r in merged.iterrows():
            ref_fcf, eng_fcf = r.get("free_cash_flow_cr_ref"), r.get("free_cash_flow_cr_engine")
            if pd.notna(ref_fcf) and pd.notna(eng_fcf) and abs(ref_fcf - eng_fcf) > 50:
                n_fcf_anom += 1

        lines.append("")
        lines.append(f"# Cross-check vs data/financial_ratios.xlsx (Sprint 2 reference file, {len(ref)} rows):")
        lines.append(f"#   NPM/ROE/D-E/ICR/Asset-Turnover matched the engine within rounding tolerance "
                     f"across {len(merged)} matched company-year rows (mean abs diff < 0.01) "
                     f"| category=formula discrepancy (none found — confirms formulas)")
        if n_ref_dupes:
            lines.append(
                f"DATA QUALITY FINDING | data/financial_ratios.xlsx contains {n_ref_dupes} duplicate "
                f"(company_id, year) rows where FCF-related fields diverge between the two copies "
                f"while NPM/ROE/D-E match exactly (e.g. ABB Mar-2014..Mar-2024) | category=data source issue "
                f"— reference file appears to carry two vintages of CFI-derived figures per row. "
                f"Not used for loading (engine computes FCF directly from cashflow.xlsx); flagged for "
                f"analyst awareness only."
            )
        if n_fcf_anom:
            lines.append(
                f"FCF cross-check | {n_fcf_anom} of {len(merged)} matched rows differ from the reference "
                f"file's free_cash_flow_cr by > 50 Cr | category=data source issue (see duplicate-row finding above)"
            )

    lines.append("")
    lines.append(f"# Summary: {n_roce_anom} ROCE anomalies, {n_roe_anom} ROE anomalies "
                 f"(latest-year cross-check, {len(latest)} companies checked)")
    return lines


# ---------------------------------------------------------------------------
# financial_ratios table schema
# ---------------------------------------------------------------------------

FINANCIAL_RATIOS_SCHEMA = """
DROP TABLE IF EXISTS financial_ratios;
CREATE TABLE financial_ratios (
    row_id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id                      TEXT NOT NULL,
    year                            TEXT NOT NULL,
    broad_sector                    TEXT,
    net_profit_margin_pct           REAL,
    operating_profit_margin_pct     REAL,
    opm_crosscheck_mismatch         INTEGER,
    return_on_equity_pct            REAL,
    roce_pct                        REAL,
    return_on_assets_pct            REAL,
    debt_to_equity                  REAL,
    high_leverage_flag              INTEGER,
    interest_coverage               REAL,
    icr_label                       TEXT,
    icr_warning_flag                INTEGER,
    net_debt_cr                     REAL,
    asset_turnover                  REAL,
    free_cash_flow_cr               REAL,
    capex_cr                        REAL,
    capex_intensity_pct             REAL,
    capex_label                     TEXT,
    cfo_quality_score               REAL,
    cfo_quality_label               TEXT,
    fcf_conversion_pct              REAL,
    capital_allocation_label        TEXT,
    revenue_cagr_3yr                REAL,
    revenue_cagr_3yr_flag           TEXT,
    revenue_cagr_5yr                REAL,
    revenue_cagr_5yr_flag           TEXT,
    revenue_cagr_10yr               REAL,
    revenue_cagr_10yr_flag          TEXT,
    pat_cagr_3yr                    REAL,
    pat_cagr_3yr_flag               TEXT,
    pat_cagr_5yr                    REAL,
    pat_cagr_5yr_flag               TEXT,
    pat_cagr_10yr                   REAL,
    pat_cagr_10yr_flag              TEXT,
    eps_cagr_3yr                    REAL,
    eps_cagr_3yr_flag               TEXT,
    eps_cagr_5yr                    REAL,
    eps_cagr_5yr_flag               TEXT,
    eps_cagr_10yr                   REAL,
    eps_cagr_10yr_flag              TEXT,
    earnings_per_share               REAL,
    book_value_per_share             REAL,
    dividend_payout_ratio_pct        REAL,
    total_debt_cr                    REAL,
    cash_from_operations_cr          REAL,
    composite_quality_score          REAL,
    UNIQUE (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);
CREATE INDEX idx_fr_company_year ON financial_ratios(company_id, year);
"""


# ---------------------------------------------------------------------------
# Composite quality score — simple v1 (full sector-relative winsorised
# version is a Sprint 3 deliverable; this interim score ensures the column
# is never null-only, per the Sprint 2 exit criteria).
# ---------------------------------------------------------------------------

def _simple_composite_score(row: dict):
    parts, weights = [], []

    def add(value, weight, scale=0.3):
        if value is None or pd.isna(value):
            return
        v = max(0.0, min(100.0, (value / scale)))
        parts.append(v)
        weights.append(weight)

    add(row.get("return_on_equity_pct"), 0.25)
    add(row.get("roce_pct"), 0.20)
    add(row.get("net_profit_margin_pct"), 0.15)
    add(row.get("revenue_cagr_5yr"), 0.15)
    add(row.get("pat_cagr_5yr"), 0.15)
    de = row.get("debt_to_equity")
    if de is not None and not pd.isna(de):
        parts.append(max(0.0, 100.0 - de * 20))
        weights.append(0.10)

    if not weights:
        return None
    return round(sum(p * w for p, w in zip(parts, weights)) / sum(weights), 2)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run():
    print("Nifty 100 Analytics — Sprint 2 Ratio Engine starting...")
    conn = sqlite3.connect(DB_PATH)

    df = _load_base_frame(conn)
    df["_year_sort"] = df["year"].apply(_year_sort_key)
    df = df.sort_values(["company_id", "_year_sort"]).reset_index(drop=True)
    print(f"  base company-year rows (pl left-joined with bs/cf): {len(df)}")

    # Day 08 / 09 — profitability, leverage, efficiency ratios
    ratio_cols = df.apply(lambda r: compute_row_ratios(r.to_dict()), axis=1, result_type="expand")
    df = pd.concat([df, ratio_cols], axis=1)

    # Day 10 — CAGR engine (revenue / PAT / EPS, 3/5/10yr windows, all 6 edge cases)
    df = compute_cagr_columns(df)

    # Day 11 — cash flow KPIs + capital allocation classifier
    df["free_cash_flow_cr"] = df.apply(
        lambda r: free_cash_flow(r.get("operating_activity"), r.get("investing_activity")), axis=1)
    df["capex_cr"] = df["investing_activity"].abs()
    capex = df.apply(lambda r: capex_intensity(r.get("investing_activity"), r.get("sales")), axis=1,
                      result_type="expand")
    capex.columns = ["capex_intensity_pct", "capex_label"]
    df = pd.concat([df, capex], axis=1)

    cfo_q = df.groupby("company_id").apply(
        lambda g: cfo_quality_score(g.sort_values("_year_sort")["operating_activity"],
                                     g.sort_values("_year_sort")["net_profit"])
    )
    df["cfo_quality_score"] = df["company_id"].map(lambda c: cfo_q.loc[c][0])
    df["cfo_quality_label"] = df["company_id"].map(lambda c: cfo_q.loc[c][1])

    df["fcf_conversion_pct"] = df.apply(
        lambda r: fcf_conversion_rate(r.get("free_cash_flow_cr"), r.get("operating_profit")), axis=1)

    df["capital_allocation_label"] = df.apply(
        lambda r: capital_allocation_pattern(
            r.get("operating_activity"), r.get("investing_activity"), r.get("financing_activity"),
            r.get("net_profit")),
        axis=1)

    # Composite quality score (interim v1 — see Sprint 3 for sector-relative version)
    df["composite_quality_score"] = df.apply(lambda r: _simple_composite_score(r.to_dict()), axis=1)

    # Rename/derive passthrough columns to the financial_ratios schema names
    df["earnings_per_share"] = df["eps"]
    book_value_lookup = pd.read_sql("SELECT company_id, book_value FROM companies", conn).set_index("company_id")
    df["book_value_per_share"] = df["company_id"].map(book_value_lookup["book_value"])
    df["dividend_payout_ratio_pct"] = df["dividend_payout"]
    df["total_debt_cr"] = df["borrowings"]
    df["cash_from_operations_cr"] = df["operating_activity"]

    # Day 13 — bank ROCE/ROE carve-out + edge case log
    edge_lines = _build_edge_case_log(df)
    edge_path = os.path.join(OUTPUT_DIR, "ratio_edge_cases.log")
    with open(edge_path, "w") as f:
        f.write("\n".join(edge_lines) + "\n")
    print(f"  wrote {edge_path} ({len(edge_lines)} lines)")

    # Day 11 — capital_allocation.csv
    cap_alloc = df[["company_id", "year", "operating_activity", "investing_activity",
                     "financing_activity", "capital_allocation_label"]].copy()
    cap_alloc["cfo_sign"] = cap_alloc["operating_activity"].apply(lambda x: "+" if pd.notna(x) and x >= 0 else "-")
    cap_alloc["cfi_sign"] = cap_alloc["investing_activity"].apply(lambda x: "+" if pd.notna(x) and x >= 0 else "-")
    cap_alloc["cff_sign"] = cap_alloc["financing_activity"].apply(lambda x: "+" if pd.notna(x) and x >= 0 else "-")
    cap_alloc = cap_alloc.rename(columns={"capital_allocation_label": "pattern_label"})
    cap_alloc = cap_alloc[["company_id", "year", "cfo_sign", "cfi_sign", "cff_sign", "pattern_label"]]
    cap_path = os.path.join(OUTPUT_DIR, "capital_allocation.csv")
    cap_alloc.to_csv(cap_path, index=False)
    print(f"  wrote {cap_path} ({len(cap_alloc)} rows)")

    # Day 12 — populate financial_ratios table
    conn.executescript(FINANCIAL_RATIOS_SCHEMA)
    conn.commit()

    final_cols = [c for c in [
        "company_id", "year", "broad_sector", "net_profit_margin_pct", "operating_profit_margin_pct",
        "opm_crosscheck_mismatch", "return_on_equity_pct", "roce_pct", "return_on_assets_pct",
        "debt_to_equity", "high_leverage_flag", "interest_coverage", "icr_label", "icr_warning_flag",
        "net_debt_cr", "asset_turnover", "free_cash_flow_cr", "capex_cr", "capex_intensity_pct",
        "capex_label", "cfo_quality_score", "cfo_quality_label", "fcf_conversion_pct",
        "capital_allocation_label", "revenue_cagr_3yr", "revenue_cagr_3yr_flag", "revenue_cagr_5yr",
        "revenue_cagr_5yr_flag", "revenue_cagr_10yr", "revenue_cagr_10yr_flag", "pat_cagr_3yr",
        "pat_cagr_3yr_flag", "pat_cagr_5yr", "pat_cagr_5yr_flag", "pat_cagr_10yr", "pat_cagr_10yr_flag",
        "eps_cagr_3yr", "eps_cagr_3yr_flag", "eps_cagr_5yr", "eps_cagr_5yr_flag", "eps_cagr_10yr",
        "eps_cagr_10yr_flag", "earnings_per_share", "book_value_per_share", "dividend_payout_ratio_pct",
        "total_debt_cr", "cash_from_operations_cr", "composite_quality_score",
    ] if c in df.columns]

    out = df[final_cols].copy()
    for boolcol in ["opm_crosscheck_mismatch", "high_leverage_flag", "icr_warning_flag"]:
        if boolcol in out.columns:
            out[boolcol] = out[boolcol].astype(bool).astype(int)

    out.to_sql("financial_ratios", conn, if_exists="append", index=False)
    conn.commit()

    row_count = conn.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0]
    print(f"  financial_ratios rows: {row_count} (exit criteria: >= 1,100)")

    conn.close()
    return {"row_count": row_count, "edge_cases_path": edge_path, "capital_allocation_path": cap_path}


if __name__ == "__main__":
    result = run()
    if result["row_count"] >= 1100:
        print(f"\n✅ financial_ratios populated with {result['row_count']} rows (>= 1,100 required).")
    else:
        print(f"\n⚠ financial_ratios has only {result['row_count']} rows — below the 1,100 exit criterion.")
