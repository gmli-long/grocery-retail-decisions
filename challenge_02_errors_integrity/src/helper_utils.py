"""Challenge 02 (Errors -> Integrity) — shared audit / repair / validation utilities.

Every function here is deliberately side-effect-free and deterministic. The
repair pipeline returns both the cleaned tables *and* a machine-readable
change log (list of dicts) so the whole lineage can be audited end-to-end.

Design principles
-----------------
1. Recover > impute: wherever a value can be *derived* from an invariant
   (e.g. line_amount == qty * unit_price, txn_id -> date/store block), we
   derive it exactly instead of guessing.
2. Statistical imputation is a last resort, used only for the single column
   (product_id) that is provably independent of all observed signals.
3. Deterministic: a fixed RNG seed, stable ordering, and tie-break rules make
   the result byte-for-byte reproducible.
"""
from pathlib import Path
import numpy as np
import pandas as pd

SCHEMA = {
    "products":   ["product_id", "sku", "name", "category_id", "vendor_id"],
    "vendors":    ["vendor_id", "name"],
    "stores":     ["store_id", "name", "city"],
    "categories": ["category_id", "name"],
    "sales":      ["txn_id", "txn_date", "store_id", "product_id",
                   "qty", "unit_price", "line_amount"],
}

CAT_PRODUCT = list(range(1, 21))   # valid product_id domain
CAT_STORE   = list(range(1, 6))    # valid store_id domain


def load_raw(data_dir):
    """Load the five CSVs as raw strings (empty string preserved, no auto-NA)."""
    data_dir = Path(data_dir)
    return {t: pd.read_csv(data_dir / f"{t}.csv", dtype=str, keep_default_na=False)
            for t in SCHEMA}


def _num(x):
    return pd.to_numeric(x, errors="coerce")


def audit(dfs):
    """Return a dict of quantified findings across all five tables.

    This is the "error audit" stage: it only *detects and counts* problems,
    it never mutates. `repair()` consumes these same rules.
    """
    sales = dfs["sales"]
    qty, price, amt = _num(sales["qty"]), _num(sales["unit_price"]), _num(sales["line_amount"])
    dates = pd.to_datetime(sales["txn_date"], errors="coerce")
    calc = (qty * price).round(6)

    findings = {
        # completeness
        "missing_txn_date":  (sales["txn_date"] == "").sum(),
        "missing_qty":       qty.isna().sum(),
        "missing_unit_price": price.isna().sum(),
        "missing_line_amount": amt.isna().sum(),
        # duplicates
        "dup_txn_id":        int(sales["txn_id"].duplicated().sum()),
        "dup_full_row":      int(sales.duplicated().sum()),
        # referential integrity (orphans)
        "store_orphans":     int((sales["store_id"] == "9999").sum()),
        "product_orphans":   int((sales["product_id"] == "9999").sum()),
        "category_orphans":  int((~sales["product_id"].isin([str(i) for i in CAT_PRODUCT] + ["9999"])).sum()),
        # value sanity
        "qty_outliers_ge1000": int((qty >= 1000).sum()),
        "qty_nonpositive":   int((qty <= 0).sum()),
        "price_nonpositive": int((price <= 0).sum()),
        "amount_mismatch":   int(((amt - calc).abs() > 1e-2).sum()),
        # date drift
        "unparseable_date":  int(((sales["txn_date"] != "") & dates.isna()).sum()),
        "date_min": str(dates.min()) if not dates.isna().all() else None,
        "date_max": str(dates.max()) if not dates.isna().all() else None,
        # reference-table hygiene
        "products_dup_id":   int(dfs["products"]["product_id"].duplicated().sum()),
        "vendors_dup_id":    int(dfs["vendors"]["vendor_id"].duplicated().sum()),
        "stores_dup_id":     int(dfs["stores"]["store_id"].duplicated().sum()),
        "categories_dup_id": int(dfs["categories"]["category_id"].duplicated().sum()),
        "category_name_inconsistent": int((dfs["categories"]["name"] !=
                                           ["Category_" + str(i) for i in dfs["categories"]["category_id"]]).sum()),
        "n_sales": len(sales),
    }
    return findings


