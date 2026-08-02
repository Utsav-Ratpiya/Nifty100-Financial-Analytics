# Sprint 6 — Clustering + REST API + QA + Sign-Off (Days 36–45, 89 SP)

**Epics 10, 11 & 12 — Clustering + REST API + QA + Sign-Off**

## Sprint Goal

All 16 FastAPI endpoints live and returning correct data. KMeans clustering
assigning all 92 companies to one of 5 labelled archetypes. The full pytest
suite showing 60+ tests with 0 failures. All 20 acceptance gates verified
and the project signed off.

## Run it

```bash
make cluster   # python3 src/analytics/clustering.py -> cluster_labels.csv,
               # elbow_plot.png, correlation_heatmap.png, outlier_report.csv,
               # portfolio_stats.csv
make api       # uvicorn src.api.main:app --reload --port 8000
make test      # pytest tests/ --html=reports/pytest_report.html
make docs      # OpenAPI + Postman export, analyst_guide.pdf
```

Then, for the final sign-off:
```bash
python3 src/reports/acceptance_gates.py       # -> output/acceptance_gates.csv
python3 src/reports/acceptance_checklist.py   # -> docs/acceptance_checklist.pdf
```

## What's in this sprint

| File | Purpose |
|---|---|
| `src/analytics/clustering.py` | KMeans (k=5, `random_state=42`), sector-median imputation, StandardScaler, elbow plot, correlation heatmap, outlier detection, portfolio percentile stats |
| `src/api/main.py` | FastAPI app, CORS (all origins), request-logging middleware, `/api/v1/health` |
| `src/api/db.py` | Shared SQLite connection + NaN-safe JSON serialization helpers |
| `src/api/routers/` | `companies.py`, `screener.py`, `sectors.py`, `peers.py`, `valuation.py`, `portfolio.py`, `documents.py` — 16 endpoints total |
| `src/api/export_postman.py` | Generates `docs/postman_collection.json` from the live OpenAPI spec |
| `src/api/perf_test.py` | 10-concurrent-request load test + dashboard/API consistency check |
| `src/reports/analyst_guide.py` | 10-page PDF: setup, screener, dashboard, tearsheets, API + curl examples, endpoint reference, troubleshooting, data dictionary |
| `src/reports/acceptance_gates.py` | Programmatically runs and records all 20 acceptance gates |
| `src/reports/acceptance_checklist.py` | Final sign-off PDF: 23 deliverables + 20 gate results |
| `tests/api/`, `tests/analytics/test_clustering.py` | 18 + 3 new tests |

## The 16 endpoints

```
GET /api/v1/health
GET /api/v1/companies                          (filters: sector, market_cap_category, search)
GET /api/v1/companies/{ticker}
GET /api/v1/companies/{ticker}/pl               (filters: from_year, to_year)
GET /api/v1/companies/{ticker}/bs
GET /api/v1/companies/{ticker}/cashflow
GET /api/v1/companies/{ticker}/ratios           (filter: year)
GET /api/v1/companies/{ticker}/tearsheet        (binary PDF download)
GET /api/v1/companies/{ticker}/documents
GET /api/v1/screener                            (min_roe, max_de, min_fcf, sector, ...)
GET /api/v1/sectors
GET /api/v1/sectors/{sector}/companies
GET /api/v1/peers/{group_name}
GET /api/v1/companies/{ticker}/peers/compare
GET /api/v1/market-cap/{ticker}
GET /api/v1/portfolio/stats
```

## Two real bugs caught and fixed while building this

1. **NaN isn't valid JSON.** Every endpoint that returns a DataFrame or
   Series needed NaN converted to `None` first (`df_records()` /
   `clean_dict()` helpers in `src/api/db.py`), or those responses would
   500 the moment a company had a missing metric.
2. **FastAPI's default query validation returns 422, but the spec wants
   400** for an invalid screener parameter. Fixed by accepting screener
   query params as raw strings and validating them manually
   (`_parse_float_param()` in `routers/screener.py`).

## Final acceptance gates: 19/20 PASS

The one failure is **AC-17** (92/92 tearsheets ≥30KB) — actually 91/92,
because JIOFIN was correctly skipped back in Sprint 5 for having fewer
than 3 years of financial history (a real IPO-recency data gap, not a
bug). Full detail in `output/acceptance_gates.csv` and
`docs/acceptance_checklist.pdf`.

| # | Gate | Result |
|---|---|---|
| AC-01 | `companies` = 92 rows | PASS |
| AC-02 | ≥90% of companies have ≥10yr P&L/BS/CF | PASS (91.3%) |
| AC-03 | 0 FK violations | PASS |
| AC-04 | `financial_ratios` ≥ 1,100 rows | PASS (1,164) |
| AC-05 | Revenue CAGR spot-check within 0.1% | PASS |
| AC-06 | ROE matches source within 5% (5 companies) | PASS (5/5) |
| AC-07 | Quality preset returns 10–50 companies | PASS (22) |
| AC-08 | Profile screen data layer < 3s | PASS (2.5ms) |
| AC-09 | Screener export valid | PASS |
| AC-10 | No tearsheet overflow (5 sampled) | PASS |
| AC-11 | `/health` returns 200 | PASS |
| AC-12 | TCS ratios ≥10 years | PASS (13) |
| AC-13 | API screener matches XLSX | PASS |
| AC-14 | Peer percentiles cover all 11 groups | PASS |
| AC-15 | All 92 companies clustered | PASS |
| AC-16 | All 92 companies have pro + con | PASS |
| AC-17 | 92 tearsheets ≥30KB | **FAIL (91/92 — JIOFIN, documented)** |
| AC-18 | 60+ tests, 0 failures | PASS (151) |
| AC-19 | `validation_failures.csv` schema | PASS |
| AC-20 | Analyst guide ≥10 pages | PASS (10) |

## Test suite: 151/151 passing

Covers Sprints 1–6: ETL/normaliser (46), KPI ratios/CAGR/cashflow (38+),
DQ rules (16), NLP (8), cash flow intelligence (6), clustering (3), API (18).
