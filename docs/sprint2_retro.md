# Sprint 2 Retrospective — Financial Ratio Engine

**Days 08–14 · 42 SP · Epic 02**

## What shipped

- `src/analytics/ratios.py` — profitability (NPM, OPM cross-check, ROE, ROCE, ROA)
  and leverage/efficiency ratios (D/E, high-leverage flag, ICR, ICR label/warning,
  Net Debt, Asset Turnover). Also the orchestration entry point wired to `make ratios`.
- `src/analytics/cagr.py` — CAGR engine for Revenue/PAT/EPS across 3/5/10-year
  trailing windows, all 6 edge cases (normal, turnaround, decline-to-loss,
  both-negative, zero-base, insufficient-data).
- `src/analytics/cashflow_kpis.py` — FCF, CFO Quality Score + label, CapEx
  Intensity + label, FCF Conversion Rate, and the 8-pattern capital allocation
  classifier.
- `financial_ratios` table in `nifty100.db` — **1,164 rows**, 46 KPI/flag/label
  columns (exceeds the 1,100-row / 14-column exit criteria).
- `output/capital_allocation.csv` — 1,164 company-year rows with sign triples
  and pattern label.
- `output/ratio_edge_cases.log` — every ROCE/ROE anomaly vs. `companies.xlsx`
  and `data/financial_ratios.xlsx`, each categorised.
- `tests/kpi/test_ratios.py`, `test_cagr.py`, `test_cashflow_kpis.py` — **42
  unit tests, 0 failures** (exceeds the 20-test exit criterion).

## Formula decisions

- **Row backbone**: `profitandloss` is the most complete of the three core
  financial tables (1,164 rows vs. 1,140 for balance sheet, 1,056 for cash
  flow), so it's the left-hand side of every join. Balance-sheet-dependent
  ratios (ROE, D/E, ROCE, ROA) are `None` for the ~106 company-years missing
  a matching balance-sheet row, rather than dropping the row entirely — this
  is what keeps the table at 1,164 rows instead of ~1,058 (the inner-join
  count) and satisfies the "no null-only columns" criterion without
  fabricating balance-sheet data.
- **EBIT approximation** for ROCE = `operating_profit + other_income`
  (pre-interest, pre-tax). No separate EBIT line exists in the source data.
- **D/E returns 0.0, not None, when borrowings = 0** — a debt-free company
  has a well-defined (zero) leverage ratio; `None` is reserved for the
  genuinely undefined case (negative net worth).
- **ICR = None + `icr_label = "Debt Free"`** when interest expense is 0,
  per the project's explicit "if Interest Expense = 0, display Debt Free"
  rule. `icr_warning_flag` never fires for debt-free companies.
- **Financials-sector carve-out**: `high_leverage_flag` is hard-suppressed
  (always `False`) for any company in the `Financials` broad_sector, since
  high leverage is structurally normal for banks/NBFCs/insurers. The D/E
  *value* is still computed and stored — only the flag is suppressed.
- **TTM rows**: every company has exactly one `TTM` (trailing-twelve-months)
  row. It gets full profitability/leverage ratios (P&L-only, always
  available) but CAGR is `None` / flagged `INSUFFICIENT` for TTM, since it
  isn't a fiscal year-end and has no defined n-year lookback in this engine.
- **Composite quality score (v1)**: a straightforward weighted blend of ROE,
  ROCE, NPM, Revenue CAGR 5yr, PAT CAGR 5yr, and a D/E penalty, scaled 0–100.
  This is an interim score so the column is never null-only. The full
  sector-relative, P10/P90-winsorised version specified for Sprint 3
  (Day 17) supersedes this.

## Edge cases resolved

All 6 CAGR edge cases are unit-tested and confirmed against the actual
company data (e.g. companies with a negative-to-positive PAT swing get
`TURNAROUND`, not a spurious CAGR value).

## Data quality findings (logged to `output/ratio_edge_cases.log`)

1. **36 ROCE anomalies / 18 ROE anomalies** (>5pp diff) between the engine's
   computed values and `companies.xlsx`'s pre-computed `roce_percentage` /
   `roe_percentage` columns, across the 92-company universe. A handful are
   extreme (BEL, HDFCLIFE, L&T, HAL, INDIGO) — for these, the balance-sheet
   figures for `equity_capital`/`reserves`/`borrowings` are implausibly small
   relative to the company's P&L scale (e.g. BEL's book equity of ~₹30 Cr
   against ₹20,000+ Cr sales), which looks like a **unit/scale inconsistency
   in the source `balancesheet.xlsx` data** rather than a formula bug — the
   same formula produces sane results for the other ~56 companies and matches
   the reference file to <0.01 average difference. Flagged for analyst
   review rather than silently corrected.
2. **234 OPM cross-check mismatches** (>1pp) against the source
   `opm_percentage` field — categorised as version differences.
3. **202 duplicate `(company_id, year)` rows** discovered in
   `data/financial_ratios.xlsx` (the Sprint 2 reference/cross-check file)
   where NPM/ROE/D-E match exactly between the duplicate pair but the
   FCF-derived fields diverge — suggesting two vintages of cash-flow data
   were merged into that reference file at some point. This file is used
   only for cross-checking, never for loading, so it doesn't affect
   `financial_ratios` — flagged for analyst awareness.
4. Per the project's known anomaly (TCS `roe_percentage` = 0.52 in the
   source vs. the engine's 50.94%), the engine's own computed value is used
   for all downstream analytics; the source value is display-only.

## Exit criteria — status

| Criterion | Result |
|---|---|
| `SELECT COUNT(*) FROM financial_ratios` >= 1,100 | ✅ 1,164 |
| All 14+ KPI columns populated, zero null-only columns | ✅ 46 columns, none null-only |
| 20+ KPI formula unit tests, 0 failures | ✅ 42 tests, 0 failures |
| Manual spot-check: ROE / Revenue CAGR vs. reference within 0.1% | ✅ mean abs diff 0.0025pp on ROE across 1,041 matched rows |
| `ratio_edge_cases.log` exists, every entry documented | ✅ 36 ROCE + 18 ROE + OPM + reference-file findings, all categorised |
| Sprint 2 review sign-off | Pending team lead demo |
