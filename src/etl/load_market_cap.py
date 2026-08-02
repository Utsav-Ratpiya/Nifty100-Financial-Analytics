"""
src/etl/load_market_cap.py — Nifty 100 Analytics
Sprint 3 / Day 15 prerequisite.

Loads market_cap.xlsx into the `market_cap` table WITHOUT touching any
other table (unlike loader.py, which rebuilds the whole DB from scratch).
Run this once after `make load` and before `make screener`/`make ratios`.
"""
from __future__ import annotations

import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from normaliser import normalize_ticker  # noqa: E402
import validator as V  # noqa: E402

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def run():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    # (Re)create just the market_cap table from schema.sql's definition,
    # without dropping anything else.
    conn.execute("DROP TABLE IF EXISTS market_cap")
    conn.execute("""
        CREATE TABLE market_cap (
            row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER,
            company_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            market_cap_crore REAL,
            enterprise_value_crore REAL,
            pe_ratio REAL,
            pb_ratio REAL,
            ev_ebitda REAL,
            dividend_yield_pct REAL,
            UNIQUE (company_id, year),
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mc_company_year ON market_cap(company_id, year)")
    conn.commit()

    valid_ids = set(pd.read_sql("SELECT company_id FROM companies", conn)["company_id"])

    df = pd.read_excel(os.path.join(DATA_DIR, "market_cap.xlsx"), header=0)
    df = df.rename(columns={"id": "source_id"})
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    rows_read = len(df)

    failures = V.dq03_fk_integrity(df, "market_cap", valid_ids)
    df = df[df["company_id"].isin(valid_ids)].copy()

    dupes = df[df.duplicated(subset=["company_id", "year"], keep=False)]
    for (cid, yr), g in dupes.groupby(["company_id", "year"]):
        failures.append(V._fail(cid, "company_id+year",
                                 f"duplicate ({cid}, {yr}) in market_cap ({len(g)} rows)",
                                 "CRITICAL", "DQ-02"))
    df = df.drop_duplicates(subset=["company_id", "year"], keep="first")

    cols = ["source_id", "company_id", "year", "market_cap_crore", "enterprise_value_crore",
            "pe_ratio", "pb_ratio", "ev_ebitda", "dividend_yield_pct"]
    df[cols].to_sql("market_cap", conn, if_exists="append", index=False)
    conn.commit()

    row_count = conn.execute("SELECT COUNT(*) FROM market_cap").fetchone()[0]
    print(f"market_cap loaded: {row_count} rows (read {rows_read}, rejected {rows_read - len(df)})")

    if failures:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        fail_path = os.path.join(OUTPUT_DIR, "validation_failures.csv")
        existing = pd.read_csv(fail_path) if os.path.exists(fail_path) else pd.DataFrame(
            columns=["rule_id", "company_id", "field", "issue", "severity"])
        combined = pd.concat([existing, pd.DataFrame(failures)], ignore_index=True)
        combined.to_csv(fail_path, index=False)
        print(f"appended {len(failures)} DQ findings to {fail_path}")

    conn.close()
    return row_count


if __name__ == "__main__":
    run()
