"""
src/analytics/clustering.py — Nifty 100 Analytics
Sprint 6 / Day 36 deliverable.

KMeans clustering of all 92 companies into 5 archetypes using their latest
fiscal-year financial profile:
    return_on_equity_pct, debt_to_equity, revenue_cagr_5yr, fcf_cagr_5yr,
    operating_profit_margin_pct

Missing values are imputed with the sector median for that feature before
scaling (StandardScaler) and clustering (KMeans, n_clusters=5,
random_state=42 for reproducibility).

Note: financial_ratios has no fcf_cagr_5yr column (Sprint 5's
cashflow_intelligence output left it None — there's no separate FCF time
series stored to compute a CAGR from). This module derives it directly
from the cashflow table's operating_activity + investing_activity series
per company (see _compute_fcf_cagr_5yr), rather than leaving the feature
entirely empty for every company.

Outputs:
    output/cluster_labels.csv  — company_id, cluster_id, cluster_name, distance_from_centroid
    reports/elbow_plot.png     — inertia vs k (2..10), confirming k=5 is reasonable

Usage:
    python3 src/analytics/clustering.py
"""
from __future__ import annotations

import os
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

FEATURES = ["return_on_equity_pct", "debt_to_equity", "revenue_cagr_5yr",
            "fcf_cagr_5yr", "operating_profit_margin_pct"]
N_CLUSTERS = 5
RANDOM_STATE = 42

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


def _compute_fcf_cagr_5yr(conn) -> pd.Series:
    """Derive a 5-year FCF CAGR per company from cashflow.operating_activity
    + investing_activity, since financial_ratios doesn't carry a separate
    FCF time series. Uses the same 6-edge-case CAGR engine as Sprint 2."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from cagr import cagr_with_flag  # noqa: E402

    cf = pd.read_sql("SELECT company_id, year, operating_activity, investing_activity "
                      "FROM cashflow WHERE year != 'TTM'", conn)
    cf["fcf"] = cf["operating_activity"] + cf["investing_activity"]
    cf["_ys"] = cf["year"].apply(_year_sort_key)
    cf = cf.sort_values(["company_id", "_ys"])

    results = {}
    for cid, g in cf.groupby("company_id"):
        values = g["fcf"].tolist()
        if len(values) < 6:
            results[cid] = None
            continue
        start, end = values[-6], values[-1]
        val, _flag = cagr_with_flag(start, end, 5)
        results[cid] = val
    return pd.Series(results, name="fcf_cagr_5yr")


def _latest_fiscal_row(fr: pd.DataFrame) -> pd.DataFrame:
    fy = fr[fr["year"] != "TTM"].copy()
    fy["_ys"] = fy["year"].apply(_year_sort_key)
    idx = fy.groupby("company_id")["_ys"].idxmax()
    return fy.loc[idx].drop(columns=["_ys"])


def _winsorize(df: pd.DataFrame, features: list, lower_pct=1, upper_pct=99) -> pd.DataFrame:
    """Clip each feature at its 1st/99th percentile before scaling.

    Without this, the handful of companies with implausible balance-sheet
    scale (documented in output/ratio_edge_cases.log since Sprint 2 — e.g.
    BEL/HDFCLIFE-style ROE values in the thousands of percent) dominate
    Euclidean distance in KMeans and swamp otherwise-sensible clusters."""
    df = df.copy()
    for col in features:
        lo, hi = df[col].quantile(lower_pct / 100), df[col].quantile(upper_pct / 100)
        df[col] = df[col].clip(lo, hi)
    return df


def _impute_by_sector_median(df: pd.DataFrame, features: list) -> pd.DataFrame:
    df = df.copy()
    for col in features:
        df[col] = df.groupby("broad_sector")[col].transform(lambda s: s.fillna(s.median()))
        # sector-level median can itself be NaN if the whole sector is missing that
        # feature; fall back to the global median in that case
        df[col] = df[col].fillna(df[col].median())
    return df


def _name_clusters(profile: pd.DataFrame) -> dict:
    """Assign a descriptive name to each cluster_id based on its mean
    feature profile, ranked against the other clusters on a simple
    composite quality signal (z-scored ROE + OPM + growth - leverage).
    This is a heuristic starting point — the brief calls for reviewing
    names with the team lead and adjusting based on which companies
    actually land in each cluster."""
    z = (profile - profile.mean()) / profile.std(ddof=0).replace(0, 1)
    quality_score = z["return_on_equity_pct"] + z["operating_profit_margin_pct"] - z["debt_to_equity"]
    growth_score = z["revenue_cagr_5yr"] + z["fcf_cagr_5yr"]

    ordered_by_quality = quality_score.sort_values(ascending=False).index.tolist()
    names = {}
    # Best overall quality profile
    names[ordered_by_quality[0]] = "High-Quality Compounders"
    # Highest growth among what's left
    remaining = [c for c in ordered_by_quality[1:]]
    best_growth = growth_score.loc[remaining].idxmax()
    names[best_growth] = "Emerging Growth"
    remaining = [c for c in remaining if c != best_growth]
    # Lowest leverage + steady (moderate) quality among what's left -> Defensive Dividend Payers
    if remaining:
        lowest_leverage = profile.loc[remaining, "debt_to_equity"].idxmin()
        names[lowest_leverage] = "Defensive Dividend Payers"
        remaining = [c for c in remaining if c != lowest_leverage]
    # Weakest quality profile -> Distressed or Turnaround
    if remaining:
        worst_quality = quality_score.loc[remaining].idxmin()
        names[worst_quality] = "Distressed or Turnaround"
        remaining = [c for c in remaining if c != worst_quality]
    # Whatever's left
    if remaining:
        names[remaining[0]] = "Value Cyclicals"

    return names


def run():
    print("Nifty 100 Analytics — Sprint 6 KMeans Clustering starting...")
    conn = sqlite3.connect(DB_PATH)

    fr = pd.read_sql("SELECT company_id, year, broad_sector, return_on_equity_pct, debt_to_equity, "
                      "revenue_cagr_5yr, operating_profit_margin_pct FROM financial_ratios", conn)
    latest = _latest_fiscal_row(fr).set_index("company_id")

    fcf_cagr = _compute_fcf_cagr_5yr(conn)
    latest["fcf_cagr_5yr"] = fcf_cagr
    latest = latest.reset_index()

    n_missing_before = latest[FEATURES].isna().sum().sum()
    latest = _impute_by_sector_median(latest, FEATURES)
    n_missing_after = latest[FEATURES].isna().sum().sum()
    print(f"  imputed {n_missing_before - n_missing_after} missing feature values with sector medians "
          f"({n_missing_after} still missing after fallback to global median)")

    latest = _winsorize(latest, FEATURES, lower_pct=5, upper_pct=95)

    X = latest[FEATURES].fillna(latest[FEATURES].median()).values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Elbow plot, k=2..10
    inertias = []
    ks = list(range(2, 11))
    for k in ks:
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        km.fit(X_scaled)
        inertias.append(km.inertia_)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(ks, inertias, marker="o", color="#1F5AA6")
    ax.axvline(N_CLUSTERS, color="#B3261E", linestyle="--", label=f"k={N_CLUSTERS} (chosen)")
    ax.set_xlabel("k (number of clusters)")
    ax.set_ylabel("Inertia")
    ax.set_title("KMeans Elbow Plot")
    ax.legend()
    fig.tight_layout()
    elbow_path = os.path.join(REPORTS_DIR, "elbow_plot.png")
    fig.savefig(elbow_path, dpi=150)
    plt.close(fig)
    print(f"  wrote {elbow_path}")

    # Final k=5 fit
    km5 = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=10)
    cluster_ids = km5.fit_predict(X_scaled)
    distances = np.linalg.norm(X_scaled - km5.cluster_centers_[cluster_ids], axis=1)

    latest["cluster_id"] = cluster_ids
    latest["distance_from_centroid"] = distances

    profile = latest.groupby("cluster_id")[FEATURES].mean()
    name_map = _name_clusters(profile)
    latest["cluster_name"] = latest["cluster_id"].map(name_map)

    out = latest[["company_id", "cluster_id", "cluster_name", "distance_from_centroid"]].copy()
    out["distance_from_centroid"] = out["distance_from_centroid"].round(4)
    out_path = os.path.join(OUTPUT_DIR, "cluster_labels.csv")
    out.to_csv(out_path, index=False)
    print(f"  wrote {out_path} ({len(out)} companies)")

    print("\n  cluster profile (mean feature values):")
    for cid in sorted(name_map):
        print(f"    cluster {cid} — {name_map[cid]} ({(latest.cluster_id == cid).sum()} companies)")
        print(f"      {profile.loc[cid].round(2).to_dict()}")

    conn.close()
    return {"row_count": len(out), "elbow_path": elbow_path, "cluster_labels_path": out_path,
            "cluster_names": name_map}


if __name__ == "__main__":
    result = run()
    status = "OK" if result["row_count"] == 92 else "CHECK"
    print(f"\n[{status}] cluster_labels.csv has {result['row_count']} rows (need 92)")
