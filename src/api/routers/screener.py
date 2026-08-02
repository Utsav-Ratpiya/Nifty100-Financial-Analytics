"""src/api/routers/screener.py — GET /api/v1/screener (Day 40)."""
from typing import Optional

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


@router.get("/screener")
def screener(min_roe: Optional[float] = None, max_de: Optional[float] = None,
             min_fcf: Optional[float] = None, sector: Optional[str] = None,
             min_rev_cagr_5yr: Optional[float] = None, min_pat_cagr_5yr: Optional[float] = None,
             max_pe: Optional[float] = None, conn=Depends(_db)):
    """Ranked company list filtered by any combination of thresholds
    (all optional; omit a param to skip that filter). D/E filters
    automatically exempt Financials-sector companies (see
    config/screener_config.yaml). 400 for an unknown sector name or a
    non-numeric threshold value passed through query params that FastAPI's
    own type coercion didn't already reject."""
    try:
        return services.run_screener(conn, min_roe=min_roe, max_de=max_de, min_fcf=min_fcf, sector=sector,
                                      min_rev_cagr_5yr=min_rev_cagr_5yr, min_pat_cagr_5yr=min_pat_cagr_5yr,
                                      max_pe=max_pe)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
