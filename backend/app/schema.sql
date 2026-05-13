-- ============================================================
-- Virtual Stock Market — Database Schema
-- SQLite with WAL mode (configured via PRAGMA at connection)
-- ============================================================

-- ── Relational Tables (Low Mutation) ──

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    balance         REAL    NOT NULL DEFAULT 10000.0,
    total_earned    REAL    NOT NULL DEFAULT 0.0,
    total_taxed     REAL    NOT NULL DEFAULT 0.0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    last_active     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

CREATE TABLE IF NOT EXISTS assets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    sector      TEXT    NOT NULL,
    base_price  REAL    NOT NULL,
    mu          REAL    NOT NULL DEFAULT 0.05,
    sigma       REAL    NOT NULL DEFAULT 0.20,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_assets_symbol ON assets(symbol);
CREATE INDEX IF NOT EXISTS idx_assets_sector ON assets(sector);

CREATE TABLE IF NOT EXISTS asset_prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id    INTEGER NOT NULL REFERENCES assets(id),
    timestamp   REAL    NOT NULL,
    open        REAL    NOT NULL,
    high        REAL    NOT NULL,
    low         REAL    NOT NULL,
    close       REAL    NOT NULL,
    volume      REAL    NOT NULL DEFAULT 0.0,
    UNIQUE(asset_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_prices_asset_time ON asset_prices(asset_id, timestamp);

-- ── Ledger Tables (High Mutation) ──

CREATE TABLE IF NOT EXISTS portfolios (
    user_id     INTEGER NOT NULL REFERENCES users(id),
    asset_id    INTEGER NOT NULL REFERENCES assets(id),
    quantity    INTEGER NOT NULL DEFAULT 0,
    avg_cost    REAL    NOT NULL DEFAULT 0.0,
    PRIMARY KEY (user_id, asset_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    asset_id        INTEGER NOT NULL REFERENCES assets(id),
    side            TEXT    NOT NULL CHECK(side IN ('buy', 'sell')),
    order_type      TEXT    NOT NULL CHECK(order_type IN ('market', 'limit')),
    quantity        INTEGER NOT NULL CHECK(quantity > 0),
    limit_price     REAL,
    filled_quantity INTEGER NOT NULL DEFAULT 0,
    status          TEXT    NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'filled', 'partial', 'cancelled')),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, status);
CREATE INDEX IF NOT EXISTS idx_orders_asset_side ON orders(asset_id, side, status);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id    INTEGER NOT NULL REFERENCES users(id),
    seller_id   INTEGER NOT NULL REFERENCES users(id),
    asset_id    INTEGER NOT NULL REFERENCES assets(id),
    quantity    INTEGER NOT NULL,
    price       REAL    NOT NULL,
    tax         REAL    NOT NULL DEFAULT 0.0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transactions_buyer ON transactions(buyer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_seller ON transactions(seller_id);
CREATE INDEX IF NOT EXISTS idx_transactions_asset ON transactions(asset_id, created_at);

CREATE TABLE IF NOT EXISTS ledger_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    entry_type      TEXT    NOT NULL CHECK(entry_type IN ('faucet', 'trade_credit', 'trade_debit', 'tax', 'transfer_in', 'transfer_out')),
    amount          REAL    NOT NULL,
    balance_after   REAL    NOT NULL,
    reference_id    INTEGER,
    description     TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ledger_user ON ledger_entries(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ledger_type ON ledger_entries(entry_type);

-- ── Task Tracking (Anti-Replay) ──

CREATE TABLE IF NOT EXISTS completed_tasks (
    task_id     TEXT    PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    tier        INTEGER NOT NULL,
    reward      REAL    NOT NULL,
    completed_at TEXT   NOT NULL DEFAULT (datetime('now'))
);

-- ── Economy Metrics (Aggregation Cache) ──

CREATE TABLE IF NOT EXISTS economy_snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp           TEXT    NOT NULL DEFAULT (datetime('now')),
    total_supply        REAL    NOT NULL,
    total_faucet        REAL    NOT NULL,
    total_sink          REAL    NOT NULL,
    sink_coverage_ratio REAL    NOT NULL,
    active_players      INTEGER NOT NULL
);

-- ── Seed Data: Initial Assets ──

INSERT OR IGNORE INTO assets (symbol, name, sector, base_price, mu, sigma) VALUES
    ('AAPL',  'Apple Inc.',            'technology',   180.00, 0.04, 0.18),
    ('MSFT',  'Microsoft Corp.',       'technology',   410.00, 0.05, 0.15),
    ('GOOGL', 'Alphabet Inc.',         'technology',   150.00, 0.04, 0.20),
    ('LNVGY', 'Lenovo Group Ltd.',     'technology',    15.00, 0.03, 0.25),
    ('WAEL',  'WAEL Exclusive Corp',   'exclusive',   1000.00, 0.50, 0.05),
    ('NOVA',  'Nova Technologies',     'technology',   150.00, 0.08, 0.30),
    ('AQUA',  'AquaPure Systems',      'utilities',     45.00, 0.03, 0.12),
    ('BOLT',  'Bolt Energy Corp',      'energy',        78.00, 0.06, 0.25),
    ('PEAK',  'Peak Healthcare',       'healthcare',   210.00, 0.05, 0.18),
    ('FLUX',  'Flux Financial Group',  'banking',      120.00, 0.07, 0.22);
