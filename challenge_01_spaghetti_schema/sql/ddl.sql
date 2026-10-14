-- ============================================================================
--  Challenge 01 — "Spaghetti to Schema"
--  Normalized PostgreSQL schema (3NF) for Greenway Grocers retail data (2024)
--
--  Design principles
--  -----------------
--  1. Every non-key attribute depends on "the key, the whole key, and nothing
--     but the key" (Boyce-Codd normal form). Descriptive attributes that were
--     flattened onto every order line (store addresses, vendor phone, brand,
--     category, size/unit) are pulled out into their owning dimension.
--  2. Derived/duplicated columns are dropped where they violate 3NF and can be
--     cheaply recomputed:
--       * weekend_flag   -> derived from sale_datetime (EXTRACT(DOW ...))
--       * inventory_snapshots.unit_cost / inventory_cost_value
--                        -> derivable from products.unit_cost * on_hand_qty
--  3. Natural codes (store_id, product_upc, promo_id, receipt_id) are kept as
--     small lookup-friendly keys instead of synthetic surrogates, because they
--     are proven unique, stable, and make fact tables human-readable / re-loadable.
--  4. Strict 3NF is relaxed in exactly one deliberate place for analytic
--     efficiency: regular_price / unit_cost are stored ON products as the
--     "current baseline", and unit_price_effective is stored ON line_items as
--     the price actually charged (which depends on an applied promotion).
--     See docs/architecture.md for the full trade-off rationale.
-- ============================================================================

BEGIN;

-- Drop in reverse-dependency order so the script is idempotent (re-runnable).
DROP TABLE IF EXISTS inventory_snapshots CASCADE;
DROP TABLE IF EXISTS line_items        CASCADE;
DROP TABLE IF EXISTS receipts          CASCADE;
DROP TABLE IF EXISTS promotions        CASCADE;
DROP TABLE IF EXISTS products          CASCADE;
DROP TABLE IF EXISTS cashiers          CASCADE;
DROP TABLE IF EXISTS stores            CASCADE;
DROP TABLE IF EXISTS vendors           CASCADE;
DROP TABLE IF EXISTS brands            CASCADE;
DROP TABLE IF EXISTS categories        CASCADE;
DROP TABLE IF EXISTS departments       CASCADE;

-- ---------------------------------------------------------------------------
-- DIMENSIONS
-- ---------------------------------------------------------------------------

-- Surrogate ids for dimensions are plain integers assigned deterministically
-- by the loader (scripts/load_data.py); this keeps the DDL and the ETL in
-- lockstep and makes the whole pipeline re-runnable & idempotent.

-- 8 product departments (Produce, Grocery, Dairy, ...)
CREATE TABLE departments (
    department_id   SMALLINT PRIMARY KEY,
    department_name TEXT     NOT NULL UNIQUE
);

-- 60 leaf categories, each belongs to exactly one department
CREATE TABLE categories (
    category_id    SMALLINT PRIMARY KEY,
    category_name  TEXT     NOT NULL,
    department_id  SMALLINT NOT NULL REFERENCES departments(department_id),
    UNIQUE (category_name, department_id)
);

-- 21 brands (a brand may span several categories)
CREATE TABLE brands (
    brand_id   SMALLINT PRIMARY KEY,
    brand_name TEXT     NOT NULL UNIQUE
);

-- 9 wholesale vendors (each carries a single service phone in the source)
CREATE TABLE vendors (
    vendor_id    SMALLINT PRIMARY KEY,
    vendor_name  TEXT     NOT NULL UNIQUE,
    vendor_phone TEXT
);

-- 3 physical stores; store_id is a stable natural key
CREATE TABLE stores (
    store_id      SMALLINT PRIMARY KEY,
    store_name    TEXT     NOT NULL,
    store_address TEXT,
    store_city    TEXT,
    store_state   CHAR(2),
    store_zip     TEXT
);

-- 8 cashiers (low-cardinality repeated string -> own dimension)
CREATE TABLE cashiers (
    cashier_id   SMALLINT PRIMARY KEY,
    cashier_name TEXT     NOT NULL UNIQUE
);

