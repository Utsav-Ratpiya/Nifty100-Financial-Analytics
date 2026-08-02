"""src/api/routers/sectors.py — GET /api/v1/sectors, /sectors/{sector}/companies (Day 40)."""
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


@router.get("/sectors")
def list_sectors(conn=Depends(_db)):
    """All broad sectors with company_count, median_roe, median_pe,
    median_de. Note: the sectors table has 10 distinct broad_sector
    values in this dataset (not 11 — that figure is Sprint 3's 11 narrower
    *peer groups*; see /api/v1/peers/{group_name})."""
    return services.list_sectors(conn)


@router.get("/sectors/{sector}/companies")
def get_sector_companies(sector: str, conn=Depends(_db)):
    """All companies in a broad_sector with latest-year KPIs. 404 for an
    unknown sector name."""
    result = services.get_sector_companies(conn, sector)
    if result is None:
        raise HTTPException(status_code=404, detail=f"unknown sector: {sector}")
    return result
