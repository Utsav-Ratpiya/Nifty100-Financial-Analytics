"""src/api/routers/health.py — GET /api/v1/health (Day 38)."""
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


@router.get("/health")
def health(conn=Depends(_db)):
    """Health check: status, per-table row counts (all 10 core tables),
    process uptime, and API version."""
    return services.get_health(conn)
