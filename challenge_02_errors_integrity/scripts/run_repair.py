"""Challenge 02 — end-to-end audit -> repair -> validate pipeline.

Produces:
    data/clean/{products,vendors,stores,categories,sales}.csv
    data/clean/audit_log.csv            (machine-readable change log)
    reports/metrics.json                 (all findings + checks + summary)
    reports/figures/f*.png               (evidence figures)
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))
import helper_utils as hu

RAW = BASE / "data" / "raw"
CLEAN = BASE / "data" / "clean"
FIG = BASE / "reports" / "figures"
CLEAN.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

NAVY = "#1b4f72"; BLUE = "#2c7fb8"; RED = "#c0392b"; AMBER = "#f0a32c"


def _num(x):
    return pd.to_numeric(x, errors="coerce")


# ============================ 1. AUDIT ======================================
dfs = hu.load_raw(RAW)
findings = hu.audit(dfs)
print("=" * 70)
print(f"{'FINDING':<28}{'COUNT':>8}")
print("=" * 70)
for k, v in findings.items():
    print(f"{k:<28}{str(v):>8}")

# ============================ 2. REPAIR =====================================
clean, change_log = hu.repair(dfs)
print("\n" + "=" * 70)
print("CHANGE LOG")
print("=" * 70)
for r in change_log:
    print(f"[step {r['step']}] {r['table']}.{r['column']}: {r['operation']} "
          f"({r['rows']} rows)")

# ============================ 3. VALIDATE ===================================
checks = hu.validate(clean)
n_fail = sum(1 for c, ok in checks.items() if not ok)
print("\n" + "=" * 70)
print("VALIDATION")
print("=" * 70)
for c, ok in checks.items():
    print(f"  {'PASS' if ok else 'FAIL'}  {c}")
print(f"\n{n_fail} failures / {len(checks)} checks")

# ============================ 4. PERSIST ====================================
for t, df in clean.items():
    df.to_csv(CLEAN / f"{t}.csv", index=False)
pd.DataFrame(change_log).to_csv(CLEAN / "audit_log.csv", index=False)
print("\ncleaned CSVs written to", CLEAN)

# ============================ 5. SUMMARY METRICS ============================
raw_sales = dfs["sales"]
q = _num(raw_sales["qty"]); p = _num(raw_sales["unit_price"]); a = _num(raw_sales["line_amount"])
total_err_units = (findings["missing_txn_date"] + findings["missing_qty"]
                   + findings["missing_unit_price"] + findings["dup_txn_id"]
                   + findings["store_orphans"] + findings["product_orphans"]
                   + findings["qty_outliers_ge1000"] + findings["amount_mismatch"])

metrics = {
    "n_sales_raw": len(raw_sales),
    "n_sales_clean": len(clean["sales"]),
    "rows_dropped": len(raw_sales) - len(clean["sales"]),
    "total_error_units": int(total_err_units),
    "findings": findings,
    "change_log": change_log,
    "validation": {k: bool(v) for k, v in checks.items()},
    "validation_passed": n_fail == 0,
    "revenue_raw": float(a.sum()),
    "revenue_clean": float(clean["sales"]["line_amount"].sum()),
}
with open(BASE / "reports" / "metrics.json", "w", encoding="utf-8") as f:
    json.dump(metrics, f, ensure_ascii=False, indent=2, default=str)
print("metrics ->", BASE / "reports" / "metrics.json")

# ============================ 6. FIGURES ====================================
# fig1 — missing values per sales column
miss = pd.Series({
    "txn_date": findings["missing_txn_date"],
    "qty": findings["missing_qty"],
    "unit_price": findings["missing_unit_price"],
    "line_amount": findings["missing_line_amount"],
})
fig, ax = plt.subplots(figsize=(7, 3))
bars = ax.barh(miss.index[::-1], miss.values[::-1], color=[AMBER, BLUE, BLUE, NAVY])
ax.bar_label(bars, padding=2, fontsize=9)
ax.set_title("Sales — missing values per column (raw)")
ax.set_xlabel("count"); ax.set_xlim(0, 60)
plt.tight_layout(); plt.savefig(FIG / "fig1_missing_values.png", dpi=110); plt.close()

# fig2 — qty distribution before/after
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.4), sharey=False)
raw_q = _num(raw_sales["qty"]).dropna()
clean_q = clean["sales"]["qty"]
vc_raw = raw_q.value_counts().sort_index()
vc_clean = clean_q.value_counts().sort_index()
ax1.bar(vc_raw.index.astype(str), vc_raw.values, color=BLUE)
ax1.set_title("Raw qty (spikes at 1000–4000)"); ax1.set_xlabel("qty")
ax1.annotate("29 outliers", xy=(1, vc_raw.get(1000, 0)), xytext=(2.3, 660),
             arrowprops=dict(arrowstyle="->", color=RED), color=RED, fontsize=9)
ax2.bar(vc_clean.index.astype(str), vc_clean.values, color=NAVY)
ax2.set_title("Clean qty (only 1–4)"); ax2.set_xlabel("qty")
plt.tight_layout(); plt.savefig(FIG / "fig2_qty_spikes.png", dpi=110); plt.close()

# fig3 — line_amount ratio distribution (log10), highlighting two corrupt clusters
sraw = dfs["sales"].copy()
sraw["_q"] = _num(sraw["qty"]); sraw["_p"] = _num(sraw["unit_price"]); sraw["_a"] = _num(sraw["line_amount"])
sraw["_ratio"] = sraw["_a"] / (sraw["_q"] * sraw["_p"])
r = sraw["_ratio"].dropna()
r = r[(r > 0) & np.isfinite(np.log10(r))]
fig, ax = plt.subplots(figsize=(7, 3.4))
ax.hist(np.log10(r), bins=60, color=BLUE, edgecolor="white")
ax.axvline(0, color=NAVY, lw=1.2, ls="--", label="consistent (ratio=1)")
ax.axvline(2, color=RED, lw=1.2, ls=":", label="x100 corruption")
ax.axvline(-3, color=AMBER, lw=1.2, ls=":", label="qty x1000 (amount ok)")
ax.set_xlabel("log10(line_amount / (qty*unit_price))"); ax.set_ylabel("rows")
ax.set_title("Amount-consistency ratio (raw)")
ax.legend(fontsize=8)
plt.tight_layout(); plt.savefig(FIG / "fig3_amount_ratio.png", dpi=110); plt.close()

# fig4 — daily revenue before/after
def daily_rev(sales, label):
    s = sales.copy()
    s["d"] = pd.to_datetime(s["txn_date"], errors="coerce").dt.normalize()
    return (s.dropna(subset=["d"]).groupby("d")["_a"]
             .sum().rename(label))
raw_daily = daily_rev(sraw[sraw["_a"].notna()], "raw")
clean["sales"]["_a"] = clean["sales"]["line_amount"]
clean_s = clean["sales"].copy()
clean_s["d"] = pd.to_datetime(clean_s["txn_date"]).dt.normalize()
clean_daily = clean_s.groupby("d")["line_amount"].sum().rename("clean")

fig, ax = plt.subplots(figsize=(9, 3.6))
ax.plot(raw_daily.index, raw_daily.values, color=RED, alpha=0.75, lw=1.1, label="raw")
ax.plot(clean_daily.index, clean_daily.values, color=NAVY, lw=1.6, label="clean")
ax.set_title("Daily total revenue — raw vs cleaned")
ax.set_xlabel("date"); ax.set_ylabel("revenue ($)"); ax.legend()
plt.tight_layout(); plt.savefig(FIG / "fig4_daily_revenue.png", dpi=110); plt.close()

print("figures ->", FIG)
print("\nDONE")