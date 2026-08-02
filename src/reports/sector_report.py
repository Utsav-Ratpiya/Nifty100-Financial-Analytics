"""
src/reports/sector_report.py — Nifty 100 Analytics
Sprint 5 / Day 34: batch sector report generation — 11 PDFs, one per
broad_sector. Each: sector summary page (median KPIs) + table of all
companies in the sector with 8 metrics each.
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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "reports", "sector")
NAVY = colors.HexColor("#1F4E78")

styles = getSampleStyleSheet()
CELL_STYLE = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7.5, leading=9, wordWrap="CJK")

METRIC_COLS = ["return_on_equity_pct", "roce_pct", "net_profit_margin_pct", "debt_to_equity",
               "revenue_cagr_5yr", "pat_cagr_5yr", "free_cash_flow_cr", "composite_quality_score"]
METRIC_LABELS = ["ROE %", "ROCE %", "NPM %", "D/E", "Rev CAGR 5yr %", "PAT CAGR 5yr %", "FCF (Cr)", "Composite"]


def _latest_per_company(conn):
    fr = pd.read_sql("SELECT * FROM financial_ratios WHERE year != 'TTM'", conn)
    fr["_cal_year"] = fr["year"].str.split("-").str[1].astype(int)
    latest = fr.sort_values("_cal_year").groupby("company_id").tail(1)
    companies = pd.read_sql("SELECT company_id, company_name FROM companies", conn)
    return latest.merge(companies, on="company_id")


def build_sector_report(sector_name: str, sector_df: pd.DataFrame, output_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                             topMargin=0.4 * inch, bottomMargin=0.4 * inch,
                             leftMargin=0.4 * inch, rightMargin=0.4 * inch)
    story = []

    header_style = ParagraphStyle("header", parent=styles["Title"], textColor=colors.white, fontSize=16)
    header = Table([[Paragraph(f"{sector_name} — Sector Report", header_style)]], colWidths=[7.7 * inch])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(header)
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"{len(sector_df)} companies in this sector", styles["Normal"]))
    story.append(Spacer(1, 10))

    # Sector median KPI summary
    medians = [sector_df[c].median() for c in METRIC_COLS]
    story.append(Paragraph("Sector Median KPIs", styles["Heading3"]))
    med_data = [METRIC_LABELS, [f"{v:.2f}" if pd.notna(v) else "N/A" for v in medians]]
    med_table = Table(med_data, colWidths=[0.96 * inch] * 8)
    med_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF4")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(med_table)
    story.append(Spacer(1, 14))

    # Company list table
    story.append(Paragraph("Companies", styles["Heading3"]))
    header_row = [Paragraph("<b>Company</b>", CELL_STYLE)] + [Paragraph(f"<b>{l}</b>", CELL_STYLE) for l in METRIC_LABELS]
    rows = [header_row]
    for _, row in sector_df.sort_values("composite_quality_score", ascending=False).iterrows():
        cells = [Paragraph(f"{row['company_name']} ({row['company_id']})", CELL_STYLE)]
        for c in METRIC_COLS:
            v = row.get(c)
            cells.append(Paragraph("N/A" if pd.isna(v) else f"{v:.2f}", CELL_STYLE))
        rows.append(cells)

    col_widths = [1.9 * inch] + [0.83 * inch] * 8
    company_table = Table(rows, colWidths=col_widths, repeatRows=1)
    company_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FB")]),
    ]))
    story.append(company_table)

    doc.build(story)


def batch_generate():
    conn = sqlite3.connect(DB_PATH)
    universe = _latest_per_company(conn)
    conn.close()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    generated = []
    for sector_name, g in universe.groupby("broad_sector"):
        safe_name = sector_name.replace(" ", "_").replace("/", "_")
        path = os.path.join(OUTPUT_DIR, f"{safe_name}_report.pdf")
        build_sector_report(sector_name, g, path)
        generated.append((sector_name, len(g), path))

    print(f"sector reports generated: {len(generated)}")
    for name, n, path in generated:
        print(f"  {name}: {n} companies -> {os.path.basename(path)}")
    return generated


if __name__ == "__main__":
    batch_generate()
