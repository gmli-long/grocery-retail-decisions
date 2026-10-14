"""Challenge 02 — verify the premises the repair pipeline relies on.

``run_repair.py`` recovers most corrupted values *deterministically* from data
invariants rather than guessing (ffill the dense txn_id axis for dates, store
block order for store_id, /1000 for qty spikes, qty*unit_price for amounts). If
any of those invariants is violated in a future dataset, the repair would
silently fill wrong values. This script re-checks the premises against the RAW
input as hard assertions, so a broken assumption fails loudly before anyone
trusts the cleaned output.

Run from the repo root:

    python challenge_02_errors_integrity/scripts/verify_premises.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"

FAILED = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    line = f"  [{status}] {name}"
    if not cond and detail:
        line += f"  -> {detail}"
    print(line)
    if not cond:
        FAILED.append(name)
    return bool(cond)


def main():
    sales = pd.read_csv(RAW / "sales.csv", dtype=str, keep_default_na=False)
    q = pd.to_numeric(sales["qty"], errors="coerce")
    p = pd.to_numeric(sales["unit_price"], errors="coerce")
    a = pd.to_numeric(sales["line_amount"], errors="coerce")
    tid = pd.to_numeric(sales["txn_id"], errors="coerce")
    date = pd.to_datetime(sales["txn_date"], errors="coerce")

    # ------------------------------------------------------------- premise 1
    print("PREMISE 1 — txn_id is dense & sorted (ffill date-recovery grid)")
    check("txn_id has no nulls", tid.notna().all(),
          f"{int(tid.isna().sum())} null txn_id")
    uniq = np.sort(tid.dropna().unique().astype(int))
    check("distinct txn_id are exactly 1..N",
          (uniq == np.arange(1, len(uniq) + 1)).all(),
          f"min={uniq.min()} max={uniq.max()} distinct={len(uniq)}")

    # one txn_id -> at most one non-null date (dups may repeat, never conflict)
    dd = pd.DataFrame({"_tid": tid, "_d": date}).dropna(subset=["_d"])
    multi = dd.groupby("_tid")["_d"].nunique()
    check("each txn_id maps to <=1 date", int((multi > 1).sum()) == 0,
          f"{int((multi > 1).sum())} txn_id with >1 date")

    # date non-decreasing in txn_id (the step-function premise for ffill)
    known = dd.drop_duplicates("_tid").sort_values("_tid")
    mono = (known["_d"].diff().dt.total_seconds().fillna(0) >= -1).all()
    check("txn_date non-decreasing in txn_id", bool(mono))
    print()

    # ------------------------------------------------------------- premise 2
    print("PREMISE 2 — qty outliers are exact x1000 (rescale rule)")
    big = q >= 1000
    spike_vals = np.sort(q[big].dropna().unique().astype(int))
    print(f"  qty>=1000 rows: {int(big.sum())}  values: {spike_vals.tolist()}")
    check("outlier qtys are exact multiples of 1000",
          all(v % 1000 == 0 for v in spike_vals))
    # amount already reflects the *unscaled* qty: line_amount == (qty/1000)*price
    resid = (a[big] - (q[big] / 1000.0) * p[big]).abs()
    check("outlier amount == (qty/1000)*unit_price",
          bool(big.sum() == 0 or resid.max() < 1e-6),
          f"max resid={resid.max():.2g}" if big.sum() else "")
    print()

    # ------------------------------------------------------------- premise 3
    print("PREMISE 3 — remaining amount errors are exact x100 (recompute rule)")
    mis = (a - q * p).abs() > 1e-2
    non_outlier_mis = mis & ~big & q.notna() & p.notna() & a.notna()
    ratio = a[non_outlier_mis] / (q[non_outlier_mis] * p[non_outlier_mis])
    print(f"  non-outlier mismatched rows: {int(non_outlier_mis.sum())}")
    check("every non-outlier mismatch is a ~x100 inflation",
          bool(non_outlier_mis.sum() == 0 or ((ratio - 100).abs() < 0.5).all()),
          f"ratios={np.round(ratio, 3).tolist()}" if non_outlier_mis.sum() else "")
    print()

    # ------------------------------------------------------------- premise 4
    print("PREMISE 4 — store_id sentinel 9999 + contiguous 1..5 cycle")
    orphan_store = sales["store_id"] == "9999"
    print(f"  store_id==9999 rows: {int(orphan_store.sum())}")
    valid_s = pd.to_numeric(sales.loc[~orphan_store, "store_id"], errors="coerce")
    check("valid store_id are all in 1..5 (no other sentinel)",
          bool(valid_s.notna().all() and valid_s.between(1, 5).all()))
    # within each day, valid store sequence never regresses (contiguous blocks)
    s = sales.assign(_tid=tid, _d=date, _s=pd.to_numeric(sales["store_id"], errors="coerce"))
    # the premise applies to valid stores (1..5) on known dates; the 9999 and
    # missing-date rows are the holes the recovery fills, not part of the cycle.
    s = s[s["_s"].between(1, 5) & s["_d"].notna()].sort_values("_tid")
    s["_day"] = s["_d"].dt.normalize()
    inversions = 0
    for _, g in s.groupby("_day"):
        seq = g["_s"].astype(int).tolist()
        inversions += sum(1 for x, y in zip(seq, seq[1:]) if y < x)
    check("store cycle contiguous within each day", inversions == 0,
          f"{inversions} non-monotone store steps")
    print()

    if FAILED:
        print(f"FAILED {len(FAILED)} premise(s): {FAILED}")
        raise SystemExit(1)
    print("All premises hold.")


if __name__ == "__main__":
    main()