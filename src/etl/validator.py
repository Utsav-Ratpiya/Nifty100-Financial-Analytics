"""
validator.py — Nifty 100 Analytics ETL
Sprint 1 / Day 03 deliverable: 16 data-quality rules (DQ-01 .. DQ-16).

Each rule returns a list of failure dicts:
    {company_id, field, issue, severity, rule_id}

severity is one of: CRITICAL, WARNING
CRITICAL failures are excluded from the final SQLite load (loader.py drops
these rows) since they would violate PK/FK constraints or represent data
that cannot be reasoned about downstream.
WARNING failures are loaded as-is but logged for analyst review
(output/validation_failures.csv) -- e.g. an OPM mismatch or a stale URL
doesn't stop the row from being usable.
"""
from __future__ import annotations

import re
from typing import List, Dict, Any
import pandas as pd


def _fail(company_id, field, issue, severity, rule_id) -> Dict[str, Any]:
    return {
        "rule_id": rule_id,
        "company_id": company_id,
        "field": field,
        "issue": issue,
        "severity": severity,
    }


# ---------------------------------------------------------------------------
# DQ-01 / DQ-02: PK uniqueness
# ---------------------------------------------------------------------------

def dq01_pk_uniqueness(df: pd.DataFrame, table_name: str, pk_col: str = "source_id") -> List[dict]:
    failures = []
    if pk_col not in df.columns:
        return failures
    dupes = df[df.duplicated(subset=[pk_col], keep=False)]
    for sid, group in dupes.groupby(pk_col):
        cid = group["company_id"].iloc[0] if "company_id" in group.columns else None
        failures.append(_fail(cid, pk_col, f"duplicate {pk_col}={sid} in {table_name} ({len(group)} rows)",
                               "CRITICAL", "DQ-01"))
    return failures


def dq02_composite_key_uniqueness(df: pd.DataFrame, table_name: str) -> List[dict]:
    failures = []
    if not {"company_id", "year"}.issubset(df.columns):
        return failures
    dupes = df[df.duplicated(subset=["company_id", "year"], keep=False)]
    for (cid, yr), group in dupes.groupby(["company_id", "year"]):
        failures.append(_fail(cid, "company_id+year",
                               f"duplicate ({cid}, {yr}) in {table_name} ({len(group)} rows)",
                               "CRITICAL", "DQ-02"))
    return failures


# ---------------------------------------------------------------------------
# DQ-03: FK integrity
# ---------------------------------------------------------------------------

def dq03_fk_integrity(df: pd.DataFrame, table_name: str, valid_company_ids: set) -> List[dict]:
    failures = []
    if "company_id" not in df.columns:
        return failures
    orphans = df[~df["company_id"].isin(valid_company_ids)]
    for cid in orphans["company_id"].unique():
        n = (orphans["company_id"] == cid).sum()
        failures.append(_fail(cid, "company_id",
                               f"{cid} in {table_name} has no matching row in companies ({n} rows)",
                               "CRITICAL", "DQ-03"))
    return failures


# ---------------------------------------------------------------------------
# DQ-04: Balance sheet balances (assets == liabilities within 1%)
# ---------------------------------------------------------------------------

def dq04_bs_balance(df: pd.DataFrame) -> List[dict]:
    failures = []
    for _, row in df.iterrows():
        ta, tl = row.get("total_assets"), row.get("total_liabilities")
        if pd.isna(ta) or pd.isna(tl) or tl == 0:
            continue
        diff_pct = abs(ta - tl) / abs(tl) * 100
        if diff_pct > 1.0:
            failures.append(_fail(row["company_id"], "total_assets/total_liabilities",
                                   f"BS imbalance {diff_pct:.2f}% at year={row.get('year')}",
                                   "WARNING", "DQ-04"))
    return failures


# ---------------------------------------------------------------------------
# DQ-05: OPM cross-check
# ---------------------------------------------------------------------------

def dq05_opm_crosscheck(df: pd.DataFrame) -> List[dict]:
    failures = []
    for _, row in df.iterrows():
        sales, op, opm = row.get("sales"), row.get("operating_profit"), row.get("opm_percentage")
        if pd.isna(sales) or pd.isna(op) or pd.isna(opm) or sales == 0:
            continue
        computed = op / sales * 100
        if abs(computed - opm) > 1.0:
            failures.append(_fail(row["company_id"], "opm_percentage",
                                   f"OPM mismatch at year={row.get('year')}: computed={computed:.2f} vs stored={opm}",
                                   "WARNING", "DQ-05"))
    return failures


