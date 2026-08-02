# Sprint 1 — Data Foundation (Days 01–07, 34 SP)

**Epic 01 — Data Ingestion & ETL**

## Sprint Goal

A fully loaded and validated SQLite database (`nifty100.db`) containing 10
tables built from the 12 source Excel files. All 16 data quality rules run,
with CRITICAL failures excluded from the load and documented.

## Run it

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

make load   # runs src/etl/loader.py -> nifty100.db, output/load_audit.csv,
            # output/validation_failures.csv
make test   # runs tests/etl/ (46 tests)
```

## What's in this sprint

| File | Purpose |
|---|---|
| `db/schema.sql` | 10-table SQLite schema: companies, profitandloss, balancesheet, cashflow, analysis, documents, prosandcons, sectors, stock_prices, peer_groups |
| `src/etl/normaliser.py` | `normalize_ticker()`, `normalize_year()` — handles 5 different raw period formats found in the real data (`'Dec 2012'`, `'Mar-13'`, bare `'2013'`, `'TTM'`, and junk-suffixed entries like `'Mar 2016 9m'`) |
| `src/etl/validator.py` | All 16 DQ rules (DQ-01 → DQ-16) |
| `src/etl/loader.py` | Loads all 12 source files, runs DQ rules, excludes CRITICAL rows, populates `nifty100.db` |
| `tests/etl/test_normalise.py` | 36 tests (20 year-parsing cases + 15 ticker cases + 1 extra) |
| `tests/etl/test_loader.py` | 10 tests on source-file row counts/columns |
| `notebooks/exploratory_queries.sql` | 10 sanity queries |

## Why `market_cap.xlsx` and the source `financial_ratios.xlsx` aren't loaded here

7 core files (companies, P&L, balance sheet, cash flow, analysis, documents,
pros/cons) + sectors + stock_prices + peer_groups = exactly 10 tables.
`market_cap.xlsx` was originally deferred to Sprint 4 (valuation) — though
in practice the Sprint 3 screener needed it earlier and it got loaded then.
The source `financial_ratios.xlsx` is a pre-computed reference file used
only to cross-check the ratio engine's own output (Sprint 2, Day 13) — it's
never loaded as raw transactional data.

## Real data quality findings (not synthetic examples)

- **8 tickers appear in P&L/balance sheet/cash flow but have no row in
  `companies.xlsx`**: `ULTRACEMCO`, `ZOMATO`, `VBL`, `VEDL`, `UNITDSPR`,
  `ZYDUSLIFE`, `WIPRO`, `UNIONBANK`. Excluded from the load (DQ-03,
  CRITICAL) and logged in `validation_failures.csv` — this is a
  data-sourcing gap, not a loader bug.
- **Duplicate `(company_id, year)` rows** in several tables — some
  companies have both a `'Mon YYYY'` row and a separate `'YYYY'`-only row
  for what looks like the same fiscal year. The loader keeps the first
  occurrence and logs the rest (DQ-02, CRITICAL).
- **JIOFIN** has only 3 years of P&L history (recent IPO) — expected, not
  a bug. This becomes relevant again in Sprint 5 (tearsheet generation).

## Exit criteria — verified

- [x] `SELECT COUNT(*) FROM companies` = 92
- [x] `PRAGMA foreign_key_check` → 0 rows
- [x] `load_audit.csv` shows per-table read/loaded/rejected counts with reasons
- [x] 46 ETL unit tests pass (spec required 35+)
- [x] Manual review of 5 random companies — row counts sane, no surprises
- [ ] Sprint review sign-off — pending team lead demo
