"""
src/analytics/cashflow_kpis.py — Nifty 100 Analytics
Sprint 2 / Day 11 deliverable.

Cash flow KPIs and the 8-pattern capital allocation classifier.
"""
from __future__ import annotations

import pandas as pd


def free_cash_flow(operating_activity, investing_activity):
    """FCF = CFO + CFI. Negative values are allowed (no clamping)."""
    if operating_activity is None or investing_activity is None:
        return None
    if pd.isna(operating_activity) or pd.isna(investing_activity):
        return None
    return operating_activity + investing_activity


def cfo_quality_score(cfo_series, pat_series):
    """CFO Quality Score = mean(CFO/PAT) over up to the last 5 years of
    data available for the company. Returns (score, label):
        >1.0        -> High Quality
        0.5 - 1.0   -> Moderate
        <0.5        -> Accrual Risk
    Returns (None, 'Insufficient Data') if PAT is 0/None throughout, or no
    overlapping data is available."""
    cfo_series = list(cfo_series)[-5:]
    pat_series = list(pat_series)[-5:]
    ratios = []
    for cfo, pat in zip(cfo_series, pat_series):
        if cfo is None or pat is None or pd.isna(cfo) or pd.isna(pat) or pat == 0:
            continue
        ratios.append(cfo / pat)
    if not ratios:
        return None, "Insufficient Data"
    score = sum(ratios) / len(ratios)
    if score > 1.0:
        label = "High Quality"
    elif score >= 0.5:
        label = "Moderate"
    else:
        label = "Accrual Risk"
    return round(score, 3), label


def capex_intensity(investing_activity, sales):
    """CapEx Intensity (%) = abs(investing_activity) / sales x 100.
    Labels: <3% Asset Light, 3-8% Moderate, >8% Capital Intensive.
    Returns (None, None) if sales is 0/None."""
    if sales is None or sales == 0 or pd.isna(sales) or investing_activity is None or pd.isna(investing_activity):
        return None, None
    pct = abs(investing_activity) / sales * 100
    if pct < 3:
        label = "Asset Light"
    elif pct <= 8:
        label = "Moderate"
    else:
        label = "Capital Intensive"
    return round(pct, 2), label


def fcf_conversion_rate(fcf, operating_profit):
    """FCF Conversion Rate (%) = FCF / operating_profit x 100.
    Returns None if operating_profit is 0/None."""
    if operating_profit is None or operating_profit == 0 or pd.isna(operating_profit):
        return None
    if fcf is None or pd.isna(fcf):
        return None
    return (fcf / operating_profit) * 100


# ---------------------------------------------------------------------------
# 8-pattern capital allocation classifier, based on sign of (CFO, CFI, CFF)
# ---------------------------------------------------------------------------

_HIGH_CFO_PAT_THRESHOLD = 1.0


def capital_allocation_pattern(cfo, cfi, cff, pat=None):
    """Classify a company-year into one of 8 capital allocation patterns
    based on the sign of (CFO, CFI, CFF):

        (+,-,-)                       -> Reinvestor
        (+,-,-) with high CFO/PAT     -> Shareholder Returns
        (+,+,-)                       -> Liquidating Assets
        (-,+,+)                       -> Distress Signal
        (-,-,+)                       -> Growth Funded by Debt
        (+,+,+)                       -> Cash Accumulator
        (-,-,-)                       -> Pre-Revenue
        (+,-,+)                       -> Mixed
    Any other sign combination not explicitly enumerated above also
    returns 'Mixed'.
    """
    if cfo is None or cfi is None or cff is None or pd.isna(cfo) or pd.isna(cfi) or pd.isna(cff):
        return None

    cfo_sign = cfo >= 0
    cfi_sign = cfi >= 0
    cff_sign = cff >= 0

    if cfo_sign and not cfi_sign and not cff_sign:
        if pat is not None and not pd.isna(pat) and pat != 0 and (cfo / pat) > _HIGH_CFO_PAT_THRESHOLD:
            return "Shareholder Returns"
        return "Reinvestor"
    if cfo_sign and cfi_sign and not cff_sign:
        return "Liquidating Assets"
    if not cfo_sign and cfi_sign and cff_sign:
        return "Distress Signal"
    if not cfo_sign and not cfi_sign and cff_sign:
        return "Growth Funded by Debt"
    if cfo_sign and cfi_sign and cff_sign:
        return "Cash Accumulator"
    if not cfo_sign and not cfi_sign and not cff_sign:
        return "Pre-Revenue"
    if cfo_sign and not cfi_sign and cff_sign:
        return "Mixed"
    return "Mixed"