-- 60 products. NOTE: the source "category" was effectively 1:1 with product,
-- but we keep the department -> category -> product hierarchy because it is
-- the correct generalization and resists new products later.
CREATE TABLE products (
    product_upc     VARCHAR(14)   PRIMARY KEY,           -- 12-digit UPC kept as code
    product_name    TEXT          NOT NULL,
    brand_id        SMALLINT      NOT NULL REFERENCES brands(brand_id),
    category_id     SMALLINT      NOT NULL REFERENCES categories(category_id),
    size            TEXT,                                 -- human label ("16 oz", "1 lb")
    unit            TEXT,                                 -- "oz", "lb", "gal", "ct", "each"
    vendor_id       SMALLINT      NOT NULL REFERENCES vendors(vendor_id),
    regular_price   NUMERIC(10,2) NOT NULL CHECK (regular_price >= 0),  -- baseline shelf price
    unit_cost       NUMERIC(10,2) NOT NULL CHECK (unit_cost     >= 0),  -- baseline unit cost
    pack_size       SMALLINT      CHECK (pack_size > 0)
);

-- 530 weekly, product-level promotions
CREATE TABLE promotions (
    promo_id         VARCHAR(16)   PRIMARY KEY,
    product_upc      VARCHAR(14)   NOT NULL REFERENCES products(product_upc),
    promo_type       TEXT          NOT NULL
                     CHECK (promo_type IN ('PCT_OFF','LOYALTY_PCT','BOGO50')),
    discount_percent NUMERIC(5,2)  NOT NULL CHECK (discount_percent BETWEEN 0 AND 100),
    start_date       DATE          NOT NULL,
    end_date         DATE          NOT NULL,
    CHECK (end_date >= start_date)
);

-- ---------------------------------------------------------------------------
-- FACTS
-- ---------------------------------------------------------------------------

-- Transaction header (one row per receipt). tender_type / customer_segment /
-- cashier / store are constant within a receipt (verified in profiling), so
-- they live here rather than being repeated on every line.
CREATE TABLE receipts (
    receipt_id      VARCHAR(32) PRIMARY KEY,
    store_id        SMALLINT    NOT NULL REFERENCES stores(store_id),
    cashier_id      SMALLINT    NOT NULL REFERENCES cashiers(cashier_id),
    sale_datetime   TIMESTAMP   NOT NULL,
    tender_type     TEXT        NOT NULL CHECK (tender_type IN ('Cash','Credit','SNAP')),
    customer_segment TEXT       NOT NULL CHECK (customer_segment IN ('Member','Non-Member'))
);

-- Transaction detail (one row per sold line). The price actually charged
-- (unit_price_effective) borrows from an optional promotion and is therefore a
-- line-level fact. line_number continues the source's line-in-receipt identity.
CREATE TABLE line_items (
    line_item_id         BIGINT       PRIMARY KEY,
    receipt_id           VARCHAR(32)  NOT NULL REFERENCES receipts(receipt_id),
    line_number          SMALLINT     NOT NULL,
    product_upc          VARCHAR(14)  NOT NULL REFERENCES products(product_upc),
    quantity             SMALLINT     NOT NULL CHECK (quantity > 0),
    promo_id             VARCHAR(16)  REFERENCES promotions(promo_id),   -- NULL = full price
    unit_price_effective NUMERIC(10,2) NOT NULL CHECK (unit_price_effective >= 0),
    line_subtotal        NUMERIC(10,2) NOT NULL CHECK (line_subtotal >= 0),
    tax_amount           NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    UNIQUE (receipt_id, line_number)
);

-- Monthly on-hand inventory. unit_cost / inventory_cost_value are deliberately
-- NOT stored: they were string-identical (byte-for-byte) to products.unit_cost in the source, so
-- keeping them here would store a duplicate that can drift and contradict the
-- product master. (If historical cost were needed, promote products.unit_cost
-- into a slowly-changing cost table — see docs/architecture.md.)
CREATE TABLE inventory_snapshots (
    snapshot_id   BIGINT      PRIMARY KEY,
    snapshot_date DATE        NOT NULL,
    store_id      SMALLINT    NOT NULL REFERENCES stores(store_id),
    product_upc   VARCHAR(14) NOT NULL REFERENCES products(product_upc),
    on_hand_qty   INT         NOT NULL CHECK (on_hand_qty >= 0),
    UNIQUE (snapshot_date, store_id, product_upc)
);

COMMIT;