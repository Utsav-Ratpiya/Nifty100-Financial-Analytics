"""
src/analytics/composite_score.py — Nifty 100 Analytics
Sprint 3 / Day 17.

Replaces the Sprint 2 placeholder composite_quality_score (a simple clipped
average) with the specified version:

    35% Profitability  = ROE(15%) + ROCE(10%) + NPM(10%)
    30% Cash Quality    = FCF CAGR(15%) + CFO/PAT ratio(10%) + FCF positive flag(5%)
    20% Growth          = Revenue CAGR 5yr(10%) + PAT CAGR 5yr(10%)
    15% Leverage        = D/E score(10%) + ICR score(5%)

Each input metric is winsorised at its P10/P90 (across the 92-company
universe) before being scaled to 0-100, so a handful of extreme values
(e.g. a company with 900% ROE) don't blow out the whole scale. The score
is also computed SECTOR-RELATIVE: winsorisation percentiles and the 0-100
scaling are both computed within each broad_sector, so a company is scored
against its peers, not the whole market (a bank's D/E means something very
different from a software company's).

There's no "FCF CAGR" column already in financial_ratios (Sprint 2 built
free_cash_flow_cr per year, not its CAGR) -- it's derived here from the
chronological FCF series per company.
"""
from __future__ import annotations

import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # -> src/, so 'screener.*' resolves
from cagr import cagr_with_flag  # noqa: E402

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")


def _winsorized_scale(series: pd.Series) -> pd.Series:
    """Winsorize at P10/P90, then min-max scale the winsorized values to 0-100.
    NaNs pass through as NaN (excluded from the composite average, not
    treated as zero)."""
    valid = series.dropna()
    if len(valid) < 3:
        return pd.Series(np.nan, index=series.index)
    p10, p90 = valid.quantile(0.10), valid.quantile(0.90)
    clipped = series.clip(lower=p10, upper=p90)
    if p90 == p10:
        return pd.Series(50.0, index=series.index).where(series.notna())
    return (clipped - p10) / (p90 - p10) * 100


def _de_score(de: pd.Series) -> pd.Series:
    """Lower D/E is better -- invert before scaling (higher = better leverage profile)."""
    inverted = -de
    return _winsorized_scale(inverted)


def _icr_score(icr: pd.Series, icr_label: pd.Series) -> pd.Series:
    """Debt-free (icr_label == 'Debt Free') scores 100 outright; otherwise
    winsorized-scaled ICR."""
    effective = icr.copy()
    scaled = _winsorized_scale(effective)
    scaled[icr_label == "Debt Free"] = 100.0
    return scaled


def compute_fcf_cagr_5yr(conn) -> pd.Series:
    """Per-company 5yr FCF CAGR, computed from the chronological
    free_cash_flow_cr series in financial_ratios (excluding TTM)."""
    fr = pd.read_sql("SELECT company_id, year, free_cash_flow_cr FROM financial_ratios WHERE year != 'TTM'", conn)
    fr["_cal_year"] = fr["year"].str.split("-").str[1].astype(int)
    fr = fr.sort_values(["company_id", "_cal_year"])

    results = {}
    for cid, g in fr.groupby("company_id"):
        series = g["free_cash_flow_cr"].tolist()
        if len(series) < 6:
            results[cid] = None
            continue
        start, end = series[-6], series[-1]
        value, _flag = cagr_with_flag(start, end, 5)
        results[cid] = value
    return pd.Series(results, name="fcf_cagr_5yr")


def compute_composite_scores(universe: pd.DataFrame, conn) -> pd.Series:
    """Sector-relative composite quality score (0-100) per company, per the
    Sprint 3 Day 17 spec. `universe` must have one row per company with
    broad_sector, return_on_equity_pct, roce_pct, net_profit_margin_pct,
    cfo_quality_score, revenue_cagr_5yr, pat_cagr_5yr, debt_to_equity,
    interest_coverage, icr_label, free_cash_flow_cr."""
    df = universe.copy()
    fcf_cagr = compute_fcf_cagr_5yr(conn)
    df = df.merge(fcf_cagr.rename("fcf_cagr_5yr"), left_on="company_id", right_index=True, how="left")
    df["fcf_positive_flag"] = (df["free_cash_flow_cr"] > 0).astype(float) * 100

    scores = pd.Series(0.0, index=df.index)
    weight_sum = pd.Series(0.0, index=df.index)

    def add(component: pd.Series, weight: float):
        nonlocal scores, weight_sum
        valid = component.notna()
        scores.loc[valid] += component.loc[valid] * weight
        weight_sum.loc[valid] += weight

    for sector, g in df.groupby("broad_sector"):
        idx = g.index

        roe_s = _winsorized_scale(g["return_on_equity_pct"])
        roce_s = _winsorized_scale(g["roce_pct"])
        npm_s = _winsorized_scale(g["net_profit_margin_pct"])

        fcf_cagr_s = _winsorized_scale(g["fcf_cagr_5yr"])
        cfo_pat_s = _winsorized_scale(g["cfo_quality_score"])
        fcf_pos_s = g["fcf_positive_flag"]

        rev_cagr_s = _winsorized_scale(g["revenue_cagr_5yr"])
        pat_cagr_s = _winsorized_scale(g["pat_cagr_5yr"])

        de_s = _de_score(g["debt_to_equity"])
        icr_s = _icr_score(g["interest_coverage"], g["icr_label"])

        for comp, w in [(roe_s, 0.15), (roce_s, 0.10), (npm_s, 0.10),
                        (fcf_cagr_s, 0.15), (cfo_pat_s, 0.10), (fcf_pos_s, 0.05),
                        (rev_cagr_s, 0.10), (pat_cagr_s, 0.10),
                        (de_s, 0.10), (icr_s, 0.05)]:
            valid = comp.notna()
            scores.loc[idx[valid]] += comp.loc[valid] * w
            weight_sum.loc[idx[valid]] += w

    final = (scores / weight_sum).round(2)
    final.index = df["company_id"]
    return final


def update_financial_ratios_composite_score():
    """Recompute and overwrite composite_quality_score in financial_ratios
    for the latest fiscal year of every company, using the v2 sector-
    relative winsorized formula. Earlier years keep the Sprint 2 v1 score
    (documented, not silently changed) since peer-relative percentiles
    only make sense for the current cross-section."""
    from screener.universe import build_universe  # local import: avoids circulars at module load

    conn = sqlite3.connect(DB_PATH)
    universe = build_universe(conn)
    v2_scores = compute_composite_scores(universe, conn)

    for company_id, score in v2_scores.items():
        latest_year = universe.loc[universe["company_id"] == company_id, "year"].iloc[0]
        conn.execute(
            "UPDATE financial_ratios SET composite_quality_score = ? WHERE company_id = ? AND year = ?",
            (float(score) if pd.notna(score) else None, company_id, latest_year),
        )
    conn.commit()
    conn.close()
    print(f"composite_quality_score (v2, sector-relative) updated for {len(v2_scores)} companies' latest fiscal year")


if __name__ == "__main__":
    update_financial_ratios_composite_score()
