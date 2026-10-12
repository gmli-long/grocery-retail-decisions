"""
Challenge 01 — "Spaghetti to Schema"
ETL pipeline: parse the denormalized flat files, clean & coerce types, resolve
the 3NF relational model, enforce key constraints & referential integrity, and
load into PostgreSQL (or SQLite as a dependency-free fallback for local runs).

Usage:
    python load_data.py                          # auto backend (postgres if available, else sqlite)
    python load_data.py --target postgres        # require PostgreSQL (DATABASE_URL env)
    python load_data.py --target sqlite --sqlite-path data/challenge_01.sqlite
    python load_data.py --data-dir <path>        # override source CSV directory

The loader logs, for every table, the source row count and the loaded row
count, and writes any rejected / anomalous rows to reports/etl/rejected_*.csv.
"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = (r"C:\Users\21597\.cache\kagglehub\competitions"
                    r"\challenge-01-spaghetti-schema-2026\Callenge Data Sets\Challenge_01_data_V1_0")

# DateTime formats differ per sales quarter (documented in readme.txt)
DT_FORMATS = {
    "q1": "%m/%d/%Y %H:%M",
    "q2": "%Y-%m-%d %H:%M",
    "q3": "%d-%b-%Y %H:%M",
    "q4": "%m/%d/%y %I:%M %p",
}

VALID_PROMO_TYPE = {"PCT_OFF", "LOYALTY_PCT", "BOGO50"}
VALID_TENDER = {"Cash", "Credit", "SNAP"}
VALID_SEGMENT = {"Member", "Non-Member"}


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("etl")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


class RejectionLog:
    """Accumulates rows that fail constraints, keyed by (table, reason)."""

    def __init__(self):
        self.rows = []

    def add(self, table, reason, df):
        if df is not None and len(df) > 0:
            for _, r in df.iterrows():
                self.rows.append({"table": table, "reason": reason, "sample": dict(r)})

    def is_empty(self):
        return len(self.rows) == 0

    def to_frame(self):
        return pd.DataFrame(self.rows)


# --------------------------------------------------------------------------- #
#  TRANSFORM: flat files -> normalized, typed, validated DataFrames
# --------------------------------------------------------------------------- #
def transform(data_dir: Path, rej: RejectionLog):
    tables = {}

    # ---- 1) products + its lookup dimensions --------------------------------
    p = pd.read_csv(data_dir / "products_2024.csv", dtype=str, keep_default_na=False)
    log.info("products source rows: %d", len(p))

    departments = (p[["department_name"]].drop_duplicates().sort_values("department_name")
                   .reset_index(drop=True))
    departments["department_id"] = np.arange(1, len(departments) + 1, dtype=np.int16)
    dept_id = dict(zip(departments["department_name"], departments["department_id"]))

    categories = (p[["category_name", "department_name"]].drop_duplicates()
                  .sort_values(["department_name", "category_name"]).reset_index(drop=True))
    categories["department_id"] = categories["department_name"].map(dept_id)
    categories["category_id"] = np.arange(1, len(categories) + 1, dtype=np.int16)
    cat_key = dict(zip(zip(categories["category_name"], categories["department_id"]),
                       categories["category_id"]))

    brands = (p[["brand"]].drop_duplicates().sort_values("brand").reset_index(drop=True))
    brands.columns = ["brand_name"]
    brands["brand_id"] = np.arange(1, len(brands) + 1, dtype=np.int16)
    brand_id = dict(zip(brands["brand_name"], brands["brand_id"]))

    vendors = (p[["vendor_name", "vendor_phone"]].drop_duplicates()
               .sort_values("vendor_name").reset_index(drop=True))
    vendors["vendor_id"] = np.arange(1, len(vendors) + 1, dtype=np.int16)
    vendor_id = dict(zip(vendors["vendor_name"], vendors["vendor_id"]))

    num_ok = _num(p["regular_price"]).notna() & _num(p["unit_cost"]).notna()
    rej.add("products", "non-numeric price/cost", p[~num_ok])

    products = pd.DataFrame({
        "product_upc": p["product_upc"],
        "product_name": p["product_name"],
        "brand_id": p["brand"].map(brand_id),
        "category_id": [cat_key[(c, dept_id[d])] for c, d in
                        zip(p["category_name"], p["department_name"])],
        "size": p["size"], "unit": p["unit"],
        "vendor_id": p["vendor_name"].map(vendor_id),
        "regular_price": _num(p["regular_price"]).round(2),
        "unit_cost": _num(p["unit_cost"]).round(2),
        "pack_size": _num(p["pack_size"]).astype("Int64"),
    })
    rej.add("products", "duplicate upc", products[products.duplicated("product_upc")])
    products = products.drop_duplicates("product_upc", keep="first")

    tables["departments"] = departments[["department_id", "department_name"]]
    tables["categories"] = categories[["category_id", "category_name", "department_id"]]
    tables["brands"] = brands[["brand_id", "brand_name"]]
    tables["vendors"] = vendors[["vendor_id", "vendor_name", "vendor_phone"]]
    tables["products"] = products.reset_index(drop=True)
    log.info("normalized: departments=%d categories=%d brands=%d vendors=%d products=%d",
             len(departments), len(categories), len(brands), len(vendors), len(products))

    # ---- 2) promotions ------------------------------------------------------
    pr = pd.read_csv(data_dir / "promotions_2024.csv", dtype=str, keep_default_na=False)
    log.info("promotions source rows: %d", len(pr))
    promo = pd.DataFrame({
        "promo_id": pr["promo_id"],
        "product_upc": pr["product_upc"],
        "promo_type": pr["promo_type"],
        "discount_percent": _num(pr["discount_percent"]).round(2),
        "start_date": pd.to_datetime(pr["start_date"], errors="coerce"),
        "end_date": pd.to_datetime(pr["end_date"], errors="coerce"),
    })
    bad_type = ~promo["promo_type"].isin(VALID_PROMO_TYPE)
    bad_disc = promo["discount_percent"].isna() | (promo["discount_percent"] < 0) | (promo["discount_percent"] > 100)
    bad_dates = promo["start_date"].isna() | promo["end_date"].isna() | (promo["end_date"] < promo["start_date"])
    orphan = ~promo["product_upc"].isin(set(products["product_upc"]))
    dup = promo.duplicated("promo_id")
    rej.add("promotions", "invalid promo_type", promo[bad_type])
    rej.add("promotions", "discount out of [0,100]", promo[bad_disc])
    rej.add("promotions", "date range invalid", promo[bad_dates])
    rej.add("promotions", "product_upc orphan", promo[orphan])
    rej.add("promotions", "duplicate promo_id", promo[dup])
    promo = promo[~(bad_type | bad_disc | bad_dates | orphan | dup)]
    tables["promotions"] = promo.reset_index(drop=True)

    # ---- 3) stores + inventory snapshots ------------------------------------
    inv = pd.read_csv(data_dir / "inventory_snapshots_2024.csv", dtype=str, keep_default_na=False)
    log.info("inventory source rows: %d", len(inv))
    stores = (inv[["store_id", "store_name", "store_address", "store_city",
                   "store_state", "store_zip"]].drop_duplicates()
              .sort_values("store_id").reset_index(drop=True))
    stores["store_id"] = _num(stores["store_id"]).astype("int16")
    tables["stores"] = stores

    snap = pd.DataFrame({
        "snapshot_date": pd.to_datetime(inv["snapshot_date"], errors="coerce"),
        "store_id": _num(inv["store_id"]).astype("int16"),
        "product_upc": inv["product_upc"],
        "on_hand_qty": _num(inv["on_hand_qty"]).astype("int32"),
    })
    bad_oh = snap["on_hand_qty"].isna() | (snap["on_hand_qty"] < 0)
    orphan = ~snap["product_upc"].isin(set(products["product_upc"]))
    bad_date = snap["snapshot_date"].isna()
    dup = snap.duplicated(["snapshot_date", "store_id", "product_upc"])
    rej.add("inventory_snapshots", "on_hand negative/null", snap[bad_oh])
    rej.add("inventory_snapshots", "product/store orphan", snap[orphan])
    rej.add("inventory_snapshots", "bad date", snap[bad_date])
    rej.add("inventory_snapshots", "duplicate snapshot key", snap[dup])
    snap = snap[~(bad_oh | orphan | bad_date | dup)].reset_index(drop=True)
    snap["snapshot_id"] = np.arange(1, len(snap) + 1, dtype=np.int64)
    tables["inventory_snapshots"] = snap

    # ---- 4) sales -> cashiers, receipts, line_items -------------------------
    parts = []
    for q, fmt in DT_FORMATS.items():
        df = pd.read_csv(data_dir / f"sales_2024_{q}.csv", dtype=str, keep_default_na=False)
        df["_dt"] = pd.to_datetime(df["sale_datetime"], format=fmt, errors="coerce")
        df["_q"] = q
        parts.append(df)
    sales = pd.concat(parts, ignore_index=True)
    log.info("sales source rows: %d", len(sales))
    rej.add("sales", "unparseable datetime", sales[sales["_dt"].isna()])

    cashiers = (sales[["cashier_name"]].drop_duplicates().sort_values("cashier_name")
                .reset_index(drop=True))
    cashiers["cashier_id"] = np.arange(1, len(cashiers) + 1, dtype=np.int16)
    cashier_id = dict(zip(cashiers["cashier_name"], cashiers["cashier_id"]))
    tables["cashiers"] = cashiers[["cashier_id", "cashier_name"]]

    receipts = (sales.groupby("receipt_id", as_index=False)
                .agg(store_id=("store_id", "first"),
                     cashier_name=("cashier_name", "first"),
                     sale_datetime=("_dt", "first"),
                     tender_type=("tender_type", "first"),
                     customer_segment=("customer_segment", "first")))
    receipts["store_id"] = _num(receipts["store_id"]).astype("int16")
    receipts["cashier_id"] = receipts["cashier_name"].map(cashier_id)
    ok = (receipts["tender_type"].isin(VALID_TENDER)
          & receipts["customer_segment"].isin(VALID_SEGMENT)
          & receipts["store_id"].isin(set(stores["store_id"]))
          & receipts["cashier_id"].notna()
          & receipts["sale_datetime"].notna())
    rej.add("receipts", "invalid tender/segment/store/cashier", receipts[~ok])
    receipts = receipts[ok].reset_index(drop=True)
    tables["receipts"] = receipts[["receipt_id", "store_id", "cashier_id",
                                   "sale_datetime", "tender_type", "customer_segment"]]

    li = pd.DataFrame({
        "receipt_id": sales["receipt_id"],
        "line_number": _num(sales["line_number"]).astype("int16"),
        "product_upc": sales["product_upc"],
        "quantity": _num(sales["quantity"]).astype("int16"),
        "promo_id": sales["promo_id"].replace("", None),
        "unit_price_effective": _num(sales["unit_price_effective"]).round(2),
        "line_subtotal": _num(sales["line_subtotal"]).round(2),
        "tax_amount": _num(sales["tax_amount"]).round(2),
    })
    # promo_id present must exist in promotions; empty/NULL promo is full price
    promo_set = set(tables["promotions"]["promo_id"])
    bad_promo = li["promo_id"].notna() & ~li["promo_id"].isin(promo_set)
    bad_qty = li["quantity"].isna() | (li["quantity"] <= 0)
    bad_upc = ~li["product_upc"].isin(set(products["product_upc"]))
    bad_rcpt = ~li["receipt_id"].isin(set(receipts["receipt_id"]))
    # numeric sanity: line_subtotal == unit_price_effective * quantity
    calc = (li["unit_price_effective"] * li["quantity"]).round(2)
    bad_calc = (li["line_subtotal"] - calc).abs() > 0.02
    dup = li.duplicated(["receipt_id", "line_number"])
    rej.add("line_items", "promo_id orphan", li[bad_promo])
    rej.add("line_items", "quantity <= 0", li[bad_qty])
    rej.add("line_items", "product orphan", li[bad_upc])
    rej.add("line_items", "receipt orphan", li[bad_rcpt])
    rej.add("line_items", "subtotal != price*qty", li[bad_calc])
    rej.add("line_items", "duplicate (receipt, line)", li[dup])
    keep = ~(bad_promo | bad_qty | bad_upc | bad_rcpt | bad_calc | dup)
    li = li[keep].reset_index(drop=True)
    li["line_item_id"] = np.arange(1, len(li) + 1, dtype=np.int64)
    tables["line_items"] = li

    return tables


# --------------------------------------------------------------------------- #
#  LOAD backends
# --------------------------------------------------------------------------- #
class PostgresBackend:
    name = "postgresql"

    def __init__(self, url):
        import psycopg2
        self.conn = psycopg2.connect(url)
        self.conn.autocommit = False

    def execute_script(self, sql_path):
        with self.conn.cursor() as cur:
            cur.execute(Path(sql_path).read_text(encoding="utf-8"))

    def load(self, table, df):
        cols = list(df.columns)
        placeholders = ",".join(["%s"] * len(cols))
        sql = f'INSERT INTO {table} ({",".join(cols)}) VALUES ({placeholders})'
        rows = [tuple(None if (isinstance(v, float) and np.isnan(v)) else v
                      for v in r) for r in df.itertuples(index=False, name=None)]
        with self.conn.cursor() as cur:
            cur.executemany(sql, rows)

    def count(self, table):
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            return cur.fetchone()[0]

    def commit(self):
        self.conn.commit()


class SQLiteBackend:
    name = "sqlite"

    def __init__(self, path):
        import sqlite3
        self.conn = sqlite3.connect(str(path))
        self.conn.execute("PRAGMA foreign_keys=ON")

    def execute_script(self, sql_path):
        # SQLite uses a reduced schema (same model, sqlite-flavoured types)
        self.conn.executescript(_SQLITE_DDL)

    def load(self, table, df):
        import datetime as _dt
        cols = list(df.columns)
        placeholders = ",".join(["?"] * len(cols))
        sql = f'INSERT INTO {table} ({",".join(cols)}) VALUES ({placeholders})'

        def norm(v):
            if v is None:
                return None
            if isinstance(v, (pd.Timestamp, _dt.datetime)):
                return v.isoformat(sep=" ")
            if isinstance(v, _dt.date):
                return v.isoformat()
            if isinstance(v, (np.integer,)):
                return int(v)
            if isinstance(v, (np.floating, float)):
                return float(v)
            if isinstance(v, float) and np.isnan(v):
                return None
            return v

        rows = [tuple(norm(v) for v in r) for r in df.itertuples(index=False, name=None)]
        self.conn.executemany(sql, rows)

    def count(self, table):
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def commit(self):
        self.conn.commit()


# Minimal SQLite DDL mirroring sql/ddl.sql (sqlite-flavoured types).
_SQLITE_DDL = """
DROP TABLE IF EXISTS inventory_snapshots; DROP TABLE IF EXISTS line_items;
DROP TABLE IF EXISTS receipts; DROP TABLE IF EXISTS promotions;
DROP TABLE IF EXISTS products; DROP TABLE IF EXISTS cashiers; DROP TABLE IF EXISTS stores;
DROP TABLE IF EXISTS vendors; DROP TABLE IF EXISTS brands; DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS departments;

