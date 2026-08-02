"""
tests/kpi/test_cashflow_kpis.py
Sprint 2 / Day 11, 14 deliverable: unit tests for FCF, CFO quality score,
CapEx intensity, FCF conversion, and the 8-pattern capital allocation
classifier in src/analytics/cashflow_kpis.py.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from cashflow_kpis import (
    free_cash_flow,
    cfo_quality_score,
    capex_intensity,
    fcf_conversion_rate,
    capital_allocation_pattern,
)


def test_fcf_allows_negative_value():
    assert free_cash_flow(operating_activity=100, investing_activity=-250) == -150


def test_fcf_normal_case():
    assert free_cash_flow(operating_activity=300, investing_activity=-100) == 200


def test_cfo_quality_high_quality_label():
    score, label = cfo_quality_score([120, 130, 140], [100, 100, 100])
    assert label == "High Quality"


def test_cfo_quality_accrual_risk_label():
    score, label = cfo_quality_score([20, 30, 40], [100, 100, 100])
    assert label == "Accrual Risk"


def test_cfo_quality_handles_zero_pat():
    score, label = cfo_quality_score([100], [0])
    assert score is None
    assert label == "Insufficient Data"


def test_capex_intensity_asset_light_label():
    pct, label = capex_intensity(investing_activity=-20, sales=1000)
    assert pct == 2.0
    assert label == "Asset Light"


def test_capex_intensity_capital_intensive_label():
    pct, label = capex_intensity(investing_activity=-150, sales=1000)
    assert pct == 15.0
    assert label == "Capital Intensive"


def test_fcf_conversion_zero_operating_profit_returns_none():
    assert fcf_conversion_rate(fcf=100, operating_profit=0) is None


def test_capital_allocation_reinvestor_pattern():
    # cfo/pat = 100/200 = 0.5, below the high-quality threshold -> Reinvestor
    label = capital_allocation_pattern(cfo=100, cfi=-50, cff=-30, pat=200)
    assert label == "Reinvestor"


def test_capital_allocation_shareholder_returns_pattern():
    # cfo/pat = 100/50 = 2.0, above the high-quality threshold -> Shareholder Returns
    label = capital_allocation_pattern(cfo=100, cfi=-50, cff=-30, pat=50)
    assert label == "Shareholder Returns"


def test_capital_allocation_distress_signal_pattern():
    label = capital_allocation_pattern(cfo=-40, cfi=20, cff=30, pat=-10)
    assert label == "Distress Signal"
