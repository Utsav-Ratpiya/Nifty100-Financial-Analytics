import json, os

ENDPOINTS = [
    ("GET", "/api/v1/health", "Health check", "health",
     [], "status, per-table row counts, uptime, version"),
    ("GET", "/api/v1/companies", "List companies", "companies",
     [("sector", "query", False), ("market_cap_category", "query", False), ("search", "query", False)],
     "All 92 companies (id, name, sector, ROE, ROCE), optionally filtered"),
    ("GET", "/api/v1/companies/{ticker}", "Get company profile", "companies",
     [("ticker", "path", True)], "Full company profile + latest-year KPIs. 404 if unknown."),
    ("GET", "/api/v1/companies/{ticker}/pl", "Get P&L history", "companies",
     [("ticker", "path", True), ("from_year", "query", False), ("to_year", "query", False)],
     "P&L history, optional YYYY-MM year range filter"),
    ("GET", "/api/v1/companies/{ticker}/bs", "Get balance sheet history", "companies",
     [("ticker", "path", True), ("from_year", "query", False), ("to_year", "query", False)],
     "Balance sheet history, optional year range filter"),
    ("GET", "/api/v1/companies/{ticker}/cashflow", "Get cash flow history", "companies",
     [("ticker", "path", True), ("from_year", "query", False), ("to_year", "query", False)],
     "Cash flow history, optional year range filter"),
    ("GET", "/api/v1/companies/{ticker}/ratios", "Get computed KPIs", "companies",
     [("ticker", "path", True), ("year", "query", False)],
     "All computed KPIs per year, or a single year if `year` is passed"),
    ("GET", "/api/v1/companies/{ticker}/tearsheet", "Download tearsheet PDF", "companies",
     [("ticker", "path", True)], "The pre-generated 2-page tearsheet PDF (application/pdf)"),
    ("GET", "/api/v1/companies/{ticker}/peers/compare", "Get radar comparison data", "companies",
     [("ticker", "path", True)], "8-axis metric values vs peer group average + benchmark company"),
    ("GET", "/api/v1/companies/{ticker}/documents", "Get annual report links", "documents",
     [("ticker", "path", True)], "Annual report links with is_url_valid (format check) flag"),
    ("GET", "/api/v1/screener", "Run the screener", "screener",
     [("min_roe", "query", False), ("max_de", "query", False), ("min_fcf", "query", False),
      ("sector", "query", False), ("min_rev_cagr_5yr", "query", False),
      ("min_pat_cagr_5yr", "query", False), ("max_pe", "query", False)],
     "Ranked company list filtered by any combination of thresholds. 400 for invalid params."),
    ("GET", "/api/v1/sectors", "List sectors", "sectors",
     [], "All broad sectors with company_count, median_roe, median_pe, median_de"),
    ("GET", "/api/v1/sectors/{sector}/companies", "Get companies in a sector", "sectors",
     [("sector", "path", True)], "All companies in a broad_sector with latest-year KPIs. 404 if unknown."),
    ("GET", "/api/v1/peers/{group_name}", "Get a peer group", "peers",
     [("group_name", "path", True)], "All companies in a peer group with percentile ranks. 404 if unknown."),
    ("GET", "/api/v1/market-cap/{ticker}", "Get valuation multiples history", "valuation",
     [("ticker", "path", True)], "Historical P/E, P/B, EV/EBITDA, dividend yield, 2019-2024 (SIMULATED data)"),
    ("GET", "/api/v1/portfolio/stats", "Get portfolio percentile stats", "portfolio",
     [], "P10-P90 percentile table for 10 core KPIs across all 92 companies"),
]

paths = {}
for method, path, summary, tag, params, desc in ENDPOINTS:
    parameters = []
    for name, loc, required in params:
        parameters.append({
            "name": name, "in": loc, "required": required,
            "schema": {"type": "string" if loc == "path" or name in ("sector", "market_cap_category", "search",
                                                                        "from_year", "to_year", "year", "group_name") else "number"},
        })
    paths.setdefault(path, {})[method.lower()] = {
        "summary": summary,
        "description": desc,
        "tags": [tag],
        "parameters": parameters,
        "responses": {
            "200": {"description": "Successful response"},
            "404": {"description": "Resource not found"},
            **({"400": {"description": "Invalid parameter value"}} if path == "/api/v1/screener" else {}),
        },
    }

openapi = {
    "openapi": "3.0.3",
    "info": {
        "title": "Nifty 100 Analytics API",
        "description": "Read-only REST API over the Nifty 100 Analytics SQLite database "
                        "(financial ratios, screener, peer comparison, valuation, reports). "
                        "Sprint 6 / Day 40 deliverable.",
        "version": "1.0.0",
    },
    "servers": [{"url": "http://localhost:8000"}],
    "paths": paths,
}

import sys; os.chdir(os.path.join(os.path.dirname(__file__), '..')); os.makedirs('docs', exist_ok=True)
with open("docs/openapi.json", "w") as f:
    json.dump(openapi, f, indent=2)

# Postman collection derived from the same endpoint list
items = []
for method, path, summary, tag, params, desc in ENDPOINTS:
    query_params = [{"key": n, "value": ""} for n, loc, req in params if loc == "query"]
    postman_path = path.replace("{ticker}", ":ticker").replace("{sector}", ":sector") \
                        .replace("{group_name}", ":group_name")
    items.append({
        "name": summary,
        "request": {
            "method": method,
            "header": [],
            "url": {
                "raw": "{{base_url}}" + postman_path,
                "host": ["{{base_url}}"],
                "path": postman_path.strip("/").split("/"),
                "query": query_params,
            },
            "description": desc,
        },
    })

postman = {
    "info": {
        "name": "Nifty 100 Analytics API",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "variable": [{"key": "base_url", "value": "http://localhost:8000"}],
    "item": items,
}

with open("docs/postman_collection.json", "w") as f:
    json.dump(postman, f, indent=2)

print(f"wrote docs/openapi.json ({len(paths)} paths, {len(ENDPOINTS)} operations)")
print(f"wrote docs/postman_collection.json ({len(items)} requests)")
