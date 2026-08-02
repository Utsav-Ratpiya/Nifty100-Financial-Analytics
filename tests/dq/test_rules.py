"""
tests/dq/test_rules.py — Sprint 3 / Day 21 deliverable.

One test per DQ rule (DQ-01 .. DQ-16, from src/etl/validator.py, built in
Sprint 1). Each test crafts a small DataFrame that violates exactly that
rule and verifies the correct rule_id and severity come back.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from etl import validator as V


def test_dq01_pk_uniqueness():
    df = pd.DataFrame({
        "source_id": [1, 1, 2],
        "company_id": ["A", "A", "B"],
    })
    failures = V.dq01_pk_uniqueness(df, "profitandloss")
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-01"
    assert failures[0]["severity"] == "CRITICAL"


def test_dq02_composite_key_uniqueness():
    df = pd.DataFrame({
        "company_id": ["A", "A", "B"],
        "year": ["Mar-2020", "Mar-2020", "Mar-2020"],
    })
    failures = V.dq02_composite_key_uniqueness(df, "profitandloss")
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-02"
    assert failures[0]["severity"] == "CRITICAL"


def test_dq03_fk_integrity():
    df = pd.DataFrame({"company_id": ["A", "ZZZ_ORPHAN"]})
    failures = V.dq03_fk_integrity(df, "profitandloss", valid_company_ids={"A"})
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-03"
    assert failures[0]["severity"] == "CRITICAL"


def test_dq04_bs_balance():
    df = pd.DataFrame({
        "company_id": ["A"], "year": ["Mar-2020"],
        "total_assets": [150.0], "total_liabilities": [100.0],  # 50% off
    })
    failures = V.dq04_bs_balance(df)
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-04"
    assert failures[0]["severity"] == "WARNING"


def test_dq05_opm_crosscheck():
    df = pd.DataFrame({
        "company_id": ["A"], "year": ["Mar-2020"],
        "sales": [1000.0], "operating_profit": [150.0], "opm_percentage": [10.0],  # computed=15%, stored=10%
    })
    failures = V.dq05_opm_crosscheck(df)
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-05"


def test_dq06_positive_sales():
    df = pd.DataFrame({"company_id": ["A"], "year": ["Mar-2020"], "sales": [-50.0]})
    failures = V.dq06_positive_sales(df)
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-06"


def test_dq07_net_cash_consistency():
    df = pd.DataFrame({
        "company_id": ["A"], "year": ["Mar-2020"],
        "operating_activity": [100.0], "investing_activity": [-50.0],
        "financing_activity": [-20.0], "net_cash_flow": [100.0],  # should be 30
    })
    failures = V.dq07_net_cash_consistency(df)
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-07"


def test_dq08_tax_rate_sanity():
    df = pd.DataFrame({"company_id": ["A"], "year": ["Mar-2020"], "tax_percentage": [95.0]})
    failures = V.dq08_tax_rate_sanity(df)
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-08"


def test_dq09_dividend_payout_cap():
    df = pd.DataFrame({"company_id": ["A"], "year": ["Mar-2020"], "dividend_payout": [300.0]})
    failures = V.dq09_dividend_payout_cap(df)
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-09"


def test_dq10_url_validity():
    df = pd.DataFrame({
        "company_id": ["A"], "year": [2020],
        "annual_report_url": ["not_a_valid_url"],
    })
    failures = V.dq10_url_validity(df)
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-10"


def test_dq11_eps_sign_consistency():
    df = pd.DataFrame({
        "company_id": ["A"], "year": ["Mar-2020"],
        "net_profit": [100.0], "eps": [-5.0],  # sign mismatch
    })
    failures = V.dq11_eps_sign_consistency(df)
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-11"


def test_dq12_bs_components():
    df = pd.DataFrame({
        "company_id": ["A"], "year": ["Mar-2020"],
        "equity_capital": [10.0], "reserves": [40.0], "borrowings": [20.0],
        "other_liabilities": [5.0], "total_liabilities": [1000.0],  # way off from 75
    })
    failures = V.dq12_bs_components(df)
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-12"


def test_dq13_year_coverage():
    pl = pd.DataFrame({"company_id": ["A"]})
    bs = pd.DataFrame({"company_id": ["A"]})
    cf = pd.DataFrame({"company_id": ["A"]})
    failures = V.dq13_year_coverage(pl, bs, cf, all_company_ids={"A", "NOCOVERAGE"})
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-13"
    assert failures[0]["company_id"] == "NOCOVERAGE"


def test_dq14_stock_price_positivity():
    df = pd.DataFrame({
        "company_id": ["A"], "price_date": ["2020-01-01"],
        "open_price": [-5.0], "high_price": [10.0], "low_price": [9.0],
        "close_price": [9.5], "adjusted_close": [9.5],
    })
    failures = V.dq14_stock_price_positivity(df)
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-14"


def test_dq15_sector_completeness():
    sectors_df = pd.DataFrame({"company_id": ["A"]})
    failures = V.dq15_sector_completeness(sectors_df, all_company_ids={"A", "NOSECTOR"})
    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-15"
    assert failures[0]["company_id"] == "NOSECTOR"


def test_dq16_peer_benchmark_uniqueness():
    peer_df = pd.DataFrame({
        "peer_group_name": ["Group A", "Group A", "Group B"],
        "company_id": ["X", "Y", "Z"],
        "is_benchmark": [1, 1, 0],  # Group A has 2 benchmarks, Group B has 0
    })
    failures = V.dq16_peer_benchmark_uniqueness(peer_df)
    assert len(failures) == 2  # one for Group A (2 benchmarks), one for Group B (0 benchmarks)
    assert all(f["rule_id"] == "DQ-16" for f in failures)
