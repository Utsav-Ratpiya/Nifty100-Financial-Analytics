"""
src/api/main.py — Nifty 100 Analytics
Sprint 6 / Day 38 deliverable: FastAPI application scaffold.

Run with:
    uvicorn src.api.main:app --reload --port 8000     (also `make api`)
    -> docs at http://localhost:8000/docs

All business logic lives in src/api/services.py (framework-independent,
unit-tested in tests/api/test_services.py); this file and src/api/routers/
are a thin HTTP layer on top of it.
"""
from __future__ import annotations

import logging
import os
import sys
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# uvicorn loads this file via the dotted path "src.api.main:app", which adds
# the project root (cwd) to sys.path but NOT this file's own directory
# (src/api/) — so bare imports like "from routers import ..." below, and
# "import services" inside each router file, would fail with
# ModuleNotFoundError otherwise. This line fixes both in one place, since
# sys.path is process-global once set.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from routers import companies, screener, sectors, peers, valuation, portfolio, documents, health  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("nifty100.api")

app = FastAPI(
    title="Nifty 100 Analytics API",
    description="Read-only REST API over the Nifty 100 Analytics SQLite database "
                 "(financial ratios, screener, peer comparison, valuation, reports).",
    version="1.0.0",
)

# CORS — internal use only, all origins allowed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start) * 1000
    logger.info(f'{request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.1f}ms)')
    return response


app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(companies.router, prefix="/api/v1", tags=["companies"])
app.include_router(screener.router, prefix="/api/v1", tags=["screener"])
app.include_router(sectors.router, prefix="/api/v1", tags=["sectors"])
app.include_router(peers.router, prefix="/api/v1", tags=["peers"])
app.include_router(valuation.router, prefix="/api/v1", tags=["valuation"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["portfolio"])
app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
