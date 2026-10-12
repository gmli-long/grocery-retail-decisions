"""Challenge 02 — dataset integrity checker.

Standalone CLI: run it against either the raw or the cleaned CSV directory to
get the same battery of checks. It is designed to *demonstrate* the repair:
raw data fails many checks (non-zero exit), cleaned data passes all (zero exit).

Usage:
    python src/evaluation.py --data data/raw      # expected to fail
    python src/evaluation.py --data data/clean    # expected to pass
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import helper_utils as hu


def _num(x):
    return pd.to_numeric(x, errors="coerce")


def run_checks(data_dir):
    """Return (checks, num_failed) where checks is a list of (name, ok, detail)."""
    dfs = hu.load_raw(data_dir)
    sales = dfs["sales"]
    products, vendors, stores, categories = (dfs["products"], dfs["vendors"],
                                             dfs["stores"], dfs["categories"])

    qty = _num(sales["qty"]); price = _num(sales["unit_price"])
    amt = _num(sales["line_amount"]); dates = pd.to_datetime(sales["txn_date"], errors="coerce")

    valid_store = set(stores["store_id"])
    valid_product = set(products["product_id"])
    valid_category = set(categories["category_id"])
    valid_vendor = set(vendors["vendor_id"])

    checks = []
    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    # --- primary-key uniqueness -------------------------------------------------
    add("products PK unique", not products["product_id"].duplicated().any(),
        f"{int(products['product_id'].duplicated().sum())} dup ids")
    add("vendors PK unique", not vendors["vendor_id"].duplicated().any())
    add("stores PK unique", not stores["store_id"].duplicated().any())
    add("categories PK unique", not categories["category_id"].duplicated().any())
    add("txn_id unique", not sales["txn_id"].duplicated().any(),
        f"{int(sales['txn_id'].duplicated().sum())} dup txn_id")

    # --- completeness ------------------------------------------------------------
    add("no missing txn_date", (sales["txn_date"] != "").all(),
        f"{(sales['txn_date'] == '').sum()} empty")
    add("no missing qty", qty.notna().all(), f"{int(qty.isna().sum())} null")
    add("no missing unit_price", price.notna().all(), f"{int(price.isna().sum())} null")
    add("no missing line_amount", amt.notna().all(), f"{int(amt.isna().sum())} null")

    # --- referential integrity ---------------------------------------------------
    add("store_id references valid", sales["store_id"].isin(valid_store).all(),
        f"orphans: {sorted(set(sales['store_id']) - valid_store)}")
    add("product_id references valid", sales["product_id"].isin(valid_product).all(),
        f"orphans: {sorted(set(sales['product_id']) - valid_product)}")
    add("products.category_id valid", products["category_id"].isin(valid_category).all())
    add("products.vendor_id valid", products["vendor_id"].isin(valid_vendor).all())

    # --- value sanity / outliers -------------------------------------------------
    add("qty in [1,4]", qty.dropna().isin([1, 2, 3, 4]).all(),
        f"out-of-range: {sorted(set(qty.dropna()) - {1,2,3,4})}")
    add("unit_price > 0", (price > 0).all())
    add("line_amount consistent (=qty*price)",
        (amt - qty * price).abs().max() < 1e-6,
        f"max abs diff = {(amt - qty*price).abs().max():.4g}")

    # --- pattern / drift ----------------------------------------------------------
    add("txn_date all parseable", (sales["txn_date"] == "").sum() == dates.isna().sum()
        and (dates.notna() | (sales["txn_date"] == "")).all(),
        "unparseable non-empty dates present" if ((sales["txn_date"] != "") & dates.isna()).any()
        else "")
    dd = dates.dropna()
    n_days = dd.dt.normalize().nunique()
    day_span = (dd.max() - dd.min()).days + 1 if len(dd) else 0
    add("no calendar-day gaps", n_days == day_span,
        f"{n_days} distinct dates over {day_span}-day span")

    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/clean")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent.parent
    data_dir = (Path(args.data) if Path(args.data).is_absolute()
                else here / args.data)

    checks = run_checks(data_dir)
    n_fail = sum(1 for _, ok, _ in checks if not ok)

    w = max(len(n) for n, _, _ in checks)
    print(f"Integrity check on: {data_dir}\n" + "=" * (w + 22))
    print(f"{'check':<{w}}  {'status':<6}  detail")
    print("-" * (w + 22))
    for name, ok, detail in checks:
        print(f"{name:<{w}}  {'PASS' if ok else 'FAIL':<6}  {detail}")

    print("=" * (w + 22))
    print(f"{len(checks) - n_fail}/{len(checks)} checks passed")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())