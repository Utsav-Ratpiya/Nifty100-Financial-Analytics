"""
src/reports/portfolio_summary.py — Nifty 100 Analytics
Sprint 5 / Day 35: one-page-per-company portfolio summary PDF, alphabetical
by ticker. Each page: company name, sector, top 6 KPIs, trend arrows
(up/down/flat vs prior year, flat = within 2%).
"""
from __future__ import annotations

import os
import sqlite3
import sys

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
OUTPUT_PATH = os.path.join(BASE_DIR, "reports", "portfolio", "portfolio_summary.pdf")
NAVY = colors.HexColor("#1F4E78")
GREEN = colors.HexColor("#1E7B34")
RED = colors.HexColor("#B32424")
GRAY = colors.HexColor("#7F8C8D")

styles = getSampleStyleSheet()
CELL_STYLE = ParagraphStyle("cell", parent=styles["Normal"], fontSize=10, leading=13)

KPI_COLS = ["return_on_equity_pct", "roce_pct", "net_profit_margin_pct",
            "debt_to_equity", "revenue_cagr_5yr", "free_cash_flow_cr"]
KPI_LABELS = ["ROE %", "ROCE %", "Net Profit Margin %", "D/E", "Revenue CAGR 5yr %", "FCF (₹ Cr)"]


def _trend_arrow(latest_val, prior_val) -> tuple:
    if pd.isna(latest_val) or pd.isna(prior_val) or prior_val == 0:
        return "→", GRAY
    pct_change = (latest_val - prior_val) / abs(prior_val) * 100
    if abs(pct_change) <= 2:
        return "→", GRAY
    return ("↑", GREEN) if pct_change > 0 else ("↓", RED)


def build_portfolio_summary():
    conn = sqlite3.connect(DB_PATH)
    fr = pd.read_sql("SELECT * FROM financial_ratios WHERE year != 'TTM'", conn)
    fr["_cal_year"] = fr["year"].str.split("-").str[1].astype(int)
    fr = fr.sort_values(["company_id", "_cal_year"])

    companies = pd.read_sql("SELECT company_id, company_name FROM companies ORDER BY company_id", conn)
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn).set_index("company_id")["broad_sector"]
    conn.close()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    doc = SimpleDocTemplate(OUTPUT_PATH, pagesize=letter,
                             topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                             leftMargin=0.7 * inch, rightMargin=0.7 * inch)
    story = []

    n_pages = 0
    for _, comp_row in companies.iterrows():
        cid, name = comp_row["company_id"], comp_row["company_name"]
        g = fr[fr["company_id"] == cid]
        if g.empty:
            continue

        latest = g.iloc[-1]
        prior = g.iloc[-2] if len(g) >= 2 else None
        sector = sectors.get(cid, "Unknown")

        header_style = ParagraphStyle("h", parent=styles["Title"], textColor=colors.white, fontSize=15)
        header = Table([[Paragraph(f"{name} ({cid})", header_style)]], colWidths=[6.6 * inch])
        header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ]))
        story.append(header)
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"Sector: {sector} · Latest period: {latest['year']}", styles["Normal"]))
        story.append(Spacer(1, 16))

        rows = [[Paragraph("<b>Metric</b>", CELL_STYLE), Paragraph("<b>Value</b>", CELL_STYLE),
                 Paragraph("<b>Trend vs prior year</b>", CELL_STYLE)]]
        for col, label in zip(KPI_COLS, KPI_LABELS):
            val = latest.get(col)
            prior_val = prior.get(col) if prior is not None else None
            arrow, color = _trend_arrow(val, prior_val)
            val_str = "N/A" if pd.isna(val) else f"{val:.2f}"
            arrow_para = Paragraph(f'<font color="{color.hexval()}"><b>{arrow}</b></font>', CELL_STYLE)
            rows.append([Paragraph(label, CELL_STYLE), Paragraph(val_str, CELL_STYLE), arrow_para])

        table = Table(rows, colWidths=[3.2 * inch, 1.7 * inch, 1.7 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF4")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        story.append(PageBreak())
        n_pages += 1

    if story and isinstance(story[-1], PageBreak):
        story.pop()

    doc.build(story)
    print(f"wrote {OUTPUT_PATH} ({n_pages} pages)")
    return n_pages


if __name__ == "__main__":
    build_portfolio_summary()
