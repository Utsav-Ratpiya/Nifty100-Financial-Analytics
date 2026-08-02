"""
src/analytics/cagr.py — Nifty 100 Analytics
Sprint 2 / Day 10 deliverable.

CAGR engine for Revenue, PAT (net profit), and EPS across 3-year, 5-year,
and 10-year trailing windows, with all 6 edge cases handled and flagged.

Edge cases (see cagr_with_flag()):
    Positive -> Positive : compute normally                      flag=None
    Positive -> Negative : None                                  flag=DECLINE_TO_LOSS
    Negative -> Positive : None                                  flag=TURNAROUND
    Negative -> Negative : None                                  flag=BOTH_NEGATIVE
    Zero base            : None                                  flag=ZERO_BASE
    < n years of data     : None                                  flag=INSUFFICIENT
"""
from __future__ import annotations

import pandas as pd


def cagr(start: float, end: float, n: int):
    """Raw CAGR formula: ((end/start)^(1/n) - 1) x 100. Caller is
    responsible for handling edge cases before calling this (see
    cagr_with_flag) — this function assumes start > 0."""
    return ((end / start) ** (1 / n) - 1) * 100


def cagr_with_flag(start, end, n):
    """Compute CAGR with all 6 edge cases handled.

    Returns (value, flag):
        value is None whenever flag is not None.
    """
    if start is None or end is None or n is None or pd.isna(start) or pd.isna(end):
        return None, "INSUFFICIENT"
    if n <= 0:
        return None, "INSUFFICIENT"
    if start == 0:
        return None, "ZERO_BASE"
    if start > 0 and end > 0:
        return cagr(start, end, n), None
    if start > 0 and end < 0:
        return None, "DECLINE_TO_LOSS"
    if start < 0 and end > 0:
        return None, "TURNAROUND"
    if start < 0 and end < 0:
        return None, "BOTH_NEGATIVE"
    # end == 0 with start != 0 falls through here; treat as decline/turnaround
    # boundary case using the same zero-base logic as a zero end value.
    return None, "ZERO_BASE"


# ---------------------------------------------------------------------------
# Series-level helper: trailing CAGR ending at every index of a
# chronologically-sorted per-company series, for windows of n years.
# ---------------------------------------------------------------------------

def trailing_cagr_series(values: list, window: int):
    """Given a chronologically sorted list of values for ONE company,
    return a list the same length where entry i is (value, flag) for the
    CAGR ending at position i using `window` years of history (i.e. start
    = values[i - window], end = values[i]). Positions with fewer than
    `window` prior data points return (None, 'INSUFFICIENT')."""
    n = len(values)
    out = []
    for i in range(n):
        if i - window < 0:
            out.append((None, "INSUFFICIENT"))
            continue
        start = values[i - window]
        end = values[i]
        out.append(cagr_with_flag(start, end, window))
    return out


def compute_cagr_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Adds revenue/pat/eps CAGR (+flag) columns for 3/5/10yr windows to
    `df`. Expects df to already be sorted by ['company_id', '_year_sort']
    and to contain a 'sales', 'net_profit', 'eps' column, plus a 'year'
    column. TTM rows are excluded from the trailing series (they are not
    fiscal-year-ends) and always get CAGR=None / flag='INSUFFICIENT' —
    the label reflects that TTM has no defined n-year lookback in this
    engine, consistent with the 'insufficient data' edge case."""
    metric_cols = {"sales": "revenue", "net_profit": "pat", "eps": "eps"}
    windows = [3, 5, 10]

    for source_col, prefix in metric_cols.items():
        for w in windows:
            df[f"{prefix}_cagr_{w}yr"] = None
            df[f"{prefix}_cagr_{w}yr_flag"] = "INSUFFICIENT"

    for company_id, group in df.groupby("company_id"):
        fy_mask = group["year"] != "TTM"
        fy_idx = group.index[fy_mask]
        for source_col, prefix in metric_cols.items():
            values = group.loc[fy_idx, source_col].tolist()
            for w in windows:
                results = trailing_cagr_series(values, w)
                for idx, (val, flag) in zip(fy_idx, results):
                    df.at[idx, f"{prefix}_cagr_{w}yr"] = val
                    df.at[idx, f"{prefix}_cagr_{w}yr_flag"] = flag

    return df
