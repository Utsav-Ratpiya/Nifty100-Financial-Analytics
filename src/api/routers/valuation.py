"""src/api/routers/valuation.py — GET /api/v1/market-cap/{ticker} (Day 40)."""
from fastapi import APIRouter, Depends, HTTPException

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


@router.get("/market-cap/{ticker}")
def get_market_cap_history(ticker: str, conn=Depends(_db)):
    """Historical valuation multiples (P/E, P/B, EV/EBITDA, dividend
    yield) from market_cap.xlsx, 2019-2024. 404 for an unknown ticker.
    Note: market_cap.xlsx is a SIMULATED dataset (see README) — displayed
    as such in the dashboard and reports."""
    result = services.get_market_cap_history(conn, ticker)
    if result is None:
        raise HTTPException(status_code=404, detail=f"company not found: {ticker}")
    return result
