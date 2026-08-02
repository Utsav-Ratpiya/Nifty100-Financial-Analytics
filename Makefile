.PHONY: load ratios screener peers valuation cluster docs test report dashboard api clean

# Load all Excel files into nifty100.db (Sprint 1 / Day 05)
load:
	python3 src/etl/loader.py

# Generate and populate the financial_ratios table (Sprint 2) + load
# market_cap (Sprint 3 addition) + composite score v2 (Sprint 3 Day 17)
#
# NOTE (fixed 2026-08-01): `src/analytics/ratios.py` — the actual Sprint 2
# ratio engine that computes and writes the financial_ratios table — was
# missing from this target. It worked in the delivered build only because
# nifty100.db shipped with financial_ratios already populated; running
# `make load` on a fresh clone recreates the schema from db/schema.sql
# (empty financial_ratios table), so every downstream step failed with
# "no such table: financial_ratios" until this was added.
ratios:
	python3 src/analytics/ratios.py
	python3 src/etl/load_market_cap.py
	python3 src/analytics/composite_score.py

# Sprint 3: screener presets, peer percentiles, radar charts, exports
screener:
	python3 src/screener/export_screener.py

peers:
	python3 src/analytics/peer.py
	python3 src/analytics/radar.py
	python3 src/screener/export_peer_comparison.py

# Compute FCF yield, sector-median P/E, and Fair/Caution/Discount flags (Sprint 4)
valuation:
	python3 src/analytics/valuation.py

# KMeans clustering (5 archetypes), correlation heatmap, outlier report,
# portfolio percentile stats (Sprint 6 / Day 36-37)
cluster:
	python3 src/analytics/clustering.py
	python3 src/analytics/cluster_profiling.py

# Regenerate docs/analyst_guide.pdf, docs/openapi.json, docs/postman_collection.json
# (Sprint 6 / Day 40, 44)
docs:
	python3 -m src.reports.analyst_guide
	python3 scripts/gen_openapi.py

# Run all pytest tests and generate reports/pytest_report.html (Sprint 6)
test:
	pytest tests/ --html=reports/pytest_report.html --self-contained-html -v

# Generate all company tearsheets, sector reports, and portfolio report (Sprint 5)
report:
	python3 src/nlp/parser.py
	python3 src/nlp/pros_cons_generator.py
	python3 src/analytics/cashflow_intelligence.py
	python3 src/reports/tearsheet.py
	python3 src/reports/sector_report.py
	python3 src/reports/portfolio_summary.py

# Launch Streamlit Dashboard on localhost:8501 (Sprint 4)
dashboard:
	streamlit run src/dashboard/app.py

# Launch FastAPI server on localhost:8000 (Sprint 6)
api:
	uvicorn src.api.main:app --reload --port 8000

# Remove cache (.pyc) and test artifacts. Database remains untouched.
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache reports/pytest_report.html