CREATE TABLE departments (department_id INTEGER PRIMARY KEY, department_name TEXT NOT NULL UNIQUE);
CREATE TABLE categories (category_id INTEGER PRIMARY KEY, category_name TEXT NOT NULL,
  department_id INTEGER NOT NULL REFERENCES departments(department_id));
CREATE TABLE brands (brand_id INTEGER PRIMARY KEY, brand_name TEXT NOT NULL UNIQUE);
CREATE TABLE vendors (vendor_id INTEGER PRIMARY KEY, vendor_name TEXT NOT NULL UNIQUE, vendor_phone TEXT);
CREATE TABLE stores (store_id INTEGER PRIMARY KEY, store_name TEXT NOT NULL, store_address TEXT,
  store_city TEXT, store_state TEXT, store_zip TEXT);
CREATE TABLE cashiers (cashier_id INTEGER PRIMARY KEY, cashier_name TEXT NOT NULL UNIQUE);
CREATE TABLE products (product_upc TEXT PRIMARY KEY, product_name TEXT NOT NULL,
  brand_id INTEGER NOT NULL REFERENCES brands(brand_id), category_id INTEGER NOT NULL REFERENCES categories(category_id),
  size TEXT, unit TEXT, vendor_id INTEGER NOT NULL REFERENCES vendors(vendor_id),
  regular_price REAL NOT NULL, unit_cost REAL NOT NULL, pack_size INTEGER);