def _validity_score(row):
    """Score a sales row for duplicate-conflict resolution.

    Higher = more trustworthy. A row gains a point for each of:
    (1) store_id is a real store, (2) product_id is a real product,
    (3) line_amount is arithmetically consistent with qty * unit_price.
    """
    q = _num(pd.Series([row["qty"]])).iloc[0]
    p = _num(pd.Series([row["unit_price"]])).iloc[0]
    a = _num(pd.Series([row["line_amount"]])).iloc[0]
    score = 0.0
    score += 1.0 if row["store_id"] not in ("", "9999") else 0.0
    score += 1.0 if row["product_id"] not in ("", "9999") else 0.0
    if pd.notna(q) and pd.notna(p) and pd.notna(a) and (q * p) != 0:
        if abs(a - q * p) / abs(q * p) < 1e-6:
            score += 1.0
    return score


def repair(dfs, rng_seed=42):
    """Apply the full repair pipeline. Returns (clean_dict, change_log).

    clean_dict maps table name -> cleaned DataFrame; change_log is a list of
    {step, table, column, operation, rows, rationale} records.
    """
    log = []
    def rec(step, table, column, operation, rows, rationale):
        log.append(dict(step=step, table=table, column=column,
                        operation=operation, rows=int(rows), rationale=rationale))

    # --- 0. reference tables -------------------------------------------------
    vendors = dfs["vendors"].copy()
    stores = dfs["stores"].copy()
    products = dfs["products"].copy()
    categories = dfs["categories"].copy()

    # 0.1 standardize inconsistent category labels -> "Category_{id}"
    before = categories["name"].tolist()
    categories["name"] = "Category_" + categories["category_id"].astype(str)
    rec(0, "categories", "name", "standardize label",
        sum(a != b for a, b in zip(before, categories["name"])),
        "naming had 4 distinct conventions (Cat-One, category_2, Category_N); "
        "normalized to Category_N to remove label drift and enable joins-by-name.")

    sales = dfs["sales"].copy()
    sales["_q"] = _num(sales["qty"]); sales["_p"] = _num(sales["unit_price"])
    sales["_a"] = _num(sales["line_amount"])
    sales["_tid"] = _num(sales["txn_id"])

    # --- 1. duplicate txn_id resolution -------------------------------------
    # txn_id is the transaction key. 50 ids appear twice -> 100 rows. Keep the
    # most valid member of each group (validity = real store + real product +
    # amount consistent with qty*price); for full duplicates this collapses to
    # keep-one.
    sales["_score"] = sales.apply(_validity_score, axis=1)
    keep_idx = sales.groupby("txn_id")["_score"].idxmax()
    dropped = len(sales) - len(keep_idx)
    sales = sales.loc[keep_idx].sort_values("_tid").reset_index(drop=True)
    rec(1, "sales", "txn_id", "deduplicate (keep-most-valid)",
        dropped,
        "50 txn_ids were stored twice (47 identical + 3 conflicting). Kept the "
        "member with valid store/product and consistent line_amount per id.")

    # --- 2. qty outlier spike (x1000) ---------------------------------------
    # 29 rows have qty in {1000,2000,3000,4000} but their line_amount equals the
    # *unscaled* qty * price -> quantity was inflated 1000x, price/doc intact.
    big = sales["_q"] >= 1000
    sales.loc[big, "_q"] = sales.loc[big, "_q"] / 1000.0
    rec(2, "sales", "qty", "scale outlier /1000",
        int(big.sum()),
        "qty in {1000..4000} appears only where line_amount is already "
        "qty*price; the true count is qty/1000 (evidence: amount invariant holds).")

    # --- 3. line_amount x100 corruption -------------------------------------
    # After (2), any remaining line_amount that is ~100x qty*price is a corrupt
    # total; recompute it from quantity and unit price (derived-field invariant).
    calc = (sales["_q"] * sales["_p"])
    ratio = sales["_a"] / calc.replace(0, np.nan)
    corrupt = (sales["_q"].notna() & sales["_p"].notna() & sales["_a"].notna()
               & ((ratio - 100).abs() < 0.5))
    sales.loc[corrupt, "_a"] = sales.loc[corrupt, "_q"] * sales.loc[corrupt, "_p"]
    rec(3, "sales", "line_amount", "recompute qty*unit_price",
        int(corrupt.sum()),
        "14 line_amounts were 100x the true qty*unit_price; line_amount is a "
        "derived field, so it is recomputed from the (trusted) qty & unit_price.")

    # --- 4. exact recovery of missing qty / unit_price ----------------------
    # qty and unit_price are never simultaneously missing, and line_amount is
    # always present -> each missing value is exactly recoverable from the
    # line_total invariant.
    miss_q = sales["_q"].isna()
    sales.loc[miss_q, "_q"] = (sales.loc[miss_q, "_a"] / sales.loc[miss_q, "_p"]).round()
    rec(4, "sales", "qty", "recover = line_amount/unit_price",
        int(miss_q.sum()),
        "qty derived exactly from line_amount/unit_price (counts are integers).")

    miss_p = sales["_p"].isna()
    sales.loc[miss_p, "_p"] = sales.loc[miss_p, "_a"] / sales.loc[miss_p, "_q"]
    rec(5, "sales", "unit_price", "recover = line_amount/qty",
        int(miss_p.sum()),
        "unit_price derived exactly from line_amount/qty (no guess, full precision).")

    # --- 5. exact recovery of missing txn_date ------------------------------
    # txn_id is a dense monotonic integer 1..2809 and each day covers a
    # contiguous txn_id block (verified: 0 block inversions). So the date is a
    # deterministic step-function of txn_id -> forward-fill recovers exactly.
    known = sales.loc[sales["txn_date"] != "", ["_tid", "txn_date"]].copy()
    known["_d"] = pd.to_datetime(known["txn_date"], errors="coerce")
    known = known.dropna(subset=["_d"]).drop_duplicates("_tid").sort_values("_tid")
    dmap = (known.set_index("_tid")["_d"]
            .reindex(range(1, int(sales["_tid"].max()) + 1))
            .ffill())
    miss_d = sales["txn_date"] == ""
    sales.loc[miss_d, "txn_date"] = dmap.loc[sales.loc[miss_d, "_tid"]].dt.strftime("%Y-%m-%d %H:%M:%S").values
    rec(6, "sales", "txn_date", "recover via txn_id block (ffill)",
        int(miss_d.sum()),
        "txn_date is a step-function of txn_id (contiguous daily blocks); "
        "forward-fill on the dense txn_id axis recovers the exact date.")

    # --- 6. exact recovery of store_id == 9999 ------------------------------
    # Within each day the stores cycle 1->2->3->4->5 in contiguous blocks
    # (verified: 0 non-monotone days). Recover the store from the block a txn
    # falls into; at a block boundary use the *next* block (bfill).
    known_s = sales.loc[sales["store_id"] != "9999", ["_tid", "store_id"]].copy()
    known_s["_s"] = _num(known_s["store_id"])
    known_s = known_s.drop_duplicates("_tid").sort_values("_tid")
    smap = known_s.set_index("_tid")["_s"].reindex(range(1, int(sales["_tid"].max()) + 1))
    ffill = smap.ffill(); bfill = smap.bfill()
    orphan_s = sales["store_id"] == "9999"
    recovered_s = np.where(ffill == bfill, ffill, bfill)  # boundary -> next block
    inds = sales.loc[orphan_s, "_tid"].to_numpy().astype(int) - 1
    sales.loc[orphan_s, "store_id"] = recovered_s[inds].astype(int).astype(str)
    rec(7, "sales", "store_id", "recover via store block order",
        int(orphan_s.sum()),
        "store_id=9999 is a malformed key; the store cycle (1..5 per day, "
        "contiguous) identically determines the true store from the txn position.")

    # --- 7. product_id == 9999: unrecoverable -> principled imputation ------
    # product_id is independent of qty, unit_price, store and date (verified),
    # so no deterministic recovery is possible. Preserve the marginal
    # distribution by sampling from empirical product frequency (fixed seed).
    orphans_p = sales["product_id"] == "9999"
    valid_p = _num(sales.loc[~orphans_p, "product_id"]).astype(int)
    freq = valid_p.value_counts(normalize=True).sort_index()
    rng = np.random.default_rng(rng_seed)
    imputed = rng.choice(freq.index.values, size=int(orphans_p.sum()), p=freq.values)
    sales.loc[orphans_p, "product_id"] = imputed.astype(int).astype(str)
    rec(8, "sales", "product_id", "impute (empirical-frequency sampling)",
        int(orphans_p.sum()),
        "product_id has no association with any observed column (uniform iid); "
        "reassigned by seeded sampling from P(product) to keep the marginal "
        "distribution unbiased and remain referentially valid.")

    # --- 8. finalize dtypes & canonical derived field -----------------------
    out = sales.copy()
    out["qty"] = out["_q"].round().astype(int)
    out["unit_price"] = out["_p"]
    out["line_amount"] = out["_q"] * out["_p"]   # canonical derived field
    out["txn_id"] = out["_tid"].astype(int)
    out["txn_date"] = out["txn_date"].str.strip()
    out["store_id"] = out["store_id"].astype(int)
    out["product_id"] = out["product_id"].astype(int)
    out = out[SCHEMA["sales"]]
    rec(9, "sales", "line_amount", "normalize = qty*unit_price",
        int(((out["line_amount"] - out["qty"] * out["unit_price"]).abs() > 1e-6).sum()),
        "re-express line_amount as the canonical qty*unit_price for full "
        "self-consistency (only the x100 rows change meaningfully).")

    clean = {
        "products":   products.astype({"product_id": int, "category_id": int, "vendor_id": int}),
        "vendors":    vendors.astype({"vendor_id": int}),
        "stores":     stores.astype({"store_id": int}),
        "categories": categories.astype({"category_id": int}),
        "sales":      out,
    }
    return clean, log


