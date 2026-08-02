# Sprint 4 — Streamlit Dashboard + Valuation (Days 22–28, 55 SP)

**Epics 05 & 06 — Streamlit Dashboard + Valuation**

> Note: this sprint's code (`src/dashboard/`, `src/analytics/valuation.py`)
> was built separately and uploaded back into the combined project rather
> than built in this session — this README documents it from inspecting
> what's actually in the codebase, so run instructions and file paths are
> verified, but day-by-day build notes aren't available the way Sprints
> 1/2/3/5/6 have them.

## Sprint Goal

An 8-screen Streamlit dashboard running on `localhost:8501`, all screens
loading without errors for any of the 92 companies. A valuation module
producing `valuation_summary.xlsx` with FCF yield, P/E flags, and
overvaluation/discount labels.

## Run it

```bash
make dashboard   # or: streamlit run src/dashboard/app.py
make valuation   # python3 src/analytics/valuation.py
```

## What's in this sprint

| File | Purpose |
|---|---|
| `src/dashboard/app.py` | Streamlit entry point, sidebar navigation |
| `src/dashboard/pages/01_home.py` | Summary KPI tiles, sector donut chart, top-5 by composite score |
| `src/dashboard/pages/02_profile.py` | Company search, KPI tiles, 10yr revenue/profit + ROE/ROCE charts, pros/cons |
| `src/dashboard/pages/03_screener.py` | 10 metric sliders, 6 preset buttons, live results table, CSV export |
| `src/dashboard/pages/04_peers.py` | Peer group dropdown, radar chart, side-by-side KPI table |
| `src/dashboard/pages/05_trends.py` | Multi-metric overlay (up to 3), 10yr line chart with YoY annotations |
| `src/dashboard/pages/06_sectors.py` | Bubble chart (Revenue x ROE, sized by market cap), sector median bars |
| `src/dashboard/pages/07_capital.py` | Treemap of 92 companies by 8 capital allocation patterns |
| `src/dashboard/pages/08_reports.py` | Annual report search + links, broken-link badge |
| `src/dashboard/utils/db.py` | Shared, cached (`@st.cache_data`) data loader functions |
| `src/analytics/valuation.py` | FCF yield, sector-relative P/E flags |
| `output/valuation_summary.xlsx` | All 92 companies — P/E, P/B, EV/EBITDA, FCF yield, valuation flag |
| `output/valuation_flags.csv` | Only Caution/Discount-flagged companies |

## Valuation methodology (from `valuation.py`)

- **FCF Yield %** = FCF / market_cap_crore × 100
- **5yr median P/E** = median of the company's own trailing 5 years of P/E
- **Sector median P/E** = median of the *latest-year* P/E across all
  companies in the same `broad_sector`
- **Flag**: `Caution` if P/E > sector median × 1.5, `Discount` if P/E <
  sector median × 0.7, otherwise `Fair`

This depends on the `market_cap` table, which — despite this sprint's name
— actually got loaded back in Sprint 3, because the screener needed P/E/P/B/
dividend yield before Sprint 4 started. Sprint 4 just reads it rather than
re-parsing `market_cap.xlsx`. See the Sprint 3 retro for that decision.

## Exit criteria

- [ ] All 8 Streamlit screens load without errors for any of the 92 tickers — not independently re-verified headlessly in this session; the underlying data layer (same `build_universe()` and `nifty100.db` the API and screener use) is verified via Sprint 6's API/dashboard consistency check
- [x] `valuation_summary.xlsx` has 92 rows with all required columns
- [ ] Company Profile screen loads in under 3 seconds — proxied in Sprint 6 (AC-08) via the underlying data-layer query time (2.5ms), not a full browser render measurement
- [ ] Sprint review sign-off — pending team lead demo
