"""
tests/kpi/test_ratios.py
Sprint 2 / Day 08, 09, 14 deliverable: unit tests for the profitability,
leverage, and efficiency ratio formulas in src/analytics/ratios.py.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from ratios import (
    net_profit_margin,
    operating_profit_margin_check,
    return_on_equity,
    return_on_capital_employed,
    return_on_assets,
    debt_to_equity,
    high_leverage_flag,
    interest_coverage_ratio,
    icr_label,
    icr_warning_flag,
    net_debt,
    asset_turnover,
)


# ---------------------------------------------------------------------------
# Day 08 — Profitability ratios (8 tests)
# ---------------------------------------------------------------------------

def test_npm_normal_case():
    assert net_profit_margin(200, 1000) == 20.0


def test_npm_zero_sales_returns_none():
    assert net_profit_margin(200, 0) is None


def test_roe_normal_case():
    assert return_on_equity(150, 100, 400) == 30.0


def test_roe_negative_equity_returns_none():
    assert return_on_equity(150, 100, -600) is None


def test_roce_normal_case():
    roce = return_on_capital_employed(operating_profit=300, other_income=20, equity_capital=100,
                                       reserves=900, borrowings=500)
    assert round(roce, 2) == round((320 / 1500) * 100, 2)


def test_roa_zero_assets_returns_none():
    assert return_on_assets(100, 0) is None


def test_roa_normal_case():
    assert return_on_assets(100, 1000) == 10.0


def test_opm_crosscheck_mismatch_flagged():
    computed, mismatch = operating_profit_margin_check(operating_profit=150, sales=1000, opm_percentage=10.0)
    # computed = 15.0%, source says 10.0% -> 5pp diff > 1pp tolerance
    assert computed == 15.0
    assert mismatch is True


def test_opm_crosscheck_within_tolerance_not_flagged():
    computed, mismatch = operating_profit_margin_check(operating_profit=150, sales=1000, opm_percentage=14.5)
    assert mismatch is False


# ---------------------------------------------------------------------------
# Day 09 — Leverage & efficiency ratios (8 tests)
# ---------------------------------------------------------------------------

def test_de_debt_free_returns_zero_not_none():
    assert debt_to_equity(borrowings=0, equity_capital=100, reserves=400) == 0.0


def test_de_normal_case():
    assert debt_to_equity(borrowings=250, equity_capital=100, reserves=400) == 0.5


def test_de_negative_net_worth_returns_none():
    assert debt_to_equity(borrowings=250, equity_capital=100, reserves=-600) is None


def test_high_leverage_flag_triggers_for_non_financials():
    assert high_leverage_flag(de_ratio=6.0, broad_sector="Industrials") is True


def test_high_leverage_flag_suppressed_for_financials_sector():
    assert high_leverage_flag(de_ratio=8.0, broad_sector="Financials") is False


def test_icr_interest_zero_returns_none():
    assert interest_coverage_ratio(operating_profit=300, other_income=10, interest=0) is None


def test_icr_label_debt_free():
    assert icr_label(None) == "Debt Free"


def test_icr_warning_flag_below_threshold():
    assert icr_warning_flag(1.2) is True
    assert icr_warning_flag(1.5) is False
    assert icr_warning_flag(None) is False


# ---------------------------------------------------------------------------
# Additional coverage (net debt, asset turnover) to round out the suite
# ---------------------------------------------------------------------------

def test_net_debt_normal_case():
    assert net_debt(borrowings=500, investments=200) == 300


def test_net_debt_handles_none_investments():
    assert net_debt(borrowings=500, investments=None) == 500


def test_asset_turnover_zero_assets_returns_none():
    assert asset_turnover(sales=1000, total_assets=0) is None


def test_asset_turnover_normal_case():
    assert asset_turnover(sales=1000, total_assets=500) == 2.0
