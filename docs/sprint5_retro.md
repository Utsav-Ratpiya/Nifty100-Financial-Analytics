# Sprint 5 Retrospective — Cash Flow Intelligence + Reports + NLP

**Days 29–35 · 70 SP · Epics 07, 08 & 09**

## What shipped

- `src/nlp/parser.py` — regex parser for `analysis.xlsx` free-text growth
  fields, `output/analysis_parsed.csv` (63 rows) + `output/parse_failures.csv`
  (17 rows) + `output/analysis_cagr_divergence.csv` (cross-check vs computed
  CAGR, >5pt divergence).
- `src/nlp/pros_cons_generator.py` — all 12 pro rules + 12 con rules,
  confidence-scored, plus a documented fallback so every company has ≥1 pro
  and ≥1 con even when no primary rule clears 60% confidence.
  `output/pros_cons_generated.csv` — 549 rows across all 92 companies.
- `src/analytics/cashflow_intelligence.py` — distress signal + deleveraging
  flag detection on top of Sprint 2's `cashflow_kpis.py`.
  `output/cashflow_intelligence.xlsx` (92 rows), `output/distress_alerts.csv`
  (13 flagged), `output/pattern_changes.csv` (49 YoY capital allocation
  pattern changes).
- `src/reports/tearsheet.py` — 2-page ReportLab tearsheet per company: KPI
  tiles, revenue/profit bars, ROE/ROCE dual-axis line, balance sheet
  stacked bar, cash flow waterfall, pros/cons, capital allocation badge.
  **91 of 92 tearsheets generated** (`reports/tearsheets/`), all ≥30KB.
- `src/reports/sector_report.py` — sector PDF reports with median KPIs +
  full company table. **10 sector reports** (`reports/sector/`).
- `src/reports/portfolio_summary.py` — one page per company, alphabetical,
  top 6 KPIs with up/down/flat trend arrows vs prior year.
  `reports/portfolio/portfolio_summary.pdf` — 92 pages.
- 22 new tests (`tests/nlp/`, `tests/analytics/test_cashflow_intelligence.py`).
  **130 total tests passing, 0 failures.**

## Real-data findings (documented, not silently patched)

- **JIOFIN skipped from tearsheets** — only 2 non-TTM years of financial
  history (recent IPO). Logged in `output/skipped_tearsheets.csv` exactly
  per spec ("skip companies with fewer than 3 years of data").
- **Only 10 sector reports generated, not 11.** The real `sectors` table
  has 10 distinct `broad_sector` values, not 11 — this matches the Sprint 2
  finding (23 Financials companies vs the doc's assumed 19) and the Sprint 3
  finding (11 *peer groups*, which is a separate grouping from sectors).
  Sectors and peer groups are different taxonomies; the "11" in the Sprint
  3 spec refers to peer groups, which is correctly 11. Sectors are 10.
- **`analysis.xlsx`'s exact spec regex `(\d+)\s*Years?:?\s*([\d.]+)%` cannot
  parse negative percentages** (e.g. `'1 Year: -2%'`, seen in real
  `stock_price_cagr` data) because the value capture group `[\d.]+` has no
  minus-sign handling. Implemented literally per spec rather than silently
  adding sign support — these rows are correctly routed to
  `parse_failures.csv`. Also correctly fails to match `'TTM:'` and
  `'Last Year:'` labels (no leading digit), by design.
- **PRO-03 (debt-free) never fires** — no company is debt-free in its
  *latest* fiscal year in this dataset (34 historical Debt-Free rows exist,
  all in earlier years). Confirmed via direct query, not a bug.
- **Net Debt > 3x EBITDA (CON-11) uses an EBITDA proxy** —
  `operating_profit_margin_pct/100 * sales + depreciation` — since no raw
  EBITDA column exists anywhere upstream.

## Exit criteria — status

| Criterion | Result |
|---|---|
| `pros_cons_generated.csv` has ≥1 pro and ≥1 con for every company | ✅ (92/92, verified programmatically) |
| All 92 tearsheets exist, each ≥30KB | ⚠ 91/92 (JIOFIN correctly skipped, documented) |
| Visual review of 5 tearsheets — no overflow, no blank pages | ✅ (TCS, HDFCBANK, RELIANCE, SUNPHARMA, TATASTEEL spot-checked) |
| `cashflow_intelligence.xlsx` has 92 rows, all required columns | ✅ |
| Sprint review sign-off | Pending team lead demo |
