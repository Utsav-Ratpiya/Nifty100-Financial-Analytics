import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from nlp.parser import parse_period_text


def test_parse_basic_years():
    assert parse_period_text("10 Years: 21%") == (10, 21.0)


def test_parse_extra_whitespace():
    assert parse_period_text("5 Years:       24%") == (5, 24.0)


def test_parse_decimal_value():
    assert parse_period_text("3 Years: 9.5%") == (3, 9.5)


def test_parse_one_year_singular_negative_value_does_not_match():
    # The spec's exact regex ([\d.]+ for the value group) has no minus-sign
    # handling, so a negative percentage like '-2%' does not match at all --
    # this is a faithful implementation of the given regex, not a bug.
    # It's correctly logged as a parse failure (see parser.py docstring).
    period, value = parse_period_text("1 Year: -2%")
    assert period is None and value is None


def test_parse_ttm_does_not_match():
    period, value = parse_period_text("TTM:            43%")
    assert period is None and value is None


def test_parse_last_year_does_not_match():
    period, value = parse_period_text("Last Year:      12%")
    assert period is None and value is None


def test_parse_none_input():
    assert parse_period_text(None) == (None, None)


def test_parse_positive_one_year():
    assert parse_period_text("1 Year: 16%") == (1, 16.0)
