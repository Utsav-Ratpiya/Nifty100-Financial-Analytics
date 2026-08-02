"""
src/analytics/peer.py — Nifty 100 Analytics
Sprint 3 / Day 18: peer percentile rankings.

Loads peer_groups (11 groups) and computes PERCENT_RANK for 10 metrics
within each group, using the latest fiscal year per company from the
screener universe. D/E is inverted (lower D/E = higher percentile, since
lower leverage is "better"). Populates the peer_percentiles table.
"""
from __future__ import annotations

import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "screener"))

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")

# metric_name -> (universe column, invert_direction)
# invert=True means a LOWER raw value should get a HIGHER percentile rank.
METRICS = {
    "ROE": ("return_on_equity_pct", False),
    "ROCE": ("roce_pct", False),
    "Net Profit Margin": ("net_profit_margin_pct", False),
    "D/E": ("debt_to_equity", True),
    "FCF": ("free_cash_flow_cr", False),
    "PAT CAGR 5yr": ("pat_cagr_5yr", False),
    "Revenue CAGR 5yr": ("revenue_cagr_5yr", False),
    "EPS CAGR 5yr": ("eps_cagr_5yr", False),
    "Interest Coverage": ("interest_coverage", False),
    "Asset Turnover": ("asset_turnover", False),
}


def _percent_rank(series: pd.Series) -> pd.Series:
    """Excel-style PERCENT_RANK.INC: rank / (n-1), 0 for the lowest value,
    1 for the highest. NaNs are excluded from ranking (kept as NaN)."""
    valid = series.dropna()
    if len(valid) <= 1:
        return pd.Series(0.5, index=series.index).where(series.notna())
    ranks = valid.rank(method="average", ascending=True)
    pct = (ranks - 1) / (len(valid) - 1)
    return pct.reindex(series.index)


def compute_peer_percentiles(universe: pd.DataFrame, peer_groups: pd.DataFrame) -> pd.DataFrame:
    """Returns long-format rows: company_id, peer_group_name, metric, value, percentile_rank, year."""
    merged = peer_groups.merge(universe, on="company_id", how="left")
    records = []

    for group_name, g in merged.groupby("peer_group_name"):
        for metric_name, (col, invert) in METRICS.items():
            if col not in g.columns:
                continue
            values = g[col]
            pct = _percent_rank(values)
            if invert:
                pct = 1 - pct
                # re-mask: invert of NaN stays NaN
                pct[values.isna()] = None
            for idx, row in g.iterrows():
                records.append({
                    "company_id": row["company_id"],
                    "peer_group_name": group_name,
                    "metric": metric_name,
                    "value": values.loc[idx] if pd.notna(values.loc[idx]) else None,
                    "percentile_rank": pct.loc[idx] if pd.notna(pct.loc[idx]) else None,
                    "year": row.get("year"),
                })

    return pd.DataFrame(records)


def companies_without_peer_group(all_company_ids: set, peer_groups: pd.DataFrame) -> list:
    grouped = set(peer_groups["company_id"])
    return sorted(all_company_ids - grouped)


def run():
    conn = sqlite3.connect(DB_PATH)
    from universe import build_universe  # local import, avoids circular path issues

    universe = build_universe(conn)
    peer_groups = pd.read_sql("SELECT company_id, peer_group_name, is_benchmark FROM peer_groups", conn)
    all_ids = set(pd.read_sql("SELECT company_id FROM companies", conn)["company_id"])

    result = compute_peer_percentiles(universe, peer_groups)

    conn.execute("DROP TABLE IF EXISTS peer_percentiles")
    conn.execute("""
        CREATE TABLE peer_percentiles (
            row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT NOT NULL,
            peer_group_name TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL,
            percentile_rank REAL,
            year TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)
    result.to_sql("peer_percentiles", conn, if_exists="append", index=False)
    conn.commit()

    no_peer = companies_without_peer_group(all_ids, peer_groups)
    print(f"peer_percentiles populated: {len(result)} rows across {peer_groups['peer_group_name'].nunique()} groups")
    if no_peer:
        print(f"No peer group assigned for {len(no_peer)} companies: {no_peer}")

    conn.close()
    return result, no_peer


if __name__ == "__main__":
    run()