def validate(clean):
    """Run referential-integrity + pattern checks. Returns dict of {check: bool}."""
    sales = clean["sales"]
    p = clean["products"]; s = clean["stores"]; c = clean["categories"]
    v = clean["vendors"]
    q, price, amt = sales["qty"], sales["unit_price"], sales["line_amount"]
    checks = {
        "no_null_txn_date":   sales["txn_date"].notna().all(),
        "no_null_qty":        q.notna().all(),
        "no_null_price":      price.notna().all(),
        "no_null_amount":     amt.notna().all(),
        "no_dup_txn_id":      not sales["txn_id"].duplicated().any(),
        "txn_id_dense":       set(sales["txn_id"]) == set(range(1, len(sales) + 1)),
        "store_refs_valid":   sales["store_id"].isin(s["store_id"]).all(),
        "product_refs_valid": sales["product_id"].isin(p["product_id"]).all(),
        "qty_in_1_4":         q.isin([1, 2, 3, 4]).all(),
        "qty_integer":        (q == q.round()).all(),
        "price_positive":     (price > 0).all(),
        "amount_consistent":  (amt - q * price).abs().max() < 1e-6,
        "date_in_window":     pd.to_datetime(sales["txn_date"]).dt.year.eq(2024).all(),
        "date_monotonic_tid": (pd.to_datetime(sales["txn_date"]).sort_index()  # by construction sorted by tid
                               .diff().dt.total_seconds().fillna(0) >= -1).all(),
        "products_clean":     (not p["product_id"].duplicated().any()) and
                              p["category_id"].isin(c["category_id"]).all() and
                              p["vendor_id"].isin(v["vendor_id"]).all(),
        "vendors_clean":      not v["vendor_id"].duplicated().any(),
        "stores_clean":       not s["store_id"].duplicated().any(),
        "categories_clean":   (not c["category_id"].duplicated().any()) and
                              (((c["name"] == "Category_" + c["category_id"].astype(str)).all())),
    }
    return checks


def daily_store_revenue(sales):
    """Aggregate sales -> daily revenue per store (for the baseline model)."""
    s = sales.copy()
    s["date"] = pd.to_datetime(s["txn_date"]).dt.normalize()
    daily = (s.groupby(["store_id", "date"], as_index=False)["line_amount"]
              .sum().rename(columns={"line_amount": "revenue"}))
    return daily.sort_values(["store_id", "date"]).reset_index(drop=True)