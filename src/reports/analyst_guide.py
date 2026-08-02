"""
src/reports/analyst_guide.py — Nifty 100 Analytics
Sprint 6 / Day 44 deliverable: generates docs/analyst_guide.pdf (10+ pages).

Usage:
    python3 -m src.reports.analyst_guide
"""
from __future__ import annotations

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, ListFlowable, ListItem, Table, TableStyle,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
os.makedirs(DOCS_DIR, exist_ok=True)
OUT_PATH = os.path.join(DOCS_DIR, "analyst_guide.pdf")

NAVY = colors.HexColor("#0B1F3A")


def build():
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=NAVY, spaceBefore=6, spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=NAVY, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=8)
    code = ParagraphStyle("code", parent=styles["Normal"], fontName="Courier", fontSize=8.5,
                           leading=11, backColor=colors.HexColor("#F2F3F5"),
                           borderPadding=6, spaceAfter=10)
    cover_title = ParagraphStyle("cover_title", parent=styles["Title"], textColor=colors.white, fontSize=28)
    cover_sub = ParagraphStyle("cover_sub", parent=styles["Normal"], textColor=colors.HexColor("#C8D3E0"),
                                fontSize=13)

    doc = SimpleDocTemplate(OUT_PATH, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                             topMargin=2*cm, bottomMargin=2*cm)
    story = []

    # --- Cover page ---
    cover = Table([[Paragraph("Nifty 100 Analytics<br/>Analyst Guide", cover_title)]], colWidths=[17*cm],
                  rowHeights=[6*cm])
    cover.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), NAVY), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                               ("LEFTPADDING", (0,0), (-1,-1), 20)]))
    story.append(cover)
    story.append(Spacer(1, 20))
    story.append(Paragraph("A practical guide to the screener, dashboard, PDF reports, and REST API "
                            "built across Sprints 1-6 of the Nifty 100 Analytics project.", cover_sub))
    story.append(PageBreak())

    # --- Table of contents ---
    story.append(Paragraph("Table of Contents", h1))
    toc_items = [
        "1. Project Overview", "2. Using the Streamlit Screener", "3. Navigating the Dashboard",
        "4. Generating PDF Tearsheets and Reports", "5. Calling the REST API",
        "6. Understanding the KPIs", "7. Data Quality Notes and Known Anomalies",
        "8. Troubleshooting Common Issues",
    ]
    story.append(ListFlowable([ListItem(Paragraph(t, body)) for t in toc_items], bulletType="bullet"))
    story.append(PageBreak())

    # --- 1. Overview ---
    story.append(Paragraph("1. Project Overview", h1))
    story.append(Paragraph(
        "Nifty 100 Analytics is an end-to-end equity research toolkit covering all 92 companies with "
        "usable data in the Nifty 100 index. It ingests 12 source Excel files into a single SQLite "
        "database (nifty100.db), computes 45+ financial ratios and CAGR metrics per company-year, runs "
        "a rule-based screener and peer percentile engine, generates PDF tearsheets and sector reports, "
        "produces auto-generated pros/cons via an NLP layer, clusters companies into 5 archetypes, and "
        "exposes everything through a Streamlit dashboard and a FastAPI REST API.", body))
    story.append(Paragraph("Key Makefile commands:", h2))
    story.append(Paragraph(
        "make load &nbsp;&nbsp; — load all Excel files into nifty100.db<br/>"
        "make ratios &nbsp;&nbsp; — run the Ratio Engine, populate financial_ratios<br/>"
        "make test &nbsp;&nbsp; — run the full pytest suite, produce reports/pytest_report.html<br/>"
        "make report &nbsp;&nbsp; — generate all tearsheets, sector reports, portfolio report<br/>"
        "make dashboard &nbsp;&nbsp; — launch Streamlit on localhost:8501<br/>"
        "make api &nbsp;&nbsp; — launch FastAPI on localhost:8000<br/>"
        "make clean &nbsp;&nbsp; — remove cache/test artifacts (database untouched)", code))
    story.append(PageBreak())

    # --- 2. Screener ---
    story.append(Paragraph("2. Using the Streamlit Screener", h1))
    story.append(Paragraph(
        "Open the Screener page from the sidebar. Ten sliders on the left control the active filters: "
        "ROE min, D/E max, FCF min, Revenue CAGR min, PAT CAGR min, OPM min, P/E max, P/B max, "
        "Dividend Yield min, and ICR min. The results table updates live as you move any slider, and a "
        "result-count label above the table tells you how many companies currently match.", body))
    story.append(Paragraph(
        "Six preset buttons — Quality Compounder, Value Pick, Growth Accelerator, Dividend Champion, "
        "Debt-Free Blue Chip, and Turnaround Watch — auto-fill the sliders to a curated combination. "
        "Note: the D/E filter automatically exempts Financials-sector companies (banks, NBFCs, "
        "insurers), since high leverage is structurally normal for that sector. The ICR filter treats "
        "a debt-free company (interest expense = 0) as having infinite interest coverage, so it always "
        "passes any ICR minimum.", body))
    story.append(Paragraph(
        "Use the CSV download button beneath the results table to export exactly the columns currently "
        "shown, for further analysis in Excel or your own model.", body))
    story.append(PageBreak())

    # --- 3. Dashboard ---
    story.append(Paragraph("3. Navigating the Dashboard", h1))
    for title, desc in [
        ("Home", "Six summary KPI tiles (avg ROE, median P/E, median D/E, total companies, median "
                 "Revenue CAGR 5yr, debt-free company count), a sector breakdown donut chart, and a "
                 "top-5 companies table by composite quality score. A year selector in the sidebar "
                 "updates every metric on the page."),
        ("Company Profile", "Search by name or ticker. Shows the company card, 6 KPI tiles, a 10-year "
                             "Revenue/Net Profit bar chart, an ROE/ROCE dual-axis line chart, and "
                             "auto-generated pros/cons badges."),
        ("Screener", "See Section 2."),
        ("Peer Comparison", "Pick a peer group from the dropdown to see a radar chart (company vs peer "
                             "average) and a side-by-side KPI table with the benchmark company "
                             "highlighted."),
        ("Trend Analysis", "Search a company and overlay up to 3 metrics on a 10-year line chart with "
                            "YoY % change annotations."),
        ("Sector Analysis", "A bubble chart (Revenue x ROE, sized by Market Cap) plus a sector median "
                             "KPI bar chart."),
        ("Capital Allocation Map", "A treemap of all 92 companies grouped by their 8 capital allocation "
                                   "patterns (Reinvestor, Shareholder Returns, Distress Signal, etc.) — "
                                   "click a pattern to see its company list."),
        ("Annual Reports", "Search a company to see its available annual report years with clickable "
                            "BSE PDF links; unavailable links show a red 'Report unavailable' badge."),
    ]:
        story.append(Paragraph(title, h2))
        story.append(Paragraph(desc, body))
    story.append(PageBreak())

    # --- 4. Reports ---
    story.append(Paragraph("4. Generating PDF Tearsheets and Reports", h1))
    story.append(Paragraph(
        "Run <font face='Courier'>make report</font> to regenerate everything: 91-92 two-page company "
        "tearsheets (skipping any company with fewer than 3 years of P&L data — see "
        "output/skipped_tearsheets.csv for the current skip list), one PDF per broad sector, and the "
        "portfolio summary PDF (one page per company, alphabetical, with trend arrows).", body))
    story.append(Paragraph(
        "Each tearsheet's page 1 covers 6 KPI tiles, a 10-year Revenue/Net Profit chart, and an "
        "ROE/ROCE dual-axis chart. Page 2 covers balance sheet composition, a cash flow waterfall for "
        "the latest year, auto-generated pros/cons, and a capital allocation pattern badge.", body))
    story.append(Paragraph(
        "Individual tearsheets can also be regenerated for specific tickers only:", body))
    story.append(Paragraph("python3 -m src.reports.tearsheet TCS RELIANCE HDFCBANK", code))
    story.append(PageBreak())

    # --- 5. API ---
    story.append(Paragraph("5. Calling the REST API", h1))
    story.append(Paragraph(
        "Start the API with <font face='Courier'>make api</font> (uvicorn on localhost:8000). Full "
        "interactive documentation is available at http://localhost:8000/docs (Swagger UI), and the "
        "raw spec is exported to docs/openapi.json (a ready-to-import Postman collection is also at "
        "docs/postman_collection.json).", body))
    story.append(Paragraph("Example requests:", h2))
    story.append(Paragraph(
        "curl http://localhost:8000/api/v1/health<br/><br/>"
        "curl http://localhost:8000/api/v1/companies/TCS<br/><br/>"
        "curl \"http://localhost:8000/api/v1/screener?min_roe=15&max_de=1\"<br/><br/>"
        "curl http://localhost:8000/api/v1/sectors/Information%20Technology/companies<br/><br/>"
        "curl http://localhost:8000/api/v1/peers/IT%20Services<br/><br/>"
        "curl -o tcs_tearsheet.pdf http://localhost:8000/api/v1/companies/TCS/tearsheet", code))
    story.append(Paragraph(
        "All endpoints are read-only (GET). Unknown tickers/sectors/peer groups return HTTP 404 with a "
        "descriptive detail message; invalid screener parameter values return HTTP 400.", body))
    story.append(PageBreak())

    # --- 6. KPIs ---
    story.append(Paragraph("6. Understanding the KPIs", h1))
    kpi_table_data = [
        ["KPI", "Meaning", "Edge case handling"],
        ["ROE", "Net profit / (equity + reserves)", "None if net worth <= 0"],
        ["ROCE", "(Operating profit + other income) / capital employed", "None if capital employed <= 0"],
        ["D/E", "Borrowings / (equity + reserves)", "0 (not None) if debt-free"],
        ["ICR", "(Operating profit + other income) / interest", "'Debt Free' label if interest = 0"],
        ["CAGR (Rev/PAT/EPS)", "((end/start)^(1/n) - 1) x 100", "6 edge cases: turnaround, decline-to-loss, "
                                                                    "both-negative, zero-base, insufficient data"],
        ["Capital Allocation", "8-pattern classifier on sign of (CFO, CFI, CFF)", "Reinvestor, Shareholder "
         "Returns, Distress Signal, etc."],
        ["Composite Quality Score", "Weighted blend of ROE/ROCE/NPM/growth/leverage, 0-100", "Sector-relative, "
         "winsorized version"],
    ]
    t = Table(kpi_table_data, colWidths=[3.5*cm, 8*cm, 5.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#D9DEE5")),
        ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#BBBBBB")),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(t)
    story.append(PageBreak())

    # --- 7. Data quality ---
    story.append(Paragraph("7. Data Quality Notes and Known Anomalies", h1))
    story.append(Paragraph(
        "A small number of companies (BEL, HDFCLIFE, HAL, INDIGO) show ROE/ROCE values far above what's "
        "plausible, traced to a balance-sheet scale inconsistency in the source data rather than a "
        "formula bug — the same formulas match the reference file within 0.01 for the other ~85+ "
        "companies. These are documented, categorized, and flagged in output/ratio_edge_cases.log; the "
        "Sprint 6 clustering and outlier-detection modules winsorize/clip extreme values so a handful "
        "of data points don't distort cluster assignment or Z-score outlier flags.", body))
    story.append(Paragraph(
        "17 companies (e.g. Asian Paints, Apollo Hospitals) have a company_name field in companies.xlsx "
        "that carries an embedded newline followed by descriptive text — all report/dashboard code "
        "truncates to the text before the first newline for display.", body))
    story.append(Paragraph(
        "stock_prices and market_cap are SIMULATED datasets (clearly labeled as such in the dashboard "
        "and reports) — do not use for real investment decisions.", body))
    story.append(PageBreak())

    # --- 8. Troubleshooting ---
    story.append(Paragraph("8. Troubleshooting Common Issues", h1))
    for issue, fix in [
        ("`make api` fails with ModuleNotFoundError", "Run `pip install -r requirements.txt` first — "
         "fastapi, uvicorn, and pydantic are required and are not part of the base Python install."),
        ("Dashboard shows 'Ticker not found'", "Check the ticker spelling matches companies.company_id "
         "exactly (all-caps, e.g. TCS not tcs)."),
        ("A tearsheet is missing for a company", "Check output/skipped_tearsheets.csv — companies with "
         "fewer than 3 years of P&L data are skipped by design."),
        ("Screener returns 0 or too many companies", "Check whether you're combining a very tight "
         "threshold (e.g. ROE > 50%) with a loose one — thresholds are combined with AND, not OR."),
        ("`make test` shows fewer than 60 tests", "Confirm pytest, fastapi, and httpx are installed — "
         "two test files (test_loader.py, test_endpoints.py) are skipped if those packages are missing."),
    ]:
        story.append(Paragraph(issue, h2))
        story.append(Paragraph(fix, body))

    doc.build(story)
    return OUT_PATH


if __name__ == "__main__":
    path = build()
    print(f"wrote {path}")
