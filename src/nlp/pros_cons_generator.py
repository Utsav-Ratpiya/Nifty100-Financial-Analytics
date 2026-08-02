"""
src/nlp/pros_cons_generator.py — Nifty 100 Analytics
Sprint 5 / Day 30: 12 pro rules + 12 con rules over financial_ratios,
each with a confidence score (0-100). Only rules scoring > 60 are
included in the main output -- but every company must end up with at
least 1 pro and 1 con (Day 30 verification step), so a lower-confidence
fallback rule fires for any company the 24 primary rules miss.
"""
from __future__ import annotations

import os
import sqlite3
import sys

import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BASE_DIR, "nifty100.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

CONFIDENCE_THRESHOLD = 60


def _clip(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def _company_series(fr: pd.DataFrame, company_id: str) -> pd.DataFrame:
    g = fr[fr["company_id"] == company_id].copy()
    g = g[g["year"] != "TTM"]
    g["_cal_year"] = g["year"].str.split("-").str[1].astype(int)
    return g.sort_values("_cal_year")


def _is_increasing(series, n=3):
    vals = [v for v in series if pd.notna(v)]
    if len(vals) < n:
        return False
    tail = vals[-n:]
    return all(tail[i] < tail[i + 1] for i in range(n - 1))


def _is_decreasing(series, n=3):
    vals = [v for v in series if pd.notna(v)]
    if len(vals) < n:
        return False
    tail = vals[-n:]
    return all(tail[i] > tail[i + 1] for i in range(n - 1))


def _all_positive(series, n):
    vals = [v for v in series if pd.notna(v)]
    if len(vals) < n:
        return False
    return all(v > 0 for v in vals[-n:])


def _all_negative(series, n):
    vals = [v for v in series if pd.notna(v)]
    if len(vals) < n:
        return False
    return all(v < 0 for v in vals[-n:])


# ---------------------------------------------------------------------------
# PRO rules — each returns (confidence, text) or None if it doesn't fire
# ---------------------------------------------------------------------------

def pro_01_high_roe(g, latest, sector_avg=None):
    roe_vals = [v for v in g["return_on_equity_pct"].tolist() if pd.notna(v)]
    if len(roe_vals) >= 3 and all(v > 20 for v in roe_vals[-3:]):
        conf = _clip(60 + (min(roe_vals[-3:]) - 20))
        return conf, "Consistently high return on equity above 20% demonstrates exceptional capital efficiency"
    return None


def pro_02_fcf_positive_5yr(g, latest, sector_avg=None):
    if _all_positive(g["free_cash_flow_cr"], 5):
        return 85, "Strong free cash flow generation over 5 years signals healthy business fundamentals"
    return None


def pro_03_debt_free(g, latest, sector_avg=None):
    if latest.get("icr_label") == "Debt Free":
        return 90, "Debt-free balance sheet provides financial flexibility and eliminates interest burden"
    return None


def pro_04_revenue_cagr(g, latest, sector_avg=None):
    val = latest.get("revenue_cagr_5yr")
    if pd.notna(val) and val > 15:
        return _clip(60 + (val - 15)), "Revenue growing at above 15% CAGR over 5 years reflects strong business momentum"
    return None


def pro_05_high_opm(g, latest, sector_avg=None):
    val = latest.get("operating_profit_margin_pct")
    if pd.notna(val) and val > 25:
        return _clip(60 + (val - 25) / 2), "Operating profit margin above 25% indicates strong pricing power and cost discipline"
    return None


def pro_06_pat_cagr(g, latest, sector_avg=None):
    val = latest.get("pat_cagr_5yr")
    if pd.notna(val) and val > 20:
        return _clip(60 + (val - 20) / 2), "Net profit compounding at above 20% over 5 years creates significant shareholder value"
    return None


def pro_07_icr_high(g, latest, sector_avg=None):
    if latest.get("icr_label") == "Debt Free":
        return 90, "Very high interest coverage ratio reflects negligible financial stress from debt servicing"
    icr = latest.get("interest_coverage")
    if pd.notna(icr) and icr > 10:
        return _clip(60 + (icr - 10)), "Very high interest coverage ratio reflects negligible financial stress from debt servicing"
    return None


def pro_08_dividend_yield(g, latest, sector_avg=None):
    div_yield = latest.get("dividend_yield_pct")
    fcf = latest.get("free_cash_flow_cr")
    if pd.notna(div_yield) and div_yield > 2 and pd.notna(fcf) and fcf > 0:
        return _clip(60 + (div_yield - 2) * 5), "Consistent dividend yield above 2% backed by positive free cash flow"
    return None


def pro_09_eps_cagr(g, latest, sector_avg=None):
    val = latest.get("eps_cagr_5yr")
    if pd.notna(val) and val > 15:
        return _clip(60 + (val - 15) / 2), "Earnings per share growing above 15% CAGR indicates strong earnings quality and compounding"
    return None


def pro_10_roe_improving(g, latest, sector_avg=None):
    if _is_increasing(g["return_on_equity_pct"], 3):
        return 75, "Return on equity improving for 3 consecutive years shows strengthening business quality"
    return None


def pro_11_operating_leverage(g, latest, sector_avg=None):
    rev, pat = latest.get("revenue_cagr_5yr"), latest.get("pat_cagr_5yr")
    if pd.notna(rev) and pd.notna(pat) and pat > rev and rev > 0:
        return _clip(60 + (pat - rev)), "Revenue growing slower than profits shows improving operating leverage and scale benefits"
    return None


def pro_12_asset_growth_debt_decline(g, latest, sector_avg=None):
    assets = [v for v in g["net_debt_cr"].tolist() if pd.notna(v)]  # proxy: declining net debt
    if len(assets) >= 3 and _is_decreasing(pd.Series(assets), 3):
        return 65, "Growing asset base funded by internal accruals reflects self-sustaining growth"
    return None


PRO_RULES = [
    ("PRO-01", pro_01_high_roe), ("PRO-02", pro_02_fcf_positive_5yr),
    ("PRO-03", pro_03_debt_free), ("PRO-04", pro_04_revenue_cagr),
    ("PRO-05", pro_05_high_opm), ("PRO-06", pro_06_pat_cagr),
    ("PRO-07", pro_07_icr_high), ("PRO-08", pro_08_dividend_yield),
    ("PRO-09", pro_09_eps_cagr), ("PRO-10", pro_10_roe_improving),
    ("PRO-11", pro_11_operating_leverage), ("PRO-12", pro_12_asset_growth_debt_decline),
]


# ---------------------------------------------------------------------------
# CON rules
# ---------------------------------------------------------------------------

def con_01_high_de(g, latest, sector, sector_avg=None):
    de = latest.get("debt_to_equity")
    if sector != "Financials" and pd.notna(de) and de > 2.0:
        return _clip(60 + (de - 2) * 5), f"Debt-to-equity ratio of {de:.2f} is elevated for a non-financial company and warrants monitoring"
    return None


def con_02_fcf_negative_3yr(g, latest, sector, sector_avg=None):
    if _all_negative(g["free_cash_flow_cr"], 3):
        return 85, "Free cash flow negative for 3 consecutive years raises concern about cash generation quality"
    return None


def con_03_opm_declining(g, latest, sector, sector_avg=None):
    if _is_decreasing(g["operating_profit_margin_pct"], 3):
        return 70, "Operating margins declining for 3 consecutive years suggest pricing or cost pressure"
    return None


def con_04_net_loss(g, latest, sector, sector_avg=None):
    np_ = latest.get("net_profit_margin_pct")
    if pd.notna(np_) and np_ < 0:
        return 90, "Company reported a net loss in the most recent financial year"
    return None


def con_05_revenue_declining(g, latest, sector, sector_avg=None):
    sales = g["sales"].tolist() if "sales" in g.columns else []
    vals = [v for v in sales if pd.notna(v)]
    if len(vals) >= 3 and vals[-1] < vals[-2] < vals[-3]:
        return 75, "Revenue contraction over 2 consecutive years indicates demand weakness or market share loss"
    return None


def con_06_icr_low(g, latest, sector, sector_avg=None):
    if latest.get("icr_warning_flag"):
        return 85, "Interest coverage ratio below 1.5x indicates the company is at risk of not meeting its debt obligations"
    return None


def con_07_dividend_payout_high(g, latest, sector, sector_avg=None):
    val = latest.get("dividend_payout_ratio_pct")
    if pd.notna(val) and val > 100:
        return _clip(60 + (val - 100) / 5), "Dividend payout ratio above 100% means the company is paying dividends from reserves, which is unsustainable"
    return None


def con_08_de_rising(g, latest, sector, sector_avg=None):
    if sector != "Financials" and _is_increasing(g["debt_to_equity"], 3):
        return 70, "Rising debt-to-equity ratio over 3 years suggests increasing financial leverage risk"
    return None


def con_09_eps_declining(g, latest, sector, sector_avg=None):
    eps = g["earnings_per_share"].tolist() if "earnings_per_share" in g.columns else []
    if _is_decreasing(pd.Series(eps), 3):
        return 75, "Earnings per share declining for 3 consecutive years reflects deteriorating profitability"
    return None


def con_10_roce_low(g, latest, sector, sector_avg=None):
    val = latest.get("roce_pct")
    if pd.notna(val) and val < 10:
        return _clip(60 + (10 - val)), "Return on capital employed below 10% suggests the business is not generating sufficient returns on invested capital"
    return None


def con_11_net_debt_high(g, latest, sector, sector_avg=None):
    net_debt = latest.get("net_debt_cr")
    op = latest.get("operating_profit_margin_pct")  # not EBITDA directly; use net_debt_cr vs total_debt as proxy
    total_debt = latest.get("total_debt_cr")
    if pd.notna(net_debt) and pd.notna(total_debt) and total_debt and net_debt > 3 * abs(total_debt) / 3:
        pass
    # Proper EBITDA proxy computed by caller and passed via latest['_ebitda']
    ebitda = latest.get("_ebitda")
    if pd.notna(net_debt) and pd.notna(ebitda) and ebitda and ebitda > 0 and net_debt > 3 * ebitda:
        return 80, "Net debt exceeding 3 times EBITDA is a high leverage ratio and limits financial flexibility"
    return None


def con_12_low_revenue_cagr(g, latest, sector, sector_avg=None):
    val = latest.get("revenue_cagr_5yr")
    if pd.notna(val) and val < 5:
        return _clip(60 + (5 - val)), "Revenue growing at below 5% over 5 years lags inflation and suggests limited business momentum"
    return None


CON_RULES = [
    ("CON-01", con_01_high_de), ("CON-02", con_02_fcf_negative_3yr),
    ("CON-03", con_03_opm_declining), ("CON-04", con_04_net_loss),
    ("CON-05", con_05_revenue_declining), ("CON-06", con_06_icr_low),
    ("CON-07", con_07_dividend_payout_high), ("CON-08", con_08_de_rising),
    ("CON-09", con_09_eps_declining), ("CON-10", con_10_roce_low),
    ("CON-11", con_11_net_debt_high), ("CON-12", con_12_low_revenue_cagr),
]


def generate_for_company(company_id, fr, sector) -> list:
    g = _company_series(fr, company_id)
    if g.empty:
        return []
    latest = g.iloc[-1].to_dict()

    ebitda = None
    if pd.notna(latest.get("operating_profit_margin_pct")) and pd.notna(latest.get("sales")):
        pass  # sales not always present; ebitda proxy computed where possible below
    latest["_ebitda"] = None  # computed in run() before calling, using joined P&L data

    results = []
    for rule_id, fn in PRO_RULES:
        r = fn(g, latest)
        if r and r[0] > CONFIDENCE_THRESHOLD:
            results.append({"company_id": company_id, "type": "pro", "rule_id": rule_id,
                             "text": r[1], "confidence_pct": round(r[0], 1)})
    for rule_id, fn in CON_RULES:
        r = fn(g, latest, sector)
        if r and r[0] > CONFIDENCE_THRESHOLD:
            results.append({"company_id": company_id, "type": "con", "rule_id": rule_id,
                             "text": r[1], "confidence_pct": round(r[0], 1)})
    return results


def _fallback_pro(latest) -> dict:
    """Lowest-confidence-but-real fallback so every company has >=1 pro,
    even if no primary rule cleared the 60% threshold: whichever of ROE /
    revenue CAGR / OPM is least bad, stated plainly (not inflated)."""
    roe = latest.get("return_on_equity_pct")
    rev = latest.get("revenue_cagr_5yr")
    opm = latest.get("operating_profit_margin_pct")
    candidates = [("ROE", roe), ("revenue CAGR (5yr)", rev), ("operating margin", opm)]
    candidates = [(name, v) for name, v in candidates if pd.notna(v)]
    if not candidates:
        return {"type": "pro", "rule_id": "FALLBACK-PRO", "confidence_pct": 30.0,
                "text": "No standout strength identified from available financial data; profile is broadly average"}
    name, val = max(candidates, key=lambda x: x[1])
    return {"type": "pro", "rule_id": "FALLBACK-PRO", "confidence_pct": 45.0,
            "text": f"{name.capitalize()} of {val:.1f}% is the company's most favorable metric among those tracked, "
                    f"though it does not clear a high-confidence threshold"}


def _fallback_con(latest) -> dict:
    de = latest.get("debt_to_equity")
    roce = latest.get("roce_pct")
    rev = latest.get("revenue_cagr_5yr")
    candidates = []
    if pd.notna(de):
        candidates.append(("elevated leverage" if de > 1 else "leverage", de, "high"))
    if pd.notna(roce):
        candidates.append(("moderate capital returns", roce, "low"))
    if pd.notna(rev):
        candidates.append(("moderate growth", rev, "low"))
    if not candidates:
        return {"type": "con", "rule_id": "FALLBACK-CON", "confidence_pct": 30.0,
                "text": "No specific weakness identified from available financial data; profile is broadly average"}
    name = candidates[0][0]
    return {"type": "con", "rule_id": "FALLBACK-CON", "confidence_pct": 45.0,
            "text": f"No single metric triggers a high-confidence concern, but {name} relative to peers is worth monitoring"}


def run():
    conn = sqlite3.connect(DB_PATH)
    fr = pd.read_sql("SELECT fr.*, pl.sales, pl.depreciation FROM financial_ratios fr "
                      "LEFT JOIN profitandloss pl ON fr.company_id = pl.company_id AND fr.year = pl.year", conn)
    mc_latest = pd.read_sql(
        "SELECT m.company_id, m.dividend_yield_pct FROM market_cap m "
        "INNER JOIN (SELECT company_id, MAX(year) as year FROM market_cap GROUP BY company_id) x "
        "ON m.company_id = x.company_id AND m.year = x.year", conn)
    div_yield_map = mc_latest.set_index("company_id")["dividend_yield_pct"].to_dict()
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn).set_index("company_id")["broad_sector"]
    companies = pd.read_sql("SELECT company_id FROM companies", conn)["company_id"].tolist()

    all_results = []
    for cid in companies:
        sector = sectors.get(cid, "Unknown")
        g = _company_series(fr, cid)
        if g.empty:
            continue
        latest = g.iloc[-1].to_dict()
        latest["dividend_yield_pct"] = div_yield_map.get(cid)
        if pd.notna(latest.get("operating_profit_margin_pct")) and pd.notna(latest.get("sales")) and pd.notna(latest.get("depreciation")):
            op_profit_cr = latest["operating_profit_margin_pct"] / 100 * latest["sales"]
            latest["_ebitda"] = op_profit_cr + latest["depreciation"]
        else:
            latest["_ebitda"] = None

        results = []
        for rule_id, fn in PRO_RULES:
            r = fn(g, latest)
            if r and r[0] > CONFIDENCE_THRESHOLD:
                results.append({"company_id": cid, "type": "pro", "rule_id": rule_id,
                                 "text": r[1], "confidence_pct": round(r[0], 1)})
        for rule_id, fn in CON_RULES:
            r = fn(g, latest, sector)
            if r and r[0] > CONFIDENCE_THRESHOLD:
                results.append({"company_id": cid, "type": "con", "rule_id": rule_id,
                                 "text": r[1], "confidence_pct": round(r[0], 1)})

        if not any(r["type"] == "pro" for r in results):
            fb = _fallback_pro(latest)
            fb["company_id"] = cid
            results.append(fb)
        if not any(r["type"] == "con" for r in results):
            fb = _fallback_con(latest)
            fb["company_id"] = cid
            results.append(fb)

        all_results.extend(results)

    result_df = pd.DataFrame(all_results, columns=["company_id", "type", "rule_id", "text", "confidence_pct"])
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "pros_cons_generated.csv")
    result_df.to_csv(path, index=False)

    coverage = result_df.groupby("company_id")["type"].apply(set)
    missing_pro = [c for c, types in coverage.items() if "pro" not in types]
    missing_con = [c for c, types in coverage.items() if "con" not in types]
    all_covered = len(coverage) == len(companies) and not missing_pro and not missing_con

    print(f"wrote {path} ({len(result_df)} rows for {result_df['company_id'].nunique()} companies)")
    print(f"every company has >=1 pro and >=1 con: {all_covered}")
    if missing_pro:
        print(f"  missing pro: {missing_pro}")
    if missing_con:
        print(f"  missing con: {missing_con}")

    conn.close()
    return result_df


if __name__ == "__main__":
    run()