CREATE TABLE promotions (promo_id TEXT PRIMARY KEY, product_upc TEXT NOT NULL REFERENCES products(product_upc),
  promo_type TEXT NOT NULL, discount_percent REAL NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL);
CREATE TABLE receipts (receipt_id TEXT PRIMARY KEY, store_id INTEGER NOT NULL REFERENCES stores(store_id),
  cashier_id INTEGER NOT NULL REFERENCES cashiers(cashier_id), sale_datetime TEXT NOT NULL,
  tender_type TEXT NOT NULL, customer_segment TEXT NOT NULL);
CREATE TABLE line_items (line_item_id INTEGER PRIMARY KEY, receipt_id TEXT NOT NULL REFERENCES receipts(receipt_id),
  line_number INTEGER NOT NULL, product_upc TEXT NOT NULL REFERENCES products(product_upc),
  quantity INTEGER NOT NULL, promo_id TEXT REFERENCES promotions(promo_id),
  unit_price_effective REAL NOT NULL, line_subtotal REAL NOT NULL, tax_amount REAL NOT NULL);
CREATE TABLE inventory_snapshots (snapshot_id INTEGER PRIMARY KEY, snapshot_date TEXT NOT NULL,
  store_id INTEGER NOT NULL REFERENCES stores(store_id), product_upc TEXT NOT NULL REFERENCES products(product_upc),
  on_hand_qty INTEGER NOT NULL);
