# Performance & Integration Testing Notes — Sprint 6 / Day 43

## Sandbox constraint (please read first)

This build environment has **no network access** and does not have
`fastapi`, `uvicorn`, `pydantic`, or `httpx` pre-installed (only
`pandas`, `sklearn`, `matplotlib`, `seaborn`, `reportlab` are available).
That means the load test, the live dashboard/API integration test, and the
port-conflict check below **could not actually be executed in this
sandbox** — the API code itself (`src/api/`) was written and syntax-checked
(`python3 -m py_compile`) but never run with a live `uvicorn` server here.

Everything below is either (a) a result that *was* produced in this
sandbox, or (b) a documented test design + exact commands to run locally
once `pip install -r requirements.txt` succeeds. Labeled accordingly.

## Load test — 10 concurrent screener calls (design, not yet run)

```python
# scripts/load_test_screener.py (illustrative — not included in this build)
import concurrent.futures, time, httpx

def call():
    t0 = time.time()
    r = httpx.get("http://localhost:8000/api/v1/screener", params={"min_roe": 15})
    return r.status_code, time.time() - t0

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
    start = time.time()
    results = list(ex.map(lambda _: call(), range(10)))
    total = time.time() - start

print(f"all 10 completed in {total:.2f}s")
assert all(status == 200 for status, _ in results)
assert total < 10.0
```

Run with the API already up (`make api`), then `python3 scripts/load_test_screener.py`.
The screener endpoint calls `screener.engine.apply_filters()` on an
in-memory DataFrame built fresh per request (`build_universe()` does ~5
small SQLite reads and a few merges over 92 rows) — at that scale,
single-request latency should be single-digit milliseconds, comfortably
within the 10-call/10-second budget. The main risk if this *doesn't* hold
is `build_universe()` being rebuilt from scratch on every request; see
"Optimization opportunities" below.

## Dashboard performance — Company Profile screen (measured pattern from Sprint 4)

Sprint 4's Day 27 QA already measured Company Profile screen load time on 5
tickers and confirmed sub-3-second loads, using `@st.cache_data(ttl=600)`
on every query function in `src/dashboard/utils/db.py`. That caching layer
is unchanged in Sprint 6, so this should still hold. Re-verify with:

```bash
make dashboard
# then click through TCS, RELIANCE, HDFCBANK, INFY, SUNPHARMA and time each load
```

## End-to-end: Streamlit (8501) + FastAPI (8000) concurrently (not yet run)

```bash
make api &          # uvicorn on :8000
make dashboard &     # streamlit on :8501
curl -s localhost:8000/api/v1/health | head -c 200
curl -s localhost:8501 -o /dev/null -w "%{http_code}\n"
```

No shared-resource conflicts are expected — both processes open independent
read connections to the same SQLite file (`nifty100.db`), and SQLite
supports concurrent readers natively. Neither process writes to the
database at request time (all writes happen in the batch pipeline scripts —
`make ratios`, `make report`, clustering — run separately beforehand), so
there's no read/write lock contention to worry about at request time.

## SQLite indexing (verified in this sandbox)

`financial_ratios` already has `idx_fr_company_year` on `(company_id, year)`
from Sprint 2 (confirmed present via `PRAGMA index_list(financial_ratios)`).
No additional indexes were added in Sprint 6 — every other table the API
reads (`companies`, `sectors`, `market_cap`, `peer_groups`,
`peer_percentiles`) is small enough (<=1,200 rows) that a full table scan
costs microseconds; an index would not be measurable at this data volume.
If the dataset grows well past Nifty 100 scale, `company_id` indexes on
`profitandloss`, `balancesheet`, and `cashflow` would be the next
candidates.

## Optimization opportunities (if the un-run load test above comes back slow)

1. **Cache `build_universe()`** — it's rebuilt from 5 SQLite reads on every
   `/screener` and `/sectors/*` call. A simple in-process cache with a TTL
   (mirroring the dashboard's `@st.cache_data(ttl=600)` pattern) would cut
   repeated-request latency substantially, at the cost of up to `ttl`
   seconds of staleness after a `make ratios` re-run.
2. **`sqlite3.connect(..., check_same_thread=False)` + a connection pool**
   if concurrent request volume grows — right now each request opens and
   closes its own connection via the `Depends(_db)` generator, which is
   fine at Nifty-100 request volumes but adds per-request connection-open
   overhead that a pool would remove.

## What to record here once you run these locally

Please append: total wall time for the 10-call load test, whether it met
the <10s bar, and Company Profile screen timings for the 5 tickers above.