# ---------------------------------------------------------------------------
# DQ-06: Positive sales
# ---------------------------------------------------------------------------

def dq06_positive_sales(df: pd.DataFrame) -> List[dict]:
    failures = []
    bad = df[df["sales"].notna() & (df["sales"] <= 0)]
    for _, row in bad.iterrows():
        failures.append(_fail(row["company_id"], "sales",
                               f"non-positive sales={row['sales']} at year={row.get('year')}",
                               "WARNING", "DQ-06"))
    return failures


# ---------------------------------------------------------------------------
# DQ-07: Net cash flow consistency
# ---------------------------------------------------------------------------

def dq07_net_cash_consistency(df: pd.DataFrame) -> List[dict]:
    failures = []
    for _, row in df.iterrows():
        parts = [row.get("operating_activity"), row.get("investing_activity"), row.get("financing_activity")]
        ncf = row.get("net_cash_flow")
        if any(pd.isna(p) for p in parts) or pd.isna(ncf):
            continue
        computed = sum(parts)
        if abs(computed - ncf) > 1:  # tolerance of 1 crore for rounding
            failures.append(_fail(row["company_id"], "net_cash_flow",
                                   f"CFO+CFI+CFF={computed} != stored net_cash_flow={ncf} at year={row.get('year')}",
                                   "WARNING", "DQ-07"))
    return failures


# ---------------------------------------------------------------------------
# DQ-08: Tax rate sanity
# ---------------------------------------------------------------------------

def dq08_tax_rate_sanity(df: pd.DataFrame) -> List[dict]:
    failures = []
    bad = df[df["tax_percentage"].notna() & ((df["tax_percentage"] < -10) | (df["tax_percentage"] > 60))]
    for _, row in bad.iterrows():
        failures.append(_fail(row["company_id"], "tax_percentage",
                               f"tax_percentage={row['tax_percentage']} outside sane range at year={row.get('year')}",
                               "WARNING", "DQ-08"))
    return failures


# ---------------------------------------------------------------------------
# DQ-09: Dividend payout cap
# ---------------------------------------------------------------------------

def dq09_dividend_payout_cap(df: pd.DataFrame) -> List[dict]:
    failures = []
    bad = df[df["dividend_payout"].notna() & ((df["dividend_payout"] < 0) | (df["dividend_payout"] > 150))]
    for _, row in bad.iterrows():
        failures.append(_fail(row["company_id"], "dividend_payout",
                               f"dividend_payout={row['dividend_payout']} outside 0-150% at year={row.get('year')}",
                               "WARNING", "DQ-09"))
    return failures


# ---------------------------------------------------------------------------
# DQ-10: URL validity
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def dq10_url_validity(df: pd.DataFrame) -> List[dict]:
    failures = []
    bad = df[df["annual_report_url"].notna() & (~df["annual_report_url"].astype(str).str.match(_URL_RE))]
    for _, row in bad.iterrows():
        failures.append(_fail(row["company_id"], "annual_report_url",
                               f"malformed URL at year={row.get('year')}: {row['annual_report_url']!r}",
                               "WARNING", "DQ-10"))
    return failures


# ---------------------------------------------------------------------------
# DQ-11: EPS sign consistency
# ---------------------------------------------------------------------------

def dq11_eps_sign_consistency(df: pd.DataFrame) -> List[dict]:
    failures = []
    for _, row in df.iterrows():
        np_, eps = row.get("net_profit"), row.get("eps")
        if pd.isna(np_) or pd.isna(eps) or np_ == 0 or eps == 0:
            continue
        if (np_ > 0) != (eps > 0):
            failures.append(_fail(row["company_id"], "eps",
                                   f"sign mismatch: net_profit={np_}, eps={eps} at year={row.get('year')}",
                                   "WARNING", "DQ-11"))
    return failures


# ---------------------------------------------------------------------------
# DQ-12: Balance sheet component check (BS components sum to total liabilities)
# ---------------------------------------------------------------------------

