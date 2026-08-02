"""
tests/etl/test_normalise.py
Sprint 1 / Day 02 deliverable: 20 unit tests for normalize_year(),
15 unit tests for normalize_ticker().
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from etl.normaliser import normalize_year, normalize_ticker, normalize_year_simple


# ---------------------------------------------------------------------------
# normalize_year — 20 tests
# ---------------------------------------------------------------------------

def test_year_mon_yyyy_basic():
    assert normalize_year("Dec 2012") == ("Dec-2012", None)

def test_year_mon_yyyy_mar():
    assert normalize_year("Mar 2014") == ("Mar-2014", None)

def test_year_mon_dash_2digit():
    assert normalize_year("Mar-13") == ("Mar-2013", None)

def test_year_mon_dash_2digit_dec():
    assert normalize_year("Dec-24") == ("Dec-2024", None)

def test_year_bare_4digit():
    assert normalize_year("2013") == ("2013-00", None)

def test_year_bare_4digit_int_input():
    assert normalize_year(2020) == ("2020-00", None)

def test_year_ttm():
    assert normalize_year("TTM") == ("TTM", None)

def test_year_ttm_lowercase():
    assert normalize_year("ttm") == ("TTM", None)

def test_year_trailing_junk_digits():
    label, reason = normalize_year("Mar 2023 15")
    assert label == "Mar-2023"
    assert reason is not None and "trailing_junk_stripped" in reason

def test_year_trailing_junk_months_tag():
    label, reason = normalize_year("Mar 2016 9m")
    assert label == "Mar-2016"
    assert reason is not None and "trailing_junk_stripped" in reason

def test_year_case_insensitive_month():
    assert normalize_year("dec 2012") == ("Dec-2012", None)
    assert normalize_year("DEC 2012") == ("Dec-2012", None)

def test_year_month_no_space():
    assert normalize_year("Mar2014") == ("Mar-2014", None)

def test_year_none_input():
    label, reason = normalize_year(None)
    assert label is None and reason == "null_value"

def test_year_empty_string():
    label, reason = normalize_year("")
    assert label is None and reason == "empty_value"

def test_year_whitespace_only():
    label, reason = normalize_year("   ")
    assert label is None and reason == "empty_value"

def test_year_nan_string():
    label, reason = normalize_year("nan")
    assert label is None and reason == "empty_value"

def test_year_unparseable_garbage():
    label, reason = normalize_year("Q1 something")
    assert label is None and reason.startswith("unparseable")

def test_year_out_of_range():
    label, reason = normalize_year("Mar 1899")
    assert label is None and "year_out_of_range" in reason

def test_year_all_months_mapped():
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for mon in months:
        label, reason = normalize_year(f"{mon} 2020")
        assert label == f"{mon}-2020", f"failed for {mon}"
        assert reason is None

def test_year_simple_wrapper_success():
    assert normalize_year_simple("Dec 2012") == "Dec-2012"

def test_year_simple_wrapper_failure():
    assert normalize_year_simple("garbage") is None


# ---------------------------------------------------------------------------
# normalize_ticker — 15 tests
# ---------------------------------------------------------------------------

def test_ticker_already_clean():
    assert normalize_ticker("RELIANCE") == "RELIANCE"

def test_ticker_lowercase():
    assert normalize_ticker("reliance") == "RELIANCE"

def test_ticker_mixed_case():
    assert normalize_ticker("Reliance") == "RELIANCE"

def test_ticker_leading_space():
    assert normalize_ticker(" RELIANCE") == "RELIANCE"

def test_ticker_trailing_space():
    assert normalize_ticker("RELIANCE ") == "RELIANCE"

def test_ticker_both_side_space():
    assert normalize_ticker("  reliance  ") == "RELIANCE"

def test_ticker_internal_double_space():
    assert normalize_ticker("BAJAJ  AUTO") == "BAJAJ AUTO"

def test_ticker_with_hyphen():
    assert normalize_ticker("bajaj-auto") == "BAJAJ-AUTO"

def test_ticker_with_ampersand():
    assert normalize_ticker("m&m") == "M&M"

def test_ticker_none_input():
    assert normalize_ticker(None) is None

def test_ticker_empty_string():
    assert normalize_ticker("") is None

def test_ticker_whitespace_only():
    assert normalize_ticker("   ") is None

def test_ticker_nan_string():
    assert normalize_ticker("NaN") is None

def test_ticker_numeric_like():
    assert normalize_ticker("360one") == "360ONE"

def test_ticker_idempotent():
    once = normalize_ticker(" reliance ")
    twice = normalize_ticker(once)
    assert once == twice == "RELIANCE"
