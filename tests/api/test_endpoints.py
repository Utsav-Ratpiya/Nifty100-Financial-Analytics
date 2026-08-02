"""
tests/api/test_endpoints.py
Sprint 6 / Day 42 deliverable: HTTP-level tests via FastAPI's TestClient.

Requires fastapi + httpx to be installed (`pip install -r requirements.txt`).
Business logic is already covered independently of the HTTP layer in
tests/api/test_services.py, which runs without these dependencies.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def test_health_returns_200_and_status_ok():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert len(body["db_row_counts"]) == 10


def test_companies_returns_92_records():
    resp = client.get("/api/v1/companies")
    assert resp.status_code == 200
    assert len(resp.json()) == 92


def test_company_tcs_returns_correct_data():
    resp = client.get("/api/v1/companies/TCS")
    assert resp.status_code == 200
    assert resp.json()["company_id"] == "TCS"


def test_company_invalid_returns_404():
    resp = client.get("/api/v1/companies/INVALID")
    assert resp.status_code == 404


def test_screener_min_roe_filters_correctly():
    resp = client.get("/api/v1/screener", params={"min_roe": 15})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert all(r.get("return_on_equity_pct") is None or r["return_on_equity_pct"] >= 15
               or r.get("broad_sector") == "Financials" for r in body)


def test_screener_invalid_parameter_returns_400():
    resp = client.get("/api/v1/screener", params={"min_roe": "not-a-number"})
    assert resp.status_code in (400, 422)  # 422 if FastAPI's own type coercion rejects it first


def test_sectors_returns_ten_sectors():
    resp = client.get("/api/v1/sectors")
    assert resp.status_code == 200
    assert len(resp.json()) == 10


def test_sectors_it_returns_only_it_companies():
    resp = client.get("/api/v1/sectors/Information Technology/companies")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 5
    assert all(r["broad_sector"] == "Information Technology" for r in body)


def test_pl_endpoint_year_filter():
    resp = client.get("/api/v1/companies/TCS/pl", params={"from_year": "2022-04", "to_year": "2024-03"})
    assert resp.status_code == 200


def test_tearsheet_endpoint_returns_pdf():
    resp = client.get("/api/v1/companies/TCS/tearsheet")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_peer_group_unknown_returns_404():
    resp = client.get("/api/v1/peers/NotAGroup")
    assert resp.status_code == 404


def test_portfolio_stats_returns_ten_rows():
    resp = client.get("/api/v1/portfolio/stats")
    assert resp.status_code == 200
    assert len(resp.json()) == 10
