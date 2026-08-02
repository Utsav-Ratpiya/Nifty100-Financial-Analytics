"""
loader.py — Nifty 100 Analytics ETL
Sprint 1 / Day 02, 04, 05 deliverable.

Loads the 7 core + 3 supplementary source Excel files (10 tables total —
see db/schema.sql for why market_cap.xlsx and the source financial_ratios.xlsx
are excluded from this base load) into nifty100.db, running all 16 DQ rules
along the way. CRITICAL-severity rows are excluded from the load; WARNING
rows are loaded as-is. Produces:

    nifty100.db                    — populated SQLite database
    output/load_audit.csv          — per-table row counts & rejections
    output/validation_failures.csv — every DQ violation with severity

Usage:
    python src/etl/loader.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from normaliser import normalize_ticker, normalize_year  # noqa: E402
import validator as V  # noqa: E402

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "db", "schema.sql")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

os.makedirs(OUTPUT_DIR, exist_ok=True)

ALL_FAILURES: list[dict] = []
LOAD_AUDIT: list[dict] = []


def _record_audit(table, source_file, rows_read, rows_loaded, rows_rejected, notes=""):
    LOAD_AUDIT.append({
        "table": table,
        "source_file": source_file,
        "rows_read": rows_read,
        "rows_loaded": rows_loaded,
        "rows_rejected": rows_rejected,
        "notes": notes,
        "loaded_at": datetime.now(timezone.utc).isoformat(),
    })


def _apply_year_normalisation(df: pd.DataFrame, year_col: str = "year") -> pd.DataFrame:
    df = df.copy()
    df["raw_year"] = df[year_col]
    labels, reasons = [], []
    for raw in df[year_col]:
        label, reason = normalize_year(raw)
        labels.append(label)
        reasons.append(reason)
    df[year_col] = labels
    df["_year_parse_reason"] = reasons
    return df


def _apply_ticker_normalisation(df: pd.DataFrame, col: str = "company_id") -> pd.DataFrame:
    df = df.copy()
    df[col] = df[col].apply(normalize_ticker)
    return df


def init_db() -> sqlite3.Connection:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


def load_companies(conn) -> set:
    path = os.path.join(DATA_DIR, "companies.xlsx")
    df = pd.read_excel(path, header=1)
    df = df.rename(columns={"id": "company_id"})
    df = _apply_ticker_normalisation(df, "company_id")
    rows_read = len(df)

    dupes = df[df.duplicated(subset=["company_id"], keep=False)]
    for cid in dupes["company_id"].unique():
        ALL_FAILURES.append(V._fail(cid, "company_id", "duplicate company_id in companies.xlsx",
                                     "CRITICAL", "DQ-01"))
    df = df.drop_duplicates(subset=["company_id"], keep="first")

    cols = ["company_id", "company_logo", "company_name", "chart_link", "about_company",
            "website", "nse_profile", "bse_profile", "face_value", "book_value",
            "roce_percentage", "roe_percentage"]
    df[cols].to_sql("companies", conn, if_exists="append", index=False)
    conn.commit()

    rejected = rows_read - len(df)
    _record_audit("companies", "companies.xlsx", rows_read, len(df), rejected)
    return set(df["company_id"])


def _load_financial_table(conn, table_name, file_name, sheet_col_map, valid_company_ids):
    """Shared loader for profitandloss / balancesheet / cashflow (Mon-YYYY periods)."""
    path = os.path.join(DATA_DIR, file_name)
    df = pd.read_excel(path, header=1)
    df = df.rename(columns={"id": "source_id"})
    df = _apply_ticker_normalisation(df, "company_id")
    df = _apply_year_normalisation(df, "year")
    rows_read = len(df)

    # Log WARNING for rows where year parsing stripped trailing junk
    for _, row in df.iterrows():
        reason = row["_year_parse_reason"]
        if isinstance(reason, str) and reason.startswith("trailing_junk_stripped"):
            ALL_FAILURES.append(V._fail(row["company_id"], "year",
                                         f"{table_name}: {reason} (raw='{row['raw_year']}')",
                                         "WARNING", "DQ-02"))

    # CRITICAL: unparseable year -> drop
    unparseable = df[df["year"].isna()]
    for _, row in unparseable.iterrows():
        ALL_FAILURES.append(V._fail(row["company_id"], "year",
                                     f"{table_name}: could not parse year (raw='{row['raw_year']}')",
                                     "CRITICAL", "DQ-02"))
    df = df[df["year"].notna()].copy()

    # DQ-01: source_id uniqueness
    ALL_FAILURES.extend(V.dq01_pk_uniqueness(df, table_name))
    # DQ-02: composite key uniqueness
    dup_failures = V.dq02_composite_key_uniqueness(df, table_name)
    ALL_FAILURES.extend(dup_failures)
    df = df.drop_duplicates(subset=["company_id", "year"], keep="first")

    # DQ-03: FK integrity -> CRITICAL, exclude orphans from load
    fk_failures = V.dq03_fk_integrity(df, table_name, valid_company_ids)
    ALL_FAILURES.extend(fk_failures)
    df = df[df["company_id"].isin(valid_company_ids)].copy()

    # Table-specific WARNING rules
    if table_name == "profitandloss":
        ALL_FAILURES.extend(V.dq05_opm_crosscheck(df))
        ALL_FAILURES.extend(V.dq06_positive_sales(df))
        ALL_FAILURES.extend(V.dq08_tax_rate_sanity(df))
        ALL_FAILURES.extend(V.dq09_dividend_payout_cap(df))
        ALL_FAILURES.extend(V.dq11_eps_sign_consistency(df))
    elif table_name == "balancesheet":
        ALL_FAILURES.extend(V.dq04_bs_balance(df))
        ALL_FAILURES.extend(V.dq12_bs_components(df))
    elif table_name == "cashflow":
        ALL_FAILURES.extend(V.dq07_net_cash_consistency(df))

    keep_cols = ["source_id", "company_id", "year", "raw_year"] + sheet_col_map
    df[keep_cols].to_sql(table_name, conn, if_exists="append", index=False)
    conn.commit()

    rejected = rows_read - len(df)
    _record_audit(table_name, file_name, rows_read, len(df), rejected)


def load_profitandloss(conn, valid_company_ids):
    cols = ["sales", "expenses", "operating_profit", "opm_percentage", "other_income",
            "interest", "depreciation", "profit_before_tax", "tax_percentage",
            "net_profit", "eps", "dividend_payout"]
    _load_financial_table(conn, "profitandloss", "profitandloss.xlsx", cols, valid_company_ids)


def load_balancesheet(conn, valid_company_ids):
    cols = ["equity_capital", "reserves", "borrowings", "other_liabilities",
            "total_liabilities", "fixed_assets", "cwip", "investments",
            "other_asset", "total_assets"]
    _load_financial_table(conn, "balancesheet", "balancesheet.xlsx", cols, valid_company_ids)


def load_cashflow(conn, valid_company_ids):
    cols = ["operating_activity", "investing_activity", "financing_activity", "net_cash_flow"]
    _load_financial_table(conn, "cashflow", "cashflow.xlsx", cols, valid_company_ids)


def load_analysis(conn, valid_company_ids):
    path = os.path.join(DATA_DIR, "analysis.xlsx")
    df = pd.read_excel(path, header=1)
    df = df.rename(columns={"id": "source_id"})
    df = _apply_ticker_normalisation(df, "company_id")
    rows_read = len(df)

    fk_failures = V.dq03_fk_integrity(df, "analysis", valid_company_ids)
    ALL_FAILURES.extend(fk_failures)
    df = df[df["company_id"].isin(valid_company_ids)].copy()

    cols = ["source_id", "company_id", "compounded_sales_growth", "compounded_profit_growth",
            "stock_price_cagr", "roe"]
    df[cols].to_sql("analysis", conn, if_exists="append", index=False)
    conn.commit()
    _record_audit("analysis", "analysis.xlsx", rows_read, len(df), rows_read - len(df))


def load_documents(conn, valid_company_ids):
    path = os.path.join(DATA_DIR, "documents.xlsx")
    df = pd.read_excel(path, header=1)
    df = df.rename(columns={"id": "source_id", "Year": "year", "Annual_Report": "annual_report_url"})
    df = _apply_ticker_normalisation(df, "company_id")
    rows_read = len(df)

    fk_failures = V.dq03_fk_integrity(df, "documents", valid_company_ids)
    ALL_FAILURES.extend(fk_failures)
    df = df[df["company_id"].isin(valid_company_ids)].copy()

    ALL_FAILURES.extend(V.dq10_url_validity(df))

    cols = ["source_id", "company_id", "year", "annual_report_url"]
    df[cols].to_sql("documents", conn, if_exists="append", index=False)
    conn.commit()
    _record_audit("documents", "documents.xlsx", rows_read, len(df), rows_read - len(df))


def load_prosandcons(conn, valid_company_ids):
    path = os.path.join(DATA_DIR, "prosandcons.xlsx")
    df = pd.read_excel(path, header=1)
    df = df.rename(columns={"id": "source_id"})
    df = _apply_ticker_normalisation(df, "company_id")
    rows_read = len(df)

    fk_failures = V.dq03_fk_integrity(df, "prosandcons", valid_company_ids)
    ALL_FAILURES.extend(fk_failures)
    df = df[df["company_id"].isin(valid_company_ids)].copy()

    cols = ["source_id", "company_id", "pros", "cons"]
    df[cols].to_sql("prosandcons", conn, if_exists="append", index=False)
    conn.commit()
    _record_audit("prosandcons", "prosandcons.xlsx", rows_read, len(df), rows_read - len(df))


def load_sectors(conn, valid_company_ids):
    path = os.path.join(DATA_DIR, "sectors.xlsx")
    df = pd.read_excel(path, header=0)
    df = df.rename(columns={"id": "source_id"})
    df = _apply_ticker_normalisation(df, "company_id")
    rows_read = len(df)

    fk_failures = V.dq03_fk_integrity(df, "sectors", valid_company_ids)
    ALL_FAILURES.extend(fk_failures)
    df = df[df["company_id"].isin(valid_company_ids)].copy()

    ALL_FAILURES.extend(V.dq15_sector_completeness(df, valid_company_ids))

    cols = ["source_id", "company_id", "broad_sector", "sub_sector", "index_weight_pct", "market_cap_category"]
    df[cols].to_sql("sectors", conn, if_exists="append", index=False)
    conn.commit()
    _record_audit("sectors", "sectors.xlsx", rows_read, len(df), rows_read - len(df))


def load_stock_prices(conn, valid_company_ids):
    path = os.path.join(DATA_DIR, "stock_prices.xlsx")
    df = pd.read_excel(path, header=0)
    df = df.rename(columns={"id": "source_id", "date": "price_date"})
    df = _apply_ticker_normalisation(df, "company_id")
    rows_read = len(df)

    fk_failures = V.dq03_fk_integrity(df, "stock_prices", valid_company_ids)
    ALL_FAILURES.extend(fk_failures)
    df = df[df["company_id"].isin(valid_company_ids)].copy()

    df["price_date"] = pd.to_datetime(df["price_date"]).dt.strftime("%Y-%m-%d")
    dupes = df[df.duplicated(subset=["company_id", "price_date"], keep=False)]
    for (cid, dt), g in dupes.groupby(["company_id", "price_date"]):
        ALL_FAILURES.append(V._fail(cid, "company_id+price_date",
                                     f"duplicate ({cid}, {dt}) in stock_prices ({len(g)} rows)",
                                     "CRITICAL", "DQ-02"))
    df = df.drop_duplicates(subset=["company_id", "price_date"], keep="first")

    ALL_FAILURES.extend(V.dq14_stock_price_positivity(df))

    df["is_simulated"] = 1  # per project rule: stock_prices is a simulated dataset

    cols = ["source_id", "company_id", "price_date", "open_price", "high_price", "low_price",
            "close_price", "volume", "adjusted_close", "is_simulated"]
    df[cols].to_sql("stock_prices", conn, if_exists="append", index=False)
    conn.commit()
    _record_audit("stock_prices", "stock_prices.xlsx", rows_read, len(df), rows_read - len(df),
                  notes="SIMULATED dataset per project rules")


def load_peer_groups(conn, valid_company_ids):
    path = os.path.join(DATA_DIR, "peer_groups.xlsx")
    df = pd.read_excel(path, header=0)
    df = df.rename(columns={"id": "source_id"})
    df = _apply_ticker_normalisation(df, "company_id")
    rows_read = len(df)

    fk_failures = V.dq03_fk_integrity(df, "peer_groups", valid_company_ids)
    ALL_FAILURES.extend(fk_failures)
    df = df[df["company_id"].isin(valid_company_ids)].copy()

    df["is_benchmark"] = df["is_benchmark"].astype(bool).astype(int)
    ALL_FAILURES.extend(V.dq16_peer_benchmark_uniqueness(df))

    cols = ["source_id", "peer_group_name", "company_id", "is_benchmark"]
    df[cols].to_sql("peer_groups", conn, if_exists="append", index=False)
    conn.commit()
    _record_audit("peer_groups", "peer_groups.xlsx", rows_read, len(df), rows_read - len(df))


def run():
    print("Nifty 100 Analytics — ETL load starting...")
    conn = init_db()

    valid_company_ids = load_companies(conn)
    print(f"  companies loaded: {len(valid_company_ids)}")

    load_profitandloss(conn, valid_company_ids)
    load_balancesheet(conn, valid_company_ids)
    load_cashflow(conn, valid_company_ids)
    load_analysis(conn, valid_company_ids)
    load_documents(conn, valid_company_ids)
    load_prosandcons(conn, valid_company_ids)
    load_sectors(conn, valid_company_ids)
    load_stock_prices(conn, valid_company_ids)
    load_peer_groups(conn, valid_company_ids)

    # DQ-13: year coverage, needs all 3 core financial tables together
    pl = pd.read_sql("SELECT company_id FROM profitandloss", conn)
    bs = pd.read_sql("SELECT company_id FROM balancesheet", conn)
    cf = pd.read_sql("SELECT company_id FROM cashflow", conn)
    ALL_FAILURES.extend(V.dq13_year_coverage(pl, bs, cf, valid_company_ids))

    # PRAGMA foreign_key_check must return 0 rows
    fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
    print(f"  PRAGMA foreign_key_check violations: {len(fk_check)}")

    conn.close()

    # Write load_audit.csv
    audit_df = pd.DataFrame(LOAD_AUDIT)
    audit_path = os.path.join(OUTPUT_DIR, "load_audit.csv")
    audit_df.to_csv(audit_path, index=False)
    print(f"  wrote {audit_path} ({len(audit_df)} rows)")

    # Write validation_failures.csv
    failures_df = pd.DataFrame(ALL_FAILURES, columns=["rule_id", "company_id", "field", "issue", "severity"])
    failures_path = os.path.join(OUTPUT_DIR, "validation_failures.csv")
    failures_df.to_csv(failures_path, index=False)
    n_critical = (failures_df["severity"] == "CRITICAL").sum() if len(failures_df) else 0
    n_warning = (failures_df["severity"] == "WARNING").sum() if len(failures_df) else 0
    print(f"  wrote {failures_path} ({len(failures_df)} rows: {n_critical} CRITICAL, {n_warning} WARNING)")

    print("\nSummary:")
    print(audit_df[["table", "rows_read", "rows_loaded", "rows_rejected"]].to_string(index=False))

    return {
        "fk_violations": len(fk_check),
        "critical_failures": int(n_critical),
        "warning_failures": int(n_warning),
    }


if __name__ == "__main__":
    result = run()
    if result["fk_violations"] > 0 or result["critical_failures"] > 0:
        print(f"\n⚠ Load completed with {result['critical_failures']} CRITICAL DQ issues excluded "
              f"and {result['fk_violations']} residual FK violations.")
    else:
        print("\n✅ Load completed cleanly: 0 CRITICAL issues, 0 FK violations.")
