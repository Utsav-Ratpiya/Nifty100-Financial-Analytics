"""
src/analytics/cluster_profiling.py — Nifty 100 Analytics
Sprint 6 / Day 37 deliverable.

- Correlation heatmap (Pearson, 10 KPIs, latest year, seaborn)
- Outlier detection: per-broad_sector Z-score > 3 on any of the 10 KPIs
- Portfolio-wide percentile table (P10/P25/P50/P75/P90/Mean/Std)

Outputs:
    reports/correlation_heatmap.png
    output/outlier_report.csv
    output/portfolio_stats.csv

Usage:
    python3 src/analytics/cluster_profiling.py
"""
from __future__ import annotations

import os
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

KPI_10 = [
    "return_on_equity_pct", "roce_pct", "net_profit_margin_pct", "debt_to_equity",
    "interest_coverage", "asset_turnover", "revenue_cagr_5yr", "pat_cagr_5yr",
    "eps_cagr_5yr", "free_cash_flow_cr",
]

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def _year_sort_key(label: str):
    if label == "TTM":
        return (9999, 99)
    if "-" in label:
        left, year = label.split("-")
        if left in _MONTHS:
            return (int(year), _MONTHS[left])
        return (int(left), 0)
    return (0, 0)


def _latest_fiscal_row(fr: pd.DataFrame) -> pd.DataFrame:
    fy = fr[fr["year"] != "TTM"].copy()
    fy["_ys"] = fy["year"].apply(_year_sort_key)
    idx = fy.groupby("company_id")["_ys"].idxmax()
    return fy.loc[idx].drop(columns=["_ys"])


def build_correlation_heatmap(latest: pd.DataFrame, out_path: str):
    corr = latest[KPI_10].corr(method="pearson")
    fig, ax = plt.subplots(figsize=(9, 7.5))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, vmin=-1, vmax=1,
                square=True, linewidths=0.5, ax=ax, annot_kws={"size": 7})
    ax.set_xticklabels(ax.get_xticklabels(), rotation=40, ha="right", fontsize=8)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=8)
    ax.set_title("Pearson Correlation — 10 Core KPIs (latest year)", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def detect_outliers(latest: pd.DataFrame) -> pd.DataFrame:
    """For each broad_sector, Z-score each of the 10 KPIs and flag any
    company-metric pair with |Z| > 3. Sectors with too few members for a
    meaningful Z-score (< 3 companies) are skipped for that computation
    (std would be unstable / undefined for n<2)."""
    rows = []
    for sector, g in latest.groupby("broad_sector"):
        if len(g) < 3:
            continue
        for col in KPI_10:
            mean, std = g[col].mean(), g[col].std(ddof=0)
            if std == 0 or pd.isna(std):
                continue
            z = (g[col] - mean) / std
            flagged = g.loc[z.abs() > 3, ["company_id"]].copy()
            for _, r in flagged.iterrows():
                rows.append({
                    "company_id": r["company_id"], "broad_sector": sector, "metric": col,
                    "value": g.loc[g.company_id == r["company_id"], col].iloc[0],
                    "z_score": round(z.loc[g.company_id == r["company_id"]].iloc[0], 2),
                })
    return pd.DataFrame(rows, columns=["company_id", "broad_sector", "metric", "value", "z_score"])


def build_portfolio_stats(latest: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in KPI_10:
        s = latest[col].dropna()
        rows.append({
            "kpi": col,
            "p10": s.quantile(0.10), "p25": s.quantile(0.25), "p50": s.quantile(0.50),
            "p75": s.quantile(0.75), "p90": s.quantile(0.90),
            "mean": s.mean(), "std": s.std(ddof=0), "n": len(s),
        })
    return pd.DataFrame(rows)


def run():
    print("Nifty 100 Analytics — Sprint 6 Cluster Profiling starting...")
    conn = sqlite3.connect(DB_PATH)
    fr = pd.read_sql(f"SELECT company_id, year, broad_sector, {', '.join(KPI_10)} FROM financial_ratios", conn)
    latest = _latest_fiscal_row(fr)

    heatmap_path = os.path.join(REPORTS_DIR, "correlation_heatmap.png")
    build_correlation_heatmap(latest, heatmap_path)
    print(f"  wrote {heatmap_path}")

    outliers = detect_outliers(latest)
    outliers_path = os.path.join(OUTPUT_DIR, "outlier_report.csv")
    outliers.to_csv(outliers_path, index=False)
    print(f"  wrote {outliers_path} ({len(outliers)} outlier company-metric pairs, "
          f"{outliers['company_id'].nunique() if len(outliers) else 0} distinct companies)")

    stats = build_portfolio_stats(latest)
    stats_path = os.path.join(OUTPUT_DIR, "portfolio_stats.csv")
    stats.to_csv(stats_path, index=False)
    print(f"  wrote {stats_path} ({len(stats)} KPIs)")

    conn.close()
    return {"heatmap_path": heatmap_path, "outlier_count": len(outliers), "stats_rows": len(stats)}


if __name__ == "__main__":
    result = run()
    print(f"\n✅ Cluster profiling complete: {result['outlier_count']} outliers flagged, "
          f"{result['stats_rows']} KPI stat rows.")
