-- schema.sql
-- Nifty 100 Analytics — Sprint 1 / Day 04 deliverable
-- 10 base tables loaded directly from the 7 core + 3 of the 5 supplementary
-- source files (sectors, stock_prices, peer_groups). market_cap and the
-- source financial_ratios.xlsx are cross-reference files used later
-- (Sprint 4 valuation, Sprint 2 cross-checks) and are NOT part of this
-- initial 10-table load. The *computed* financial_ratios table (built by
-- the ratio engine in Sprint 2) is added on top of this schema separately.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS companies;
CREATE TABLE companies (
    company_id          TEXT PRIMARY KEY,      -- normalized ticker, e.g. 'ABB'
    company_logo        TEXT,
    company_name        TEXT NOT NULL,
    chart_link          TEXT,
    about_company       TEXT,
    website             TEXT,
    nse_profile         TEXT,
    bse_profile         TEXT,
    face_value          REAL,
    book_value          REAL,
    roce_percentage     REAL,                  -- source pre-computed, display-only
    roe_percentage      REAL                    -- source pre-computed, display-only
);

DROP TABLE IF EXISTS profitandloss;
CREATE TABLE profitandloss (
    row_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER,
    company_id          TEXT NOT NULL,
    year                TEXT NOT NULL,          -- normalized period label, e.g. 'Mar-2024'
    raw_year             TEXT,                  -- original unnormalized value, kept for audit
    sales               REAL,
    expenses            REAL,
    operating_profit    REAL,
    opm_percentage      REAL,
    other_income        REAL,
    interest            REAL,
    depreciation        REAL,
    profit_before_tax   REAL,
    tax_percentage      REAL,
    net_profit          REAL,
    eps                 REAL,
    dividend_payout     REAL,
    UNIQUE (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

DROP TABLE IF EXISTS balancesheet;
CREATE TABLE balancesheet (
    row_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER,
    company_id          TEXT NOT NULL,
    year                TEXT NOT NULL,
    raw_year             TEXT,
    equity_capital      REAL,
    reserves            REAL,
    borrowings          REAL,
    other_liabilities   REAL,
    total_liabilities   REAL,
    fixed_assets        REAL,
    cwip                REAL,
    investments         REAL,
    other_asset         REAL,
    total_assets        REAL,
    UNIQUE (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

DROP TABLE IF EXISTS cashflow;
CREATE TABLE cashflow (
    row_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER,
    company_id          TEXT NOT NULL,
    year                TEXT NOT NULL,
    raw_year             TEXT,
    operating_activity  REAL,
    investing_activity  REAL,
    financing_activity  REAL,
    net_cash_flow       REAL,
    UNIQUE (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

DROP TABLE IF EXISTS analysis;
CREATE TABLE analysis (
    row_id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id                   INTEGER,
    company_id                  TEXT NOT NULL,
    compounded_sales_growth     TEXT,           -- free text, parsed in Sprint 5 NLP module
    compounded_profit_growth    TEXT,
    stock_price_cagr            TEXT,
    roe                         TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

DROP TABLE IF EXISTS documents;
CREATE TABLE documents (
    row_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER,
    company_id          TEXT NOT NULL,
    year                INTEGER,
    annual_report_url   TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

DROP TABLE IF EXISTS prosandcons;
CREATE TABLE prosandcons (
    row_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER,
    company_id          TEXT NOT NULL,
    pros                TEXT,
    cons                TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

DROP TABLE IF EXISTS sectors;
CREATE TABLE sectors (
    row_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER,
    company_id          TEXT NOT NULL UNIQUE,
    broad_sector        TEXT NOT NULL,
    sub_sector          TEXT,
    index_weight_pct    REAL,
    market_cap_category TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

DROP TABLE IF EXISTS stock_prices;
CREATE TABLE stock_prices (
    row_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER,
    company_id          TEXT NOT NULL,
    price_date          TEXT NOT NULL,          -- ISO date, monthly granularity
    open_price          REAL,
    high_price          REAL,
    low_price           REAL,
    close_price         REAL,
    volume              INTEGER,
    adjusted_close      REAL,
    is_simulated        INTEGER DEFAULT 1,       -- flagged per project rules: SIMULATED dataset
    UNIQUE (company_id, price_date),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

DROP TABLE IF EXISTS peer_groups;
CREATE TABLE peer_groups (
    row_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER,
    peer_group_name     TEXT NOT NULL,
    company_id          TEXT NOT NULL,
    is_benchmark        INTEGER DEFAULT 0,
    UNIQUE (peer_group_name, company_id),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

-- Added in Sprint 3 (Day 15): the screener needs P/E, P/B, dividend yield,
-- and market cap thresholds, which live in market_cap.xlsx. Originally
-- deferred to Sprint 4 (valuation module) per the Sprint 1 schema note,
-- but the Sprint 3 screener spec requires these fields, so it's loaded now.
DROP TABLE IF EXISTS market_cap;
CREATE TABLE market_cap (
    row_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id               INTEGER,
    company_id              TEXT NOT NULL,
    year                    INTEGER NOT NULL,       -- plain calendar year, e.g. 2024
    market_cap_crore        REAL,
    enterprise_value_crore  REAL,
    pe_ratio                REAL,
    pb_ratio                REAL,
    ev_ebitda               REAL,
    dividend_yield_pct      REAL,
    UNIQUE (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);
CREATE INDEX idx_mc_company_year ON market_cap(company_id, year);

-- Indexes to support later sprints (screener, peer percentile, API)
CREATE INDEX idx_pl_company_year ON profitandloss(company_id, year);
CREATE INDEX idx_bs_company_year ON balancesheet(company_id, year);
CREATE INDEX idx_cf_company_year ON cashflow(company_id, year);
CREATE INDEX idx_sp_company_date ON stock_prices(company_id, price_date);
CREATE INDEX idx_sectors_broad ON sectors(broad_sector);
CREATE INDEX idx_peer_group_name ON peer_groups(peer_group_name);
