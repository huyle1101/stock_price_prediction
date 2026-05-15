-- init.sql
-- runs automatically on first postgres container start
-- creates all tables for the stock prediction pipeline

CREATE DATABASE airflow;

-- ── prices ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prices (
    date        TEXT        NOT NULL,
    symbol      TEXT        NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      REAL,
    source      TEXT,                           -- tcbs | ssi
    created_at  TIMESTAMP   DEFAULT NOW(),
    PRIMARY KEY (date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_prices_symbol ON prices (symbol);
CREATE INDEX IF NOT EXISTS idx_prices_date   ON prices (date);

-- ── macro ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS macro (
    date        TEXT        NOT NULL PRIMARY KEY,
    dxy         REAL,
    fed_rate    REAL,
    gold        REAL,
    oil         REAL,
    sp500       REAL,
    source      TEXT                            -- yfinance | fred
);

CREATE INDEX IF NOT EXISTS idx_macro_date ON macro (date);

-- ── predictions ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
    date                TEXT    NOT NULL,
    symbol              TEXT    NOT NULL,
    arimax_pred         REAL,                   -- predicted close from ARIMAX
    lstm_pred           REAL,                   -- predicted close from LSTM
    gru_pred            REAL,                   -- predicted close from GRU
    transformer_pred    REAL,                   -- predicted close from Transformer
    ridge_pred          REAL,                   -- final blended prediction from Ridge
    confidence          REAL,                   -- Ridge confidence score 0.0 - 1.0
    created_at          TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_predictions_symbol ON predictions (symbol);
CREATE INDEX IF NOT EXISTS idx_predictions_date   ON predictions (date);

-- ── actuals ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS actuals (
    date            TEXT    NOT NULL,
    symbol          TEXT    NOT NULL,
    actual_close    REAL,                       -- fetched after market close 15:30
    filled_at       TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_actuals_symbol ON actuals (symbol);
CREATE INDEX IF NOT EXISTS idx_actuals_date   ON actuals (date);

-- ── model_versions ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_versions (
    version_id      TEXT        NOT NULL PRIMARY KEY,   -- e.g. arimax_VNM_20260521
    model_type      TEXT,                               -- arimax | lstm | gru | transformer | ridge
    ticker          TEXT,                               -- VNM | FPT | ... | ALL (for Ridge)
    train_end_date  TEXT,
    trained_at      TIMESTAMP   DEFAULT NOW(),
    mae             REAL,
    da              REAL,                               -- directional accuracy
    r2              REAL,
    is_active       SMALLINT    DEFAULT 1               -- 1 = currently used in production
);
