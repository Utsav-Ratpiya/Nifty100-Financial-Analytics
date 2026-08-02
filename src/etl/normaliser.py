"""
normaliser.py — Nifty 100 Analytics ETL
Sprint 1 / Day 02 deliverable.

Provides two pure functions used everywhere company_id and year/period values
are read from the raw Excel source files:

    normalize_ticker(raw)  -> canonical uppercase, trimmed ticker string
    normalize_year(raw)    -> canonical period label, or (None, reason) on failure

Design notes (documented here because both functions have to deal with real
messy source data found in the Nifty 100 workbooks):

TICKERS
-------
Source files are inconsistent about whitespace and case
(" reliance", "Reliance ", "RELIANCE" all refer to the same company).
normalize_ticker() trims surrounding whitespace, collapses internal
whitespace, and upper-cases the result. It does NOT validate that the
ticker exists in companies.xlsx -- that is the validator's job (DQ-03,
FK integrity), because loader.py needs to load orphan rows and log them
rather than silently drop them.

YEARS / PERIODS
----------------
Across profitandloss.xlsx, balancesheet.xlsx, cashflow.xlsx and
financial_ratios.xlsx the "year" column is a free-text period label that
appears in at least five different shapes:

    'Dec 2012'        -> Mon YYYY                       (most common)
    'Mar-13'          -> Mon-YY (2-digit year)           (cashflow.xlsx)
    '2013'            -> bare 4-digit year, no month     (balancesheet.xlsx)
    'TTM'             -> trailing-twelve-months, not a fiscal year end
    'Mar 2023 15'     -> Mon YYYY plus a stray trailing token (dirty data)
    'Mar 2016 9m'     -> Mon YYYY plus a "Nm" (N months) interim-period tag

normalize_year() converts all of these into ONE canonical, sortable label:

    'Mon-YYYY'   e.g. 'Mar-2024', 'Dec-2012'   -- normal fiscal period
    'YYYY-00'    e.g. '2013-00'                -- bare year, month unknown
    'TTM'        unchanged                     -- trailing twelve months
    None         with a reason string          -- unparseable

Malformed trailing tokens ('15', '9m') are stripped and the row is still
parsed, but the loader logs these as WARN-level normalisation events (not
hard failures) since the underlying Mon+Year is still recoverable.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

_MONTHS = {
    "jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr",
    "may": "May", "jun": "Jun", "jul": "Jul", "aug": "Aug",
    "sep": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dec",
}

# Mon[-\s]YY(YY)? optionally followed by junk (extra digits, "9m", etc.)
_MON_YEAR_RE = re.compile(
    r"^(?P<mon>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"[\s\-]*"
    r"(?P<year>\d{2,4})"
    r"(?P<trailing>.*)$",
    re.IGNORECASE,
)

_BARE_YEAR_RE = re.compile(r"^(?P<year>\d{4})$")


def normalize_ticker(raw: Optional[str]) -> Optional[str]:
    """Trim, collapse whitespace, and upper-case a company_id / ticker.

    Returns None if raw is None/NaN or empty after stripping.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return None
    text = re.sub(r"\s+", " ", text)
    return text.upper()


def _expand_2digit_year(yy: str) -> str:
    """Expand a 2-digit year to 4 digits. Dataset spans 2007-2024, so any
    2-digit year is assumed 2000s."""
    if len(yy) == 4:
        return yy
    return f"20{yy}"


def normalize_year(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Normalize a raw period value into a canonical label.

    Returns (label, reason):
        - (label, None)        on success
        - (None, reason_str)   on failure -- caller should log to
                                 output/parse_failures / validation_failures.
    """
    if raw is None:
        return None, "null_value"

    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return None, "empty_value"

    # TTM (trailing twelve months) - not a calendar period, keep as sentinel
    if text.upper() == "TTM":
        return "TTM", None

    # Mon YYYY / Mon-YY / Mon YYYY <junk>
    m = _MON_YEAR_RE.match(text)
    if m:
        mon_key = m.group("mon").lower()
        mon = _MONTHS[mon_key]
        year = _expand_2digit_year(m.group("year"))
        if not (2000 <= int(year) <= 2035):
            return None, f"year_out_of_range:{year}"
        trailing = m.group("trailing").strip()
        label = f"{mon}-{year}"
        if trailing:
            # Recoverable, but flag it so the loader can log a WARN.
            return label, f"trailing_junk_stripped:'{trailing}'"
        return label, None

    # Bare 4-digit year, no month info
    m = _BARE_YEAR_RE.match(text)
    if m:
        year = m.group("year")
        if not (2000 <= int(year) <= 2035):
            return None, f"year_out_of_range:{year}"
        return f"{year}-00", None

    return None, f"unparseable:'{text}'"


def normalize_year_simple(raw: Optional[str]) -> Optional[str]:
    """Convenience wrapper returning just the label (or None). Used by
    loader.py in the hot path where the reason is only needed for logging."""
    label, _ = normalize_year(raw)
    return label
