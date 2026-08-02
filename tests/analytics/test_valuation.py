"""
tests/analytics/test_valuation.py — Nifty 100 Analytics
Sprint 4 deliverable: unit tests for src/analytics/valuation.py's pure
formula functions (classify_valuation, fcf_yield_pct).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from valuation import classify_valuation, fcf_yield_pct  # noqa: E402


def test_classify_caution_when_pe_high_vs_sector():
    assert classify_valuation(pe=40, sector_median=20) == "Caution"


def test_classify_discount_when_pe_low_vs_sector():
    assert classify_valuation(pe=10, sector_median=20) == "Discount"


def test_classify_fair_within_band():
    assert classify_valuation(pe=22, sector_median=20) == "Fair"


def test_classify_boundary_at_1_5x_is_fair_not_caution():
    # exactly at the multiple should NOT trip "Caution" (strictly greater-than)
    assert classify_valuation(pe=30, sector_median=20) == "Fair"


def test_classify_boundary_at_0_7x_is_fair_not_discount():
    # exactly at the multiple should NOT trip "Discount" (strictly less-than)
    assert classify_valuation(pe=14, sector_median=20) == "Fair"


def test_classify_not_rated_when_pe_missing():
    assert classify_valuation(pe=None, sector_median=20) == "Not Rated"


def test_classify_not_rated_when_sector_median_missing():
    assert classify_valuation(pe=25, sector_median=None) == "Not Rated"


def test_classify_not_rated_when_sector_median_zero():
    assert classify_valuation(pe=25, sector_median=0) == "Not Rated"


def test_fcf_yield_normal_case():
    assert round(fcf_yield_pct(500, 10000), 2) == 5.0


def test_fcf_yield_negative_fcf_allowed():
    assert round(fcf_yield_pct(-200, 10000), 2) == -2.0


def test_fcf_yield_none_when_market_cap_zero():
    assert fcf_yield_pct(500, 0) is None


def test_fcf_yield_none_when_inputs_missing():
    assert fcf_yield_pct(None, 10000) is None
    assert fcf_yield_pct(500, None) is None