"""

# Order tables so parents load before children (FK constraints active).
LOAD_ORDER = ["departments", "categories", "brands", "vendors", "stores", "cashiers",
              "products", "promotions", "receipts", "line_items", "inventory_snapshots"]


def run(args):
    data_dir = Path(args.data_dir).expanduser()
    rej = RejectionLog()

    t0 = time.time()
    tables = transform(data_dir, rej)

    # ---- wire up backend ----
    if args.target == "postgres" or (args.target == "auto" and _pg_available()):
        url = os.environ.get("DATABASE_URL")
        if not url:
            log.error("--target postgres requires DATABASE_URL to be set (e.g. postgresql://user:pass@host:5432/db)")
            sys.exit(2)
        backend = PostgresBackend(url)
    else:
        Path(args.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        backend = SQLiteBackend(args.sqlite_path)
    log.info("backend: %s", backend.name)

    # Create schema (PostgreSQL runs the canonical DDL; SQLite runs the mirror)
    backend.execute_script(BASE_DIR / "sql" / "ddl.sql")

    # ---- load in dependency order, log before/after counts ----
    log.info("-" * 62)
    for table_name in LOAD_ORDER:
        df = tables[table_name]
        backend.load(table_name, df)
        loaded = backend.count(table_name)
        log.info("%-20s source_rows=%-6d loaded=%d", table_name, len(df), loaded)

    backend.commit()

    # ---- write rejected rows (if any) ----
    rej_frame = rej.to_frame()
    rej_dir = BASE_DIR / "reports" / "etl"
    rej_dir.mkdir(parents=True, exist_ok=True)
    if not rej.is_empty():
        rej_frame.to_csv(rej_dir / "rejected_rows.csv", index=False)
        log.warning("REJECTED rows: %d -> reports/etl/rejected_rows.csv", len(rej_frame))
    else:
        (rej_dir / "rejected_rows.csv").write_text("table,reason,sample\n", encoding="utf-8")
        log.info("REJECTED rows: 0 (all constraints satisfied)")

    # ---- summary ----
    log.info("-" * 62)
    log.info("ETL complete in %.2fs. Fact rows loaded:", time.time() - t0)
    log.info("  receipts=%d  line_items=%d  inventory_snapshots=%d",
             backend.count("receipts"), backend.count("line_items"),
             backend.count("inventory_snapshots"))
    if backend.name == "sqlite":
        log.info("SQLite database written to %s", args.sqlite_path)


def _pg_available():
    try:
        import psycopg2  # noqa: F401
        return True
    except ImportError:
        return False


def main(argv=None):
    global log
    ap = argparse.ArgumentParser(description="Challenge 01 ETL pipeline")
    ap.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    ap.add_argument("--target", choices=["auto", "postgres", "sqlite"], default="auto")
    ap.add_argument("--sqlite-path", default=str(BASE_DIR / "data" / "challenge_01.sqlite"))
    ap.add_argument("--log", default=str(BASE_DIR / "reports" / "etl" / "etl.log"))
    args = ap.parse_args(argv)
    log = setup_logging(Path(args.log))
    run(args)


if __name__ == "__main__":
    main()