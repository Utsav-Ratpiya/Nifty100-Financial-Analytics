"""
tests/analytics/test_clustering.py
Sprint 6 / Day 36-37 deliverable: unit tests for src/analytics/clustering.py.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from clustering import _winsorize, _impute_by_sector_median, _name_clusters


def test_winsorize_clips_extreme_values():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5, 1000]})
    out = _winsorize(df, ["x"], lower_pct=5, upper_pct=95)
    assert out["x"].max() < 1000


def test_impute_by_sector_median_fills_missing():
    df = pd.DataFrame({
        "broad_sector": ["A", "A", "A", "B", "B"],
        "x": [10, None, 30, None, 50],
    })
    out = _impute_by_sector_median(df, ["x"])
    assert out["x"].isna().sum() == 0
    assert out.loc[1, "x"] == 20  # median of [10, 30]


def test_name_clusters_assigns_five_distinct_names():
    profile = pd.DataFrame({
        "return_on_equity_pct": [30, 15, 10, 5, 20],
        "debt_to_equity": [0.2, 0.5, 1.0, 8.0, 0.3],
        "revenue_cagr_5yr": [10, 25, 5, 15, 8],
        "fcf_cagr_5yr": [10, 20, 0, -5, 5],
        "operating_profit_margin_pct": [30, 20, 15, 25, 18],
    }, index=[0, 1, 2, 3, 4])
    names = _name_clusters(profile)
    assert len(names) == 5
    assert len(set(names.values())) == 5
