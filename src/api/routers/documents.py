"""src/api/routers/documents.py — GET /api/v1/companies/{ticker}/documents (Day 40)."""
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


@router.get("/companies/{ticker}/documents")
def get_documents(ticker: str, conn=Depends(_db)):
    """Annual report links with an is_url_valid flag per link. Note:
    is_url_valid is a well-formed-URL check (scheme + host present), not a
    live reachability check — this API has no outbound network access for
    a real-time HTTP HEAD request."""
    result = services.get_company_documents(conn, ticker)
    if result is None:
        raise HTTPException(status_code=404, detail=f"company not found: {ticker}")
    return result
