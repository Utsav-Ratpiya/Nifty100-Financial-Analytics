"""
src/api/services.py — Nifty 100 Analytics
Sprint 6 / Day 38-40 deliverable (service layer).

Every function here is plain Python (sqlite3 + pandas only, no FastAPI or
pydantic dependency), so the business logic is fully unit-testable without
the API framework installed — see tests/api/test_services.py. The FastAPI
routers in src/api/routers/ are thin wrappers around these functions that
translate return values into HTTP responses and status codes.

Convention: functions that can 404 return None (not raise) when the
resource isn't found; the router layer converts None -> HTTPException(404).
Functions that can 400 raise ValueError with a human-readable message; the
router layer converts ValueError -> HTTPException(400).
"""
from __future__ import annotations

import math
import os
import sqlite3
import sys
import time
from functools import wraps

import numpy as np
import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEARSHEET_DIR = os.path.join(BASE_DIR, "reports", "tearsheets")

sys.path.insert(0, os.path.join(BASE_DIR, "src"))

_ALL_TABLES = ["companies", "profitandloss", "balancesheet", "cashflow", "analysis",
               "documents", "prosandcons", "sectors", "stock_prices", "financial_ratios"]

_SERVER_START_TIME = time.time()
_API_VERSION = "1.0.0"


