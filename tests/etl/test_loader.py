"""
tests/etl/test_loader.py
Sprint 1 / Day 02 deliverable: 10 unit tests verifying the loader reads
correct row counts and column names for each source file.

These tests read directly from data/*.xlsx (not the DB) so they catch
schema drift in the source files early, independent of DB state.
"""
import os
import sys
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def _load(fname, header):
    return pd.read_excel(os.path.join(DATA_DIR, fname), header=header)


def test_companies_row_count_and_columns():
    df = _load("companies.xlsx", header=1)
    assert len(df) == 92
    assert {"id", "company_name", "roce_percentage", "roe_percentage"}.issubset(df.columns)


def test_companies_ids_unique():
    df = _load("companies.xlsx", header=1)
    assert df["id"].nunique() == len(df)


def test_profitandloss_columns():
    df = _load("profitandloss.xlsx", header=1)
    expected = {"id", "company_id", "year", "sales", "expenses", "operating_profit",
                "opm_percentage", "other_income", "interest", "depreciation",
                "profit_before_tax", "tax_percentage", "net_profit", "eps", "dividend_payout"}
    assert expected.issubset(df.columns)
    assert len(df) > 1000  # sanity: dataset should be sizeable


def test_balancesheet_columns():
    df = _load("balancesheet.xlsx", header=1)
    expected = {"id", "company_id", "year", "equity_capital", "reserves", "borrowings",
                "other_liabilities", "total_liabilities", "fixed_assets", "cwip",
                "investments", "other_asset", "total_assets"}
    assert expected.issubset(df.columns)


def test_cashflow_columns():
    df = _load("cashflow.xlsx", header=1)
    expected = {"id", "company_id", "year", "operating_activity", "investing_activity",
                "financing_activity", "net_cash_flow"}
    assert expected.issubset(df.columns)


def test_analysis_row_count_and_columns():
    df = _load("analysis.xlsx", header=1)
    assert len(df) == 20
    expected = {"id", "company_id", "compounded_sales_growth", "compounded_profit_growth",
                "stock_price_cagr", "roe"}
    assert expected.issubset(df.columns)


def test_documents_columns():
    df = _load("documents.xlsx", header=1)
    expected = {"id", "company_id", "Year", "Annual_Report"}
    assert expected.issubset(df.columns)


def test_prosandcons_row_count():
    df = _load("prosandcons.xlsx", header=1)
    assert len(df) == 16
    assert {"id", "company_id", "pros", "cons"}.issubset(df.columns)


def test_sectors_row_count_and_columns():
    df = _load("sectors.xlsx", header=0)
    assert len(df) == 92
    expected = {"id", "company_id", "broad_sector", "sub_sector", "index_weight_pct", "market_cap_category"}
    assert expected.issubset(df.columns)


def test_stock_prices_row_count():
    df = _load("stock_prices.xlsx", header=0)
    assert len(df) == 5520
    expected = {"id", "company_id", "date", "open_price", "high_price", "low_price",
                "close_price", "volume", "adjusted_close"}
    assert expected.issubset(df.columns)
