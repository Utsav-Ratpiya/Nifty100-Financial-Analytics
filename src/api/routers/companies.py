"""
src/api/routers/companies.py — Nifty 100 Analytics
Sprint 6 / Day 39 deliverable: company data endpoints.

    GET /api/v1/companies
    GET /api/v1/companies/{ticker}
    GET /api/v1/companies/{ticker}/pl
    GET /api/v1/companies/{ticker}/bs
    GET /api/v1/companies/{ticker}/cashflow
    GET /api/v1/companies/{ticker}/ratios
    GET /api/v1/companies/{ticker}/tearsheet
    GET /api/v1/companies/{ticker}/peers/compare   (also documented here since
                                                      it hangs off /companies/{ticker})
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # -> src/api/, so 'services' resolves

import services

router = APIRouter()


def _db():
    conn = services.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/companies")
def list_companies(sector: Optional[str] = None, market_cap_category: Optional[str] = None,
                    search: Optional[str] = None, conn=Depends(_db)):
    """All 92 companies with id, name, sector, and ROE/ROCE. Optional
    filters: sector (broad_sector, case-insensitive), market_cap_category
    ('Large Cap' / 'Mid Cap'), search (partial match on ticker or name)."""
    return services.list_companies(conn, sector=sector, market_cap_category=market_cap_category, search=search)


@router.get("/companies/{ticker}")
def get_company(ticker: str, conn=Depends(_db)):
    """Full company profile: companies fields + sector + latest-year KPIs.
    404 if the ticker doesn't exist."""
    result = services.get_company_profile(conn, ticker)
    if result is None:
        raise HTTPException(status_code=404, detail=f"company not found: {ticker}")
    return result


@router.get("/companies/{ticker}/pl")
def get_pl(ticker: str, from_year: Optional[str] = None, to_year: Optional[str] = None, conn=Depends(_db)):
    """P&L history. from_year/to_year are 'YYYY-MM' (e.g. '2020-04'),
    matched against the fiscal year's calendar-year component."""
    result = services.get_company_pl(conn, ticker, from_year, to_year)
    if result is None:
        raise HTTPException(status_code=404, detail=f"company not found: {ticker}")
    return result


@router.get("/companies/{ticker}/bs")
def get_bs(ticker: str, from_year: Optional[str] = None, to_year: Optional[str] = None, conn=Depends(_db)):
    """Balance sheet history. Same year-filter params as /pl."""
    result = services.get_company_bs(conn, ticker, from_year, to_year)
    if result is None:
        raise HTTPException(status_code=404, detail=f"company not found: {ticker}")
    return result


@router.get("/companies/{ticker}/cashflow")
def get_cashflow(ticker: str, from_year: Optional[str] = None, to_year: Optional[str] = None, conn=Depends(_db)):
    """Cash flow history. Same year-filter params as /pl."""
    result = services.get_company_cashflow(conn, ticker, from_year, to_year)
    if result is None:
        raise HTTPException(status_code=404, detail=f"company not found: {ticker}")
    return result


@router.get("/companies/{ticker}/ratios")
def get_ratios(ticker: str, year: Optional[str] = None, conn=Depends(_db)):
    """All computed KPIs per year. Pass `year` (e.g. 'Mar-2024' or 'TTM')
    to return a single year instead of the full history."""
    result = services.get_company_ratios(conn, ticker, year)
    if result is None:
        raise HTTPException(status_code=404, detail=f"company not found: {ticker}")
    return result


@router.get("/companies/{ticker}/tearsheet")
def get_tearsheet(ticker: str):
    """Returns the pre-generated 2-page tearsheet PDF (application/pdf).
    404 if the ticker has no tearsheet (unknown ticker, or it was skipped
    in batch generation for having < 3 years of data — see
    output/skipped_tearsheets.csv)."""
    path = services.get_tearsheet_path(ticker)
    if path is None:
        raise HTTPException(status_code=404,
                             detail=f"no tearsheet available for {ticker} (unknown ticker, or skipped "
                                    f"during batch generation — see output/skipped_tearsheets.csv)")
    return FileResponse(path, media_type="application/pdf", filename=f"{ticker}_tearsheet.pdf")


@router.get("/companies/{ticker}/peers/compare")
def get_peer_compare(ticker: str, conn=Depends(_db)):
    """Radar comparison data: the company's 8 axis metric values, the peer
    group average, and the peer group's benchmark (top composite-score)
    company. If the company has no peer group assignment, returns a
    'No peer group assigned' message rather than a 404 or error."""
    result = services.get_peer_compare(conn, ticker)
    if result is None:
        raise HTTPException(status_code=404, detail=f"company not found: {ticker}")
    return result
