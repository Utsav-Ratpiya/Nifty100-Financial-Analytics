"""
tests/analytics/test_cluster_profiling.py
Sprint 6 / Day 37 deliverable: unit tests for src/analytics/cluster_profiling.py.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from cluster_profiling import detect_outliers, build_portfolio_stats, KPI_10


def _make_latest():
    n = 12
    data = {"company_id": [f"C{i}" for i in range(n)], "broad_sector": ["Sector1"] * n}
    base = [10, 11, 9, 10.5, 9.5, 10, 10.2, 9.8, 10, 10.1, 9.9, 10]
    for col in KPI_10:
        data[col] = list(base)
    # inject one clearly extreme outlier on the first KPI. With n-1 near-
    # identical values, the outlier's z-score asymptotically approaches
    # sqrt(n-1) as its magnitude grows (n=12 -> sqrt(11) ~= 3.317, safely
    # clearing the strict z>3 threshold; n=10 would cap out at exactly
    # z=3.0 and never clear it, which is what broke this test originally).
    data[KPI_10[0]] = base[:-1] + [50000]
    return pd.DataFrame(data)


def test_detect_outliers_flags_extreme_value():
    latest = _make_latest()
    out = detect_outliers(latest)
    assert len(out) >= 1
    assert "C11" in out["company_id"].values


def test_detect_outliers_skips_small_sectors():
    latest = _make_latest().iloc[:2]  # only 2 companies in the sector
    out = detect_outliers(latest)
    assert out.empty


def test_build_portfolio_stats_has_all_percentiles():
    latest = _make_latest()
    stats = build_portfolio_stats(latest)
    assert len(stats) == len(KPI_10)
    for col in ["p10", "p25", "p50", "p75", "p90", "mean", "std"]:
        assert col in stats.columns
