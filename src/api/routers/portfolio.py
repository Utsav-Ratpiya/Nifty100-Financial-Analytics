"""src/api/routers/portfolio.py — GET /api/v1/portfolio/stats (Day 40)."""
from fastapi import APIRouter, Depends

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


@router.get("/portfolio/stats")
def get_portfolio_stats(conn=Depends(_db)):
    """P10 through P90 percentile table (plus mean/std/n) for the 10 core
    KPIs across all 92 companies. Reads output/portfolio_stats.csv
    (Sprint 6 Day 37) if present, otherwise computes it on the fly."""
    return services.get_portfolio_stats(conn)
