"""
src/screener/engine.py — Nifty 100 Analytics Screener
Sprint 3 / Day 15 (filter engine core) + Day 16 (6 presets) + Day 17
(composite quality score v2, sector-relative, winsorized).

Loads config/screener_config.yaml and applies threshold filters to the
screener universe (src/screener/universe.py -> financial_ratios + P&L +
market_cap, one row per company).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # -> src/, so 'screener.*' resolves

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "screener_config.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _passes_threshold(series: pd.Series, direction: str, threshold: float,
                       column: str, universe: pd.DataFrame) -> pd.Series:
    """Returns a boolean mask. Handles the two documented special cases:
      - D/E filters (column == 'debt_to_equity') automatically pass every
        Financials-sector company regardless of threshold.
      - ICR filters (column == 'interest_coverage') treat a None/NaN value
        that corresponds to icr_label == 'Debt Free' as +infinity, so it
        always passes a minimum-ICR filter.
    """
    if column == "debt_to_equity":
        sector_exempt = universe["broad_sector"] == "Financials"
    else:
        sector_exempt = pd.Series(False, index=universe.index)

    if column == "interest_coverage":
        debt_free = universe["icr_label"] == "Debt Free"
        effective = series.copy()
        effective[debt_free] = np.inf
    else:
        effective = series
        debt_free = pd.Series(False, index=universe.index)

    if direction == "min":
        passes = effective >= threshold
    elif direction == "max":
        passes = effective <= threshold
    else:
        raise ValueError(f"unknown direction: {direction}")

    return passes | sector_exempt


def apply_filters(universe: pd.DataFrame, filters: dict, config: dict | None = None) -> pd.DataFrame:
    """Apply a dict of {metric_name: threshold} filters to the universe.
    Metric names must exist in config['metrics']. Returns a DataFrame sorted
    by composite_quality_score descending."""
    if config is None:
        config = load_config()
    metrics = config["metrics"]

    mask = pd.Series(True, index=universe.index)
    for metric_name, threshold in filters.items():
        if metric_name not in metrics:
            raise ValueError(f"unknown screener metric: {metric_name}")
        spec = metrics[metric_name]
        column, direction = spec["column"], spec["direction"]
        if column not in universe.columns:
            raise ValueError(f"universe is missing column required by {metric_name}: {column}")
        row_mask = _passes_threshold(universe[column], direction, threshold, column, universe)
        row_mask = row_mask.fillna(False)
        mask &= row_mask

    result = universe[mask].copy()
    return result.sort_values("composite_quality_score", ascending=False)


def run_preset(preset_name: str, universe: pd.DataFrame | None = None, config: dict | None = None) -> pd.DataFrame:
    """Run one of the 6 named presets from screener_config.yaml.
    'turnaround_watch' additionally requires D/E declining year-over-year,
    which needs a 2-year lookback not expressible as a simple threshold --
    handled separately here using the financial_ratios table directly."""
    if config is None:
        config = load_config()
    if universe is None:
        from screener.universe import build_universe
        universe = build_universe()

    if preset_name not in config["presets"]:
        raise ValueError(f"unknown preset: {preset_name}")

    preset = config["presets"][preset_name]
    result = apply_filters(universe, preset["filters"], config)

    if preset_name == "turnaround_watch":
        result = _apply_de_declining_filter(result)

    return result


def _apply_de_declining_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only companies whose D/E declined from the prior fiscal year to
    the latest fiscal year (used by the Turnaround Watch preset)."""
    import sqlite3
    conn = sqlite3.connect(os.path.join(BASE_DIR, "nifty100.db"))
    fr = pd.read_sql("SELECT company_id, year, debt_to_equity FROM financial_ratios WHERE year != 'TTM'", conn)
    conn.close()
    fr["_cal_year"] = fr["year"].str.split("-").str[1].astype(int)

    keep_ids = []
    for cid in df["company_id"]:
        sub = fr[fr["company_id"] == cid].sort_values("_cal_year")
        if len(sub) < 2:
            continue
        prev_de, latest_de = sub["debt_to_equity"].iloc[-2], sub["debt_to_equity"].iloc[-1]
        if pd.notna(prev_de) and pd.notna(latest_de) and latest_de < prev_de:
            keep_ids.append(cid)

    return df[df["company_id"].isin(keep_ids)]


PRESET_NAMES = ["quality_compounder", "value_pick", "growth_accelerator",
                "dividend_champion", "debt_free_blue_chip", "turnaround_watch"]