def dq12_bs_components(df: pd.DataFrame) -> List[dict]:
    failures = []
    for _, row in df.iterrows():
        parts = [row.get("equity_capital"), row.get("reserves"), row.get("borrowings"), row.get("other_liabilities")]
        tl = row.get("total_liabilities")
        if any(pd.isna(p) for p in parts) or pd.isna(tl) or tl == 0:
            continue
        computed = sum(parts)
        diff_pct = abs(computed - tl) / abs(tl) * 100
        if diff_pct > 1.0:
            failures.append(_fail(row["company_id"], "total_liabilities components",
                                   f"components sum to {computed}, stored total={tl} ({diff_pct:.2f}% off) at year={row.get('year')}",
                                   "WARNING", "DQ-12"))
    return failures


# ---------------------------------------------------------------------------
# DQ-13: Year coverage (company has at least 1 year of core financial data)
# ---------------------------------------------------------------------------

def dq13_year_coverage(pl_df: pd.DataFrame, bs_df: pd.DataFrame, cf_df: pd.DataFrame,
                       all_company_ids: set) -> List[dict]:
    failures = []
    covered = set(pl_df["company_id"]) | set(bs_df["company_id"]) | set(cf_df["company_id"])
    for cid in sorted(all_company_ids - covered):
        failures.append(_fail(cid, "year_coverage",
                               "company has zero records across P&L, Balance Sheet, and Cash Flow",
                               "WARNING", "DQ-13"))
    return failures


# ---------------------------------------------------------------------------
# DQ-14: Stock price positivity
# ---------------------------------------------------------------------------

def dq14_stock_price_positivity(df: pd.DataFrame) -> List[dict]:
    failures = []
    price_cols = ["open_price", "high_price", "low_price", "close_price", "adjusted_close"]
    for col in price_cols:
        if col not in df.columns:
            continue
        bad = df[df[col].notna() & (df[col] <= 0)]
        for _, row in bad.iterrows():
            failures.append(_fail(row["company_id"], col,
                                   f"non-positive {col}={row[col]} at date={row.get('price_date')}",
                                   "WARNING", "DQ-14"))
    return failures


# ---------------------------------------------------------------------------
# DQ-15: Sector completeness
# ---------------------------------------------------------------------------

def dq15_sector_completeness(sectors_df: pd.DataFrame, all_company_ids: set) -> List[dict]:
    failures = []
    covered = set(sectors_df["company_id"])
    for cid in sorted(all_company_ids - covered):
        failures.append(_fail(cid, "broad_sector",
                               "company has no sector assignment",
                               "WARNING", "DQ-15"))
    return failures


# ---------------------------------------------------------------------------
# DQ-16: Peer group benchmark uniqueness
# ---------------------------------------------------------------------------

def dq16_peer_benchmark_uniqueness(peer_df: pd.DataFrame) -> List[dict]:
    failures = []
    for group_name, group in peer_df.groupby("peer_group_name"):
        n_benchmarks = int(group["is_benchmark"].sum())
        if n_benchmarks != 1:
            failures.append(_fail(None, "is_benchmark",
                                   f"peer group '{group_name}' has {n_benchmarks} benchmark companies (expected 1)",
                                   "WARNING", "DQ-16"))
    return failures


DQ_RULE_DESCRIPTIONS = {
    "DQ-01": "PK uniqueness (per-table source_id)",
    "DQ-02": "(company_id, year) composite key uniqueness",
    "DQ-03": "FK integrity — company_id must exist in companies",
    "DQ-04": "Balance sheet balances (assets == liabilities, <1% diff)",
    "DQ-05": "OPM cross-check (computed vs stored opm_percentage)",
    "DQ-06": "Positive sales",
    "DQ-07": "Net cash flow consistency (CFO+CFI+CFF == net_cash_flow)",
    "DQ-08": "Tax rate sanity range",
    "DQ-09": "Dividend payout cap (0-150%)",
    "DQ-10": "Annual report URL validity",
    "DQ-11": "EPS sign consistency with net_profit",
    "DQ-12": "Balance sheet component sum check",
    "DQ-13": "Year coverage — company has >=1 year of core financial data",
    "DQ-14": "Stock price positivity",
    "DQ-15": "Sector completeness — every company has a sector",
    "DQ-16": "Peer group benchmark uniqueness (exactly 1 per group)",
}
