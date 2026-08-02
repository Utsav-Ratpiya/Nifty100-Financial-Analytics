"""
src/reports/tearsheet.py — Nifty 100 Analytics
Sprint 5 / Day 33 (template) + Day 34 (batch generation).

2-page company tearsheet:
    Page 1: navy header, 6 KPI tiles (2x3), 10yr Revenue/Net Profit bars,
            ROE/ROCE dual-axis line chart
    Page 2: balance sheet composition stacked bar, cash flow waterfall
            (latest year), pros (green) / cons (red), capital allocation badge

All table cells use Paragraph (word-wrap) instead of raw strings, per the
Sprint 5 spec ("All table columns must use WORDWRAP to prevent text
overflow").
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "reports", "tearsheets")
NAVY = colors.HexColor("#1F4E78")
GREEN = colors.HexColor("#1E7B34")
RED = colors.HexColor("#B32424")
GOLD = colors.HexColor("#FFD966")

styles = getSampleStyleSheet()
CELL_STYLE = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8, leading=10, wordWrap="CJK")
PRO_STYLE = ParagraphStyle("pro", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=GREEN)
CON_STYLE = ParagraphStyle("con", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=RED)


def _load_company_data(conn, company_id):
    company = pd.read_sql("SELECT * FROM companies WHERE company_id=?", conn, params=(company_id,)).iloc[0]
    sector = pd.read_sql("SELECT broad_sector, sub_sector FROM sectors WHERE company_id=?",
                          conn, params=(company_id,))
    sector = sector.iloc[0] if not sector.empty else pd.Series({"broad_sector": "Unknown", "sub_sector": ""})

    fr = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id=? AND year != 'TTM'",
                      conn, params=(company_id,))
    fr["_cal_year"] = fr["year"].str.split("-").str[1].astype(int)
    fr = fr.sort_values("_cal_year")

    pl = pd.read_sql("SELECT year, sales, net_profit FROM profitandloss WHERE company_id=? AND year != 'TTM'",
                      conn, params=(company_id,))
    bs = pd.read_sql("SELECT year, equity_capital, reserves, borrowings, other_liabilities "
                      "FROM balancesheet WHERE company_id=? AND year != 'TTM'", conn, params=(company_id,))
    cf = pd.read_sql("SELECT year, operating_activity, investing_activity, financing_activity, net_cash_flow "
                      "FROM cashflow WHERE company_id=? AND year != 'TTM'", conn, params=(company_id,))

    pros_cons = pd.read_sql("SELECT * FROM pros_cons_generated WHERE company_id=?", conn, params=(company_id,)) \
        if _table_exists(conn, "pros_cons_generated") else pd.DataFrame()

    return company, sector, fr, pl, bs, cf, pros_cons


def _table_exists(conn, name):
    return conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _kpi_tiles_table(fr, latest):
    def fmt(v, suffix="%", digits=1):
        if v is None or pd.isna(v):
            return "N/A"
        return f"{v:.{digits}f}{suffix}"

    tiles = [
        ("ROE", fmt(latest.get("return_on_equity_pct"))),
        ("ROCE", fmt(latest.get("roce_pct"))),
        ("Net Profit Margin", fmt(latest.get("net_profit_margin_pct"))),
        ("D/E", fmt(latest.get("debt_to_equity"), suffix="x")),
        ("Revenue CAGR (5yr)", fmt(latest.get("revenue_cagr_5yr"))),
        ("FCF (latest, Cr)", fmt(latest.get("free_cash_flow_cr"), suffix="", digits=0)),
    ]
    data = []
    for i in range(0, 6, 3):
        row_labels = [Paragraph(f"<b>{t[0]}</b>", CELL_STYLE) for t in tiles[i:i + 3]]
        row_values = [Paragraph(f"<font size=13>{t[1]}</font>", CELL_STYLE) for t in tiles[i:i + 3]]
        data.append(row_labels)
        data.append(row_values)

    t = Table(data, colWidths=[1.9 * inch] * 3)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF4")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#E8EEF4")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _revenue_profit_chart(pl, tmpdir):
    fig, ax = plt.subplots(figsize=(5.4, 2.6))
    years = [y.split("-")[1] for y in pl["year"]]
    x = range(len(years))
    ax.bar([i - 0.2 for i in x], pl["sales"], width=0.4, label="Revenue", color="#1F4E78")
    ax.bar([i + 0.2 for i in x], pl["net_profit"], width=0.4, label="Net Profit", color="#5B9BD5")
    ax.set_xticks(list(x))
    ax.set_xticklabels(years, rotation=45, fontsize=6)
    ax.set_title("Revenue vs Net Profit (₹ Cr)", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=6)
    fig.tight_layout()
    path = os.path.join(tmpdir, "rev_profit.png")
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _roe_roce_chart(fr, tmpdir):
    fig, ax1 = plt.subplots(figsize=(5.4, 2.6))
    years = [y.split("-")[1] for y in fr["year"]]
    ax1.plot(years, fr["return_on_equity_pct"], color="#1F4E78", marker="o", markersize=3, label="ROE %")
    ax1.set_ylabel("ROE %", fontsize=7, color="#1F4E78")
    ax1.tick_params(axis="x", rotation=45, labelsize=6)
    ax1.tick_params(axis="y", labelsize=6)

    ax2 = ax1.twinx()
    ax2.plot(years, fr["roce_pct"], color="#C0392B", marker="s", markersize=3, linestyle="--", label="ROCE %")
    ax2.set_ylabel("ROCE %", fontsize=7, color="#C0392B")
    ax2.tick_params(axis="y", labelsize=6)

    ax1.set_title("ROE vs ROCE (%)", fontsize=9)
    fig.tight_layout()
    path = os.path.join(tmpdir, "roe_roce.png")
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _bs_composition_chart(bs, tmpdir):
    fig, ax = plt.subplots(figsize=(6.6, 2.8))
    years = [y.split("-")[1] for y in bs["year"]]
    ax.bar(years, bs["equity_capital"] + bs["reserves"], label="Equity + Reserves", color="#1F4E78")
    bottom1 = bs["equity_capital"] + bs["reserves"]
    ax.bar(years, bs["borrowings"], bottom=bottom1, label="Borrowings", color="#C0392B")
    bottom2 = bottom1 + bs["borrowings"]
    ax.bar(years, bs["other_liabilities"], bottom=bottom2, label="Other Liabilities", color="#95A5A6")
    ax.set_title("Balance Sheet Composition (₹ Cr)", fontsize=9)
    ax.legend(fontsize=7, loc="upper left")
    ax.tick_params(axis="x", rotation=45, labelsize=6)
    ax.tick_params(axis="y", labelsize=6)
    fig.tight_layout()
    path = os.path.join(tmpdir, "bs_comp.png")
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _cashflow_waterfall_chart(cf_latest, tmpdir):
    labels = ["CFO", "CFI", "CFF", "Net Cash Flow"]
    values = [cf_latest.get("operating_activity", 0) or 0, cf_latest.get("investing_activity", 0) or 0,
              cf_latest.get("financing_activity", 0) or 0, cf_latest.get("net_cash_flow", 0) or 0]
    colors_list = ["#1F4E78" if v >= 0 else "#C0392B" for v in values]

    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    ax.bar(labels, values, color=colors_list)
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_title("Cash Flow Waterfall — Latest Year (₹ Cr)", fontsize=9)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    path = os.path.join(tmpdir, "cf_waterfall.png")
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def build_tearsheet(company_id: str, conn, output_path: str, tmpdir: str) -> bool:
    company, sector, fr, pl, bs, cf, _ = _load_company_data(conn, company_id)
    if fr.empty or len(pl) < 1:
        return False

    latest = fr.iloc[-1].to_dict()
    pros_cons_df = pd.read_csv(os.path.join(BASE_DIR, "output", "pros_cons_generated.csv"))
    company_pros = pros_cons_df[(pros_cons_df.company_id == company_id) & (pros_cons_df.type == "pro")]
    company_cons = pros_cons_df[(pros_cons_df.company_id == company_id) & (pros_cons_df.type == "con")]

    doc = SimpleDocTemplate(output_path, pagesize=letter,
                             topMargin=0.4 * inch, bottomMargin=0.4 * inch,
                             leftMargin=0.5 * inch, rightMargin=0.5 * inch)
    story = []

    # --- Page 1 ---
    header_style = ParagraphStyle("header", parent=styles["Title"], textColor=colors.white, fontSize=16)
    header_table = Table([[Paragraph(f"{company['company_name']} ({company_id})", header_style)]],
                          colWidths=[7.5 * inch])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(header_table)
    story.append(Paragraph(f"{sector['broad_sector']} — {sector['sub_sector']}", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(_kpi_tiles_table(fr, latest))
    story.append(Spacer(1, 10))

    if len(pl) >= 2:
        img1 = Image(_revenue_profit_chart(pl, tmpdir), width=3.6 * inch, height=1.75 * inch)
        img2 = Image(_roe_roce_chart(fr, tmpdir), width=3.6 * inch, height=1.75 * inch)
        chart_row = Table([[img1, img2]], colWidths=[3.7 * inch, 3.7 * inch])
        story.append(chart_row)

    story.append(PageBreak())

    # --- Page 2 ---
    story.append(Paragraph(f"{company['company_name']} ({company_id}) — Balance Sheet & Cash Flow",
                            styles["Heading2"]))
    story.append(Spacer(1, 6))
    if len(bs) >= 2:
        story.append(Image(_bs_composition_chart(bs, tmpdir), width=6.6 * inch, height=2.8 * inch))
    story.append(Spacer(1, 6))
    if len(cf) >= 1:
        story.append(Image(_cashflow_waterfall_chart(cf.iloc[-1].to_dict(), tmpdir), width=6.6 * inch, height=2.6 * inch))
    story.append(Spacer(1, 10))

    cap_label = latest.get("capital_allocation_label", "N/A")
    badge = Table([[Paragraph(f"<b>Capital Allocation Pattern:</b> {cap_label}", CELL_STYLE)]], colWidths=[6.6 * inch])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(badge)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Pros", ParagraphStyle("prohead", parent=styles["Heading3"], textColor=GREEN)))
    for _, row in company_pros.iterrows():
        story.append(Paragraph(f"&#10003; {row['text']} ({row['confidence_pct']:.0f}% confidence)", PRO_STYLE))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Cons", ParagraphStyle("conhead", parent=styles["Heading3"], textColor=RED)))
    for _, row in company_cons.iterrows():
        story.append(Paragraph(f"&#10007; {row['text']} ({row['confidence_pct']:.0f}% confidence)", CON_STYLE))

    doc.build(story)
    return True


def batch_generate():
    conn = sqlite3.connect(DB_PATH)
    companies = pd.read_sql("SELECT company_id FROM companies", conn)["company_id"].tolist()
    print(f"Generating tearsheets for {len(companies)} companies "
          f"(each renders 4 matplotlib charts — this can take 1-3 minutes total, "
          f"the first run especially, while matplotlib builds its font cache)...")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    skipped = []
    generated = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, cid in enumerate(companies, start=1):
            fr_check = pd.read_sql("SELECT COUNT(*) as n FROM financial_ratios WHERE company_id=? AND year != 'TTM'",
                                    conn, params=(cid,)).iloc[0]["n"]
            if fr_check < 3:
                skipped.append({"company_id": cid, "reason": f"only {fr_check} years of data (<3 required)"})
                print(f"  [{i}/{len(companies)}] {cid}: skipped ({fr_check} years of data, <3 required)")
                continue
            path = os.path.join(OUTPUT_DIR, f"{cid}_tearsheet.pdf")
            try:
                ok = build_tearsheet(cid, conn, path, tmpdir)
                if ok:
                    generated += 1
                    print(f"  [{i}/{len(companies)}] {cid}: done")
                else:
                    skipped.append({"company_id": cid, "reason": "insufficient data"})
                    print(f"  [{i}/{len(companies)}] {cid}: skipped (insufficient data)")
            except Exception as e:
                skipped.append({"company_id": cid, "reason": str(e)})
                print(f"  [{i}/{len(companies)}] {cid}: FAILED ({e})")

    conn.close()

    skipped_df = pd.DataFrame(skipped)
    skipped_path = os.path.join(BASE_DIR, "output", "skipped_tearsheets.csv")
    skipped_df.to_csv(skipped_path, index=False)

    print(f"tearsheets generated: {generated} / {len(companies)} (skipped: {len(skipped)})")
    print(f"wrote {skipped_path}")
    return generated, skipped_df


if __name__ == "__main__":
    batch_generate()
