"""Challenge 02 — baseline re-test: does cleaning change the model?

Trains the *same* Challenge-01 baseline (daily store-revenue forecast) twice —
once on the raw/dirty targets and once on the cleaned targets — and evaluates
both against the cleaned (trusted) test window. The goal is to show cleaning
*removes* distortion rather than introducing suspicious metric jumps.

Outputs:
    reports/retest_metrics.json
    reports/figures/fig5_retest.png
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))
import helper_utils as hu

FIG = BASE / "reports" / "figures"
NAVY = "#1b4f72"; BLUE = "#2c7fb8"; RED = "#c0392b"

raw = hu.load_raw(BASE / "data" / "raw")
clean = hu.load_raw(BASE / "data" / "clean")  # load clean with same string loader


def daily(raw_sales):
    s = raw_sales.copy()
    s["date"] = pd.to_datetime(s["txn_date"], errors="coerce").dt.normalize()
    s["amt"] = pd.to_numeric(s["line_amount"], errors="coerce")
    d = (s.dropna(subset=["date"])
          .groupby(["store_id", "date"], as_index=False)["amt"].sum()
          .rename(columns={"amt": "revenue"}))
    d["store_id"] = d["store_id"].astype(int)
    return d.sort_values(["store_id", "date"]).reset_index(drop=True)


dirty = daily(raw["sales"])          # raw daily revenue (distorted)
truth = daily(clean["sales"])        # cleaned daily revenue (trusted)

# align to the cleaned grid (all 5 stores x 60 days present)
grid = truth[["store_id", "date"]].copy()
dirty_al = grid.merge(dirty, on=["store_id", "date"], how="left")
dirty_al["revenue"] = dirty_al["revenue"].fillna(0.0)
print(f"grid: {len(truth)} clean store-days | {dirty_al['revenue'].notna().sum()} dirty coverage")

FEATS = ["store_id", "dow", "month", "dayofyear", "is_weekend"]


def add_feats(df):
    df = df.copy()
    df["dow"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month
    df["dayofyear"] = df["date"].dt.dayofyear
    df["is_weekend"] = (df["dow"] >= 5).astype(int)
    return df


truth_f = add_feats(truth)
dirty_f = add_feats(dirty_al)

SPLIT = "2024-02-15"
train_t = truth_f[truth_f["date"] < SPLIT]
test_t = truth_f[truth_f["date"] >= SPLIT]
train_d = dirty_f[dirty_f["date"] < SPLIT]
test_d = dirty_f[dirty_f["date"] >= SPLIT]
y_test = test_t["revenue"].values   # trusted targets

print(f"train store-days: {len(train_t)} | test: {len(test_t)}")


def metrics(ytrue, ypred):
    m = ~np.isnan(ypred)
    yt, yp = ytrue[m], ypred[m]
    mae = mean_absolute_error(yt, yp)
    rmse = np.sqrt(mean_squared_error(yt, yp))
    mape = 100 * np.mean(np.abs((yt - yp) / yt))
    return dict(mae=float(mae), rmse=float(rmse), mape=float(mape), n=int(m.sum()))


def naive_preds(train_df):
    last = train_df.groupby("store_id")["revenue"].last().to_dict()
    dow_last = train_df.groupby(["store_id", "dow"])["revenue"].last().to_dict()
    def persist(test_df):
        return np.array([last.get(s, np.nan) for s in test_df["store_id"]])
    def weekday(test_df):
        return np.array([dow_last.get((s, w), np.nan)
                        for s, w in zip(test_df["store_id"], test_df["dow"])])
    return persist, weekday


def fit_rf(train_df):
    m = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=42, n_jobs=-1)
    m.fit(train_df[FEATS], train_df["revenue"])
    return m


results = {}
for tag, train_df in [("dirty", train_d), ("clean", train_t)]:
    persist, weekday = naive_preds(train_df)
    rf = fit_rf(train_df)
    results[tag] = {
        "persistence": metrics(y_test, persist(test_t)),
        "weekday_naive": metrics(y_test, weekday(test_t)),
        "random_forest": metrics(y_test, rf.predict(test_t[FEATS])),
    }

print("\nmodel                  |  MAE    RMSE   MAPE%   (train=" + "dirty" + " -> clean)")
print("-" * 74)
models = ["persistence", "weekday_naive", "random_forest"]
for mname in models:
    d = results["dirty"][mname]; c = results["clean"][mname]
    print(f"{mname:<22} | {d['mae']:6.0f}  {d['rmse']:6.0f}  {d['mape']:5.2f} "
          f"-> {c['mae']:6.0f}  {c['rmse']:6.0f}  {c['mape']:5.2f}")

with open(BASE / "reports" / "retest_metrics.json", "w", encoding="utf-8") as f:
    json.dump({"split": SPLIT, "results": results,
               "revenue_dirty_total": float(dirty["revenue"].sum()),
               "revenue_clean_total": float(truth["revenue"].sum())},
              f, ensure_ascii=False, indent=2, default=str)

# --- figure: actual vs RF predictions (dirty-trained vs clean-trained) ------
rf_d = fit_rf(train_d); rf_c = fit_rf(train_t)
fig, ax = plt.subplots(figsize=(9, 3.8))
s5 = test_t[test_t["store_id"] == 5].sort_values("date")
ax.plot(s5["date"], s5["revenue"].values, color=NAVY, lw=1.6, label="actual (clean)")
ax.plot(s5["date"], rf_d.predict(s5[FEATS]), color=RED, lw=1.2, alpha=0.8, label="RF trained on dirty")
ax.plot(s5["date"], rf_c.predict(s5[FEATS]), color=BLUE, lw=1.2, alpha=0.9, label="RF trained on clean")
ax.set_title("Store 5 daily revenue — test window (Feb 15–29)")
ax.set_ylabel("revenue ($)"); ax.legend(fontsize=8)
plt.tight_layout(); plt.savefig(FIG / "fig5_retest.png", dpi=110); plt.close()

print("\nretest_metrics.json written; figure ->", FIG / "fig5_retest.png")