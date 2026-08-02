"""
tests/kpi/test_cagr.py
Sprint 2 / Day 10, 14 deliverable: 10 unit tests for the CAGR engine,
covering all 6 edge cases plus the trailing-series helper.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from cagr import cagr, cagr_with_flag, trailing_cagr_series


def test_cagr_raw_formula():
    # 100 -> 200 over 3 years
    assert round(cagr(100, 200, 3), 2) == round(((200 / 100) ** (1 / 3) - 1) * 100, 2)


def test_cagr_normal_positive_to_positive():
    value, flag = cagr_with_flag(100, 200, 5)
    assert flag is None
    assert value is not None and value > 0


def test_cagr_turnaround_negative_to_positive():
    value, flag = cagr_with_flag(-50, 100, 5)
    assert value is None
    assert flag == "TURNAROUND"


def test_cagr_decline_to_loss_positive_to_negative():
    value, flag = cagr_with_flag(100, -50, 5)
    assert value is None
    assert flag == "DECLINE_TO_LOSS"


def test_cagr_both_negative():
    value, flag = cagr_with_flag(-100, -50, 5)
    assert value is None
    assert flag == "BOTH_NEGATIVE"


def test_cagr_zero_base():
    value, flag = cagr_with_flag(0, 100, 5)
    assert value is None
    assert flag == "ZERO_BASE"


def test_cagr_insufficient_data_none_start():
    value, flag = cagr_with_flag(None, 100, 5)
    assert value is None
    assert flag == "INSUFFICIENT"


def test_cagr_insufficient_data_zero_window():
    value, flag = cagr_with_flag(100, 200, 0)
    assert value is None
    assert flag == "INSUFFICIENT"


def test_trailing_cagr_series_insufficient_for_early_positions():
    values = [100, 110, 120, 130, 140]
    results = trailing_cagr_series(values, window=3)
    # first 3 positions have < 3 years of prior history
    for val, flag in results[:3]:
        assert val is None and flag == "INSUFFICIENT"
    # position index 3 (4th year) has exactly 3 years of history: 100 -> 130
    val, flag = results[3]
    assert flag is None
    assert val is not None


def test_trailing_cagr_series_turnaround_flag_propagates():
    values = [-50, 10, 20, 100]
    results = trailing_cagr_series(values, window=3)
    val, flag = results[3]
    assert val is None
    assert flag == "TURNAROUND"
