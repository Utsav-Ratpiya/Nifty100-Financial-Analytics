"""
tests/api/test_services.py
Sprint 6 / Day 41-42 deliverable: unit tests for src/api/services.py.

These test the service layer directly (plain sqlite3 connection, no
FastAPI TestClient), so they run even in environments without fastapi/
uvicorn/pydantic installed. tests/api/test_endpoints.py covers the actual
HTTP layer via FastAPI's TestClient where those packages are available.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "api"))

import services  # noqa: E402


def _conn():
    return services.get_connection()


def test_health_returns_ok_and_all_ten_tables():
    conn = _conn()
    result = services.get_health(conn)
    conn.close()
    assert result["status"] == "ok"
    assert len(result["db_row_counts"]) == 10
    assert result["db_row_counts"]["companies"] == 92


def test_list_companies_returns_92():
    conn = _conn()
    result = services.list_companies(conn)
    conn.close()
    assert len(result) == 92


def test_list_companies_search_filter():
    conn = _conn()
    result = services.list_companies(conn, search="tcs")
    conn.close()
    assert any(r["company_id"] == "TCS" for r in result)


def test_get_company_profile_known_ticker():
    conn = _conn()
    result = services.get_company_profile(conn, "TCS")
    conn.close()
    assert result is not None
    assert result["company_id"] == "TCS"
    assert "latest_kpis" in result


def test_get_company_profile_unknown_ticker_returns_none():
    conn = _conn()
    result = services.get_company_profile(conn, "NOTATICKER")
    conn.close()
    assert result is None


def test_get_company_pl_returns_rows_for_known_ticker():
    conn = _conn()
    result = services.get_company_pl(conn, "TCS")
    conn.close()
    assert result is not None
    assert len(result) >= 10


def test_get_company_pl_unknown_ticker_returns_none():
    conn = _conn()
    result = services.get_company_pl(conn, "NOTATICKER")
    conn.close()
    assert result is None


def test_get_company_pl_year_range_filter():
    conn = _conn()
    result = services.get_company_pl(conn, "TCS", from_year="2020-04", to_year="2022-03")
    conn.close()
    years = [r["year"] for r in result]
    assert all(y == "TTM" or ("2020" <= y.split("-")[1] <= "2022") for y in years)


def test_get_company_ratios_single_year():
    conn = _conn()
    result = services.get_company_ratios(conn, "TCS", year="Mar-2024")
    conn.close()
    assert len(result) == 1
    assert result[0]["year"] == "Mar-2024"


def test_screener_min_roe_filters_correctly():
    conn = _conn()
    result = services.run_screener(conn, min_roe=15)
    conn.close()
    assert len(result) > 0
    assert all(r["return_on_equity_pct"] is None or r["return_on_equity_pct"] >= 15
               or r["broad_sector"] == "Financials" for r in result)


def test_screener_invalid_numeric_raises_valueerror():
    conn = _conn()
    try:
        services.run_screener(conn, min_roe="not-a-number")
        raised = False
    except ValueError:
        raised = True
    conn.close()
    assert raised


def test_list_sectors_returns_ten():
    conn = _conn()
    result = services.list_sectors(conn)
    conn.close()
    assert len(result) == 10  # see src/reports/sector_report.py docstring re: the "11" figure


def test_get_sector_companies_known_sector():
    conn = _conn()
    result = services.get_sector_companies(conn, "Information Technology")
    conn.close()
    assert result is not None
    assert len(result) == 5


def test_get_sector_companies_unknown_sector_returns_none():
    conn = _conn()
    result = services.get_sector_companies(conn, "NotASector")
    conn.close()
    assert result is None


def test_get_peer_group_known_group():
    conn = _conn()
    result = services.get_peer_group(conn, "IT Services")
    conn.close()
    assert result is not None
    assert len(result) > 0


def test_get_peer_group_unknown_group_returns_none():
    conn = _conn()
    result = services.get_peer_group(conn, "NotAGroup")
    conn.close()
    assert result is None


def test_get_peer_compare_no_peer_group_message():
    conn = _conn()
    # find a company without a peer group assignment
    import pandas as pd
    all_ids = pd.read_sql("SELECT company_id FROM companies", conn)["company_id"].tolist()
    grouped_ids = pd.read_sql("SELECT DISTINCT company_id FROM peer_groups", conn)["company_id"].tolist()
    ungrouped = [c for c in all_ids if c not in grouped_ids]
    assert ungrouped, "expected at least one company without a peer group for this test"
    result = services.get_peer_compare(conn, ungrouped[0])
    conn.close()
    assert result["message"] == "No peer group assigned"


def test_get_market_cap_history_known_ticker():
    conn = _conn()
    result = services.get_market_cap_history(conn, "TCS")
    conn.close()
    assert result is not None and len(result) > 0


def test_get_portfolio_stats_returns_ten_kpis():
    conn = _conn()
    result = services.get_portfolio_stats(conn)
    conn.close()
    assert len(result) == 10


def test_get_company_documents_known_ticker():
    conn = _conn()
    result = services.get_company_documents(conn, "TCS")
    conn.close()
    assert result is not None
    assert "is_url_valid" in result[0]


def test_get_company_documents_unknown_ticker_returns_none():
    conn = _conn()
    result = services.get_company_documents(conn, "NOTATICKER")
    conn.close()
    assert result is None


def test_get_tearsheet_path_known_ticker_exists():
    path = services.get_tearsheet_path("TCS")
    assert path is not None and os.path.exists(path)


def test_get_tearsheet_path_unknown_ticker_returns_none():
    path = services.get_tearsheet_path("NOTATICKER")
    assert path is None


def test_list_companies_contains_no_raw_nan():
    """Regression test: services responses must never contain a raw float
    NaN, since Starlette's JSONResponse uses allow_nan=False and would
    raise ValueError on serialization. list_companies is a good target for
    this because roce_percentage/roe_percentage are frequently missing in
    the source data. See the @_sanitized decorator in services.py."""
    import math
    conn = _conn()
    result = services.list_companies(conn)
    conn.close()

    def _contains_nan(obj):
        if isinstance(obj, dict):
            return any(_contains_nan(v) for v in obj.values())
        if isinstance(obj, list):
            return any(_contains_nan(v) for v in obj)
        if isinstance(obj, float):
            return math.isnan(obj)
        return False

    assert not _contains_nan(result)