def _sanitize(obj):
    """Recursively replace NaN/Inf floats and numpy scalar types with
    JSON-safe Python equivalents. pandas leaves missing numeric values as
    NaN, and Starlette's JSONResponse calls json.dumps(..., allow_nan=False)
    — so any NaN reaching a route handler raises
    'ValueError: Out of range float values are not JSON compliant: nan'.
    Every public service function below is wrapped with @_sanitized to
    guarantee its return value is always safe to serialize."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if obj is pd.NaT:
        return None
    return obj


def _sanitized(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return _sanitize(fn(*args, **kwargs))
    return wrapper


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_dicts(rows) -> list:
    return [dict(r) for r in rows]


def _year_sort_key(label: str):
    months = {m: i for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}
    if label == "TTM":
        return (9999, 99)
    if "-" in label:
        left, year = label.split("-")
        if left in months:
            return (int(year), months[left])
        return (int(left), 0)
    return (0, 0)


def _filter_year_range(df: pd.DataFrame, from_year: str | None, to_year: str | None) -> pd.DataFrame:
    """from_year/to_year are 'YYYY-MM' per the API spec (e.g. '2020-04');
    we compare on the calendar year component against the 'Mon-YYYY' /
    'YYYY-00' labels stored in the source tables."""
    if from_year is None and to_year is None:
        return df
    df = df.copy()
    df["_ys"] = df["year"].apply(_year_sort_key)

    def _year_num(s):
        return int(s.split("-")[0])

    if from_year:
        lo = _year_num(from_year)
        df = df[df["_ys"].apply(lambda t: t[0] >= lo)]
    if to_year:
        hi = _year_num(to_year)
        df = df[df["_ys"].apply(lambda t: t[0] <= hi)]
    return df.drop(columns=["_ys"])


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@_sanitized
def get_health(conn: sqlite3.Connection) -> dict:
    row_counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in _ALL_TABLES}
    return {
        "status": "ok",
        "db_row_counts": row_counts,
        "uptime_seconds": round(time.time() - _SERVER_START_TIME, 1),
        "version": _API_VERSION,
    }


# ---------------------------------------------------------------------------
# GET /companies
# ---------------------------------------------------------------------------

@_sanitized
def list_companies(conn: sqlite3.Connection, sector: str | None = None,
                    market_cap_category: str | None = None, search: str | None = None) -> list:
    query = """
        SELECT c.company_id, c.company_name, s.broad_sector, s.sub_sector,
               c.roce_percentage, c.roe_percentage
        FROM companies c
        LEFT JOIN sectors s ON s.company_id = c.company_id
    """
    df = pd.read_sql(query, conn)
    if sector:
        df = df[df["broad_sector"].str.lower() == sector.lower()]
    if market_cap_category:
        mc = pd.read_sql("SELECT company_id, market_cap_category FROM sectors", conn)
        keep_ids = mc[mc["market_cap_category"].str.lower() == market_cap_category.lower()]["company_id"]
        df = df[df["company_id"].isin(keep_ids)]
    if search:
        needle = search.lower()
        df = df[df["company_id"].str.lower().str.contains(needle) |
                df["company_name"].str.lower().str.contains(needle, na=False)]
    return df.to_dict(orient="records")


# ---------------------------------------------------------------------------
# GET /companies/{ticker}
# ---------------------------------------------------------------------------

@_sanitized
def get_company_profile(conn: sqlite3.Connection, ticker: str) -> dict | None:
    company = pd.read_sql("SELECT * FROM companies WHERE company_id = ?", conn, params=(ticker,))
    if company.empty:
        return None
    sector = pd.read_sql("SELECT broad_sector, sub_sector, market_cap_category FROM sectors "
                          "WHERE company_id = ?", conn, params=(ticker,))
    fr = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? AND year != 'TTM'",
                      conn, params=(ticker,))

    result = company.iloc[0].to_dict()
    result.update(sector.iloc[0].to_dict() if not sector.empty else {})
    if not fr.empty:
        fr["_ys"] = fr["year"].apply(_year_sort_key)
        latest = fr.sort_values("_ys").iloc[-1].drop("_ys").to_dict()
        result["latest_year"] = latest.pop("year")
        result["latest_kpis"] = latest
    else:
        result["latest_year"] = None
        result["latest_kpis"] = {}
    return result


# ---------------------------------------------------------------------------
# GET /companies/{ticker}/pl, /bs, /cashflow
# ---------------------------------------------------------------------------

def _get_history(conn, ticker, table, from_year=None, to_year=None) -> list | None:
    exists = conn.execute("SELECT 1 FROM companies WHERE company_id = ?", (ticker,)).fetchone()
    if exists is None:
        return None
    df = pd.read_sql(f"SELECT * FROM {table} WHERE company_id = ?", conn, params=(ticker,))
    df = _filter_year_range(df, from_year, to_year)
    df = df.drop(columns=[c for c in ("row_id", "source_id", "raw_year") if c in df.columns])
    return df.to_dict(orient="records")


@_sanitized
def get_company_pl(conn, ticker, from_year=None, to_year=None):
    return _get_history(conn, ticker, "profitandloss", from_year, to_year)


@_sanitized
def get_company_bs(conn, ticker, from_year=None, to_year=None):
    return _get_history(conn, ticker, "balancesheet", from_year, to_year)


@_sanitized
def get_company_cashflow(conn, ticker, from_year=None, to_year=None):
    return _get_history(conn, ticker, "cashflow", from_year, to_year)


# ---------------------------------------------------------------------------
# GET /companies/{ticker}/ratios
# ---------------------------------------------------------------------------

@_sanitized
def get_company_ratios(conn, ticker, year: str | None = None) -> list | None:
    exists = conn.execute("SELECT 1 FROM companies WHERE company_id = ?", (ticker,)).fetchone()
    if exists is None:
        return None
    if year:
        df = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? AND year = ?",
                          conn, params=(ticker, year))
    else:
        df = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ?", conn, params=(ticker,))
    df = df.drop(columns=["row_id"], errors="ignore")
    return df.to_dict(orient="records")


# ---------------------------------------------------------------------------
# GET /companies/{ticker}/tearsheet
# ---------------------------------------------------------------------------

def get_tearsheet_path(ticker: str) -> str | None:
    path = os.path.join(TEARSHEET_DIR, f"{ticker}_tearsheet.pdf")
    return path if os.path.exists(path) else None


# ---------------------------------------------------------------------------
# GET /screener
# ---------------------------------------------------------------------------

_SCREENER_PARAM_MAP = {
    "min_roe": "min_roe", "max_de": "max_de", "min_fcf": "min_fcf",
    "sector": None,  # handled separately, not a threshold metric
    "min_rev_cagr_5yr": "min_rev_cagr_5yr", "min_pat_cagr_5yr": "min_pat_cagr_5yr",
    "max_pe": "max_pe",
}


@_sanitized
def run_screener(conn, min_roe=None, max_de=None, min_fcf=None, sector=None,
                  min_rev_cagr_5yr=None, min_pat_cagr_5yr=None, max_pe=None) -> list:
    """Wraps src/screener/engine.py's apply_filters(). Raises ValueError
    (-> HTTP 400 at the router layer) for an unknown sector name or a
    non-numeric threshold value."""
    from screener.engine import load_config, apply_filters
    from screener.universe import build_universe

    filters = {}
    for name, value in [("min_roe", min_roe), ("max_de", max_de), ("min_fcf", min_fcf),
                         ("min_rev_cagr_5yr", min_rev_cagr_5yr), ("min_pat_cagr_5yr", min_pat_cagr_5yr),
                         ("max_pe", max_pe)]:
        if value is None:
            continue
        try:
            filters[name] = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"invalid numeric value for {name}: {value!r}")

    universe = build_universe(conn)
    if sector is not None:
        valid_sectors = set(universe["broad_sector"].dropna().unique())
        if sector not in valid_sectors:
            raise ValueError(f"unknown sector: {sector!r} (valid: {sorted(valid_sectors)})")
        universe = universe[universe["broad_sector"] == sector]

    config = load_config()
    result = apply_filters(universe, filters, config) if filters else universe.sort_values(
        "composite_quality_score", ascending=False)
    return result.to_dict(orient="records")


# ---------------------------------------------------------------------------
# GET /sectors, /sectors/{sector}/companies
# ---------------------------------------------------------------------------

@_sanitized
def list_sectors(conn) -> list:
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)
    fr = pd.read_sql("SELECT company_id, year, return_on_equity_pct FROM financial_ratios "
                      "WHERE year != 'TTM'", conn)
    fr["_ys"] = fr["year"].apply(_year_sort_key)
    idx = fr.groupby("company_id")["_ys"].idxmax()
    latest_roe = fr.loc[idx, ["company_id", "return_on_equity_pct"]]

    mc_max = pd.read_sql("SELECT company_id, MAX(year) AS year FROM market_cap GROUP BY company_id", conn)
    mc = pd.read_sql("SELECT * FROM market_cap", conn).merge(mc_max, on=["company_id", "year"])

    from screener.universe import build_universe
    universe = build_universe(conn)

    out = []
    for sector_name, g in sectors.groupby("broad_sector"):
        ids = g["company_id"]
        roe_vals = latest_roe[latest_roe.company_id.isin(ids)]["return_on_equity_pct"]
        pe_vals = mc[mc.company_id.isin(ids)]["pe_ratio"]
        de_vals = universe[universe.company_id.isin(ids)]["debt_to_equity"]
        out.append({
            "broad_sector": sector_name,
            "company_count": len(ids),
            "median_roe": _safe_median(roe_vals),
            "median_pe": _safe_median(pe_vals),
            "median_de": _safe_median(de_vals),
        })
    return out


def _safe_median(series):
    m = series.dropna().median() if len(series) else None
    return round(m, 2) if m is not None and pd.notna(m) else None


@_sanitized
def get_sector_companies(conn, sector: str) -> list | None:
    from screener.universe import build_universe
    universe = build_universe(conn)
    valid_sectors = set(universe["broad_sector"].dropna().unique())
    if sector not in valid_sectors:
        return None
    return universe[universe["broad_sector"] == sector].to_dict(orient="records")


# ---------------------------------------------------------------------------
# GET /peers/{group_name}, /companies/{ticker}/peers/compare
# ---------------------------------------------------------------------------

@_sanitized
def get_peer_group(conn, group_name: str) -> list | None:
    valid = pd.read_sql("SELECT DISTINCT peer_group_name FROM peer_groups", conn)["peer_group_name"].tolist()
    if group_name not in valid:
        return None
    members = pd.read_sql("SELECT company_id FROM peer_groups WHERE peer_group_name = ?",
                           conn, params=(group_name,))["company_id"].tolist()
    percentiles = pd.read_sql(
        "SELECT company_id, metric, value, percentile_rank FROM peer_percentiles WHERE peer_group_name = ?",
        conn, params=(group_name,))
    out = []
    for cid in members:
        sub = percentiles[percentiles.company_id == cid]
        out.append({
            "company_id": cid,
            "metrics": {r["metric"]: {"value": r["value"], "percentile_rank": r["percentile_rank"]}
                        for _, r in sub.iterrows()},
        })
    return out


_RADAR_AXES = ["return_on_equity_pct", "roce_pct", "net_profit_margin_pct", "debt_to_equity",
               "free_cash_flow_cr", "pat_cagr_5yr", "revenue_cagr_5yr", "composite_quality_score"]


@_sanitized
def get_peer_compare(conn, ticker: str) -> dict | None:
    exists = conn.execute("SELECT 1 FROM companies WHERE company_id = ?", (ticker,)).fetchone()
    if exists is None:
        return None

    group_row = pd.read_sql("SELECT peer_group_name FROM peer_groups WHERE company_id = ?",
                             conn, params=(ticker,))
    if group_row.empty:
        return {"company_id": ticker, "peer_group_name": None,
                "message": "No peer group assigned", "company_values": {}, "peer_group_average": {},
                "benchmark_company": None}
    group_name = group_row.iloc[0]["peer_group_name"]

    members = pd.read_sql("SELECT company_id FROM peer_groups WHERE peer_group_name = ?",
                           conn, params=(group_name,))["company_id"].tolist()

    fr = pd.read_sql("SELECT * FROM financial_ratios WHERE year != 'TTM'", conn)
    fr["_ys"] = fr["year"].apply(_year_sort_key)
    idx = fr.groupby("company_id")["_ys"].idxmax()
    latest = fr.loc[idx]

    group_rows = latest[latest.company_id.isin(members)]
    company_row = group_rows[group_rows.company_id == ticker]
    company_values = company_row.iloc[0][_RADAR_AXES].to_dict() if not company_row.empty else {}
    peer_avg = {axis: _safe_median(group_rows[axis]) for axis in _RADAR_AXES}

    benchmark = group_rows.sort_values("composite_quality_score", ascending=False).iloc[0]["company_id"] \
        if not group_rows.empty else None

    return {
        "company_id": ticker, "peer_group_name": group_name, "message": None,
        "company_values": company_values, "peer_group_average": peer_avg,
        "benchmark_company": benchmark,
    }


# ---------------------------------------------------------------------------
# GET /market-cap/{ticker}
# ---------------------------------------------------------------------------

@_sanitized
def get_market_cap_history(conn, ticker: str) -> list | None:
    exists = conn.execute("SELECT 1 FROM companies WHERE company_id = ?", (ticker,)).fetchone()
    if exists is None:
        return None
    df = pd.read_sql("SELECT year, market_cap_crore, enterprise_value_crore, pe_ratio, pb_ratio, "
                      "ev_ebitda, dividend_yield_pct FROM market_cap WHERE company_id = ? ORDER BY year",
                      conn, params=(ticker,))
    return df.to_dict(orient="records")


# ---------------------------------------------------------------------------
# GET /portfolio/stats
# ---------------------------------------------------------------------------

@_sanitized
def get_portfolio_stats(conn) -> list:
    stats_path = os.path.join(OUTPUT_DIR, "portfolio_stats.csv")
    if os.path.exists(stats_path):
        return pd.read_csv(stats_path).to_dict(orient="records")
    # fallback: compute on the fly if Day 37's output hasn't been generated yet
    from analytics.cluster_profiling import build_portfolio_stats, _latest_fiscal_row, KPI_10
    fr = pd.read_sql(f"SELECT company_id, year, {', '.join(KPI_10)} FROM financial_ratios", conn)
    latest = _latest_fiscal_row(fr)
    return build_portfolio_stats(latest).to_dict(orient="records")


# ---------------------------------------------------------------------------
# GET /companies/{ticker}/documents
# ---------------------------------------------------------------------------

def _is_well_formed_url(url: str) -> bool:
    """Format-only validity check (scheme + netloc present) — this API has
    no network egress for a live HTTP HEAD check, so 'valid' here means
    'well-formed', not 'currently reachable'. Documented in the OpenAPI
    description for this field."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(str(url))
        return bool(parsed.scheme in ("http", "https") and parsed.netloc)
    except Exception:
        return False


@_sanitized
def get_company_documents(conn, ticker: str) -> list | None:
    exists = conn.execute("SELECT 1 FROM companies WHERE company_id = ?", (ticker,)).fetchone()
    if exists is None:
        return None
    df = pd.read_sql("SELECT year, annual_report_url FROM documents WHERE company_id = ? ORDER BY year DESC",
                      conn, params=(ticker,))
    df["is_url_valid"] = df["annual_report_url"].apply(_is_well_formed_url)
    return df.to_dict(orient="records")
