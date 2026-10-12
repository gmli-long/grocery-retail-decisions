"""
Challenge 01 — baseline daily store-sales forecast on the normalized schema.
Demonstrates "analytical readiness": a simple, defensible model that predicts
daily revenue per store, evaluated on a held-out time window.

Model: RandomForest on calendar features vs. two naive baselines.
Metrics: MAE, RMSE, MAPE on the held-out Nov–Dec window.
"""
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "challenge_01.sqlite"
FIG = BASE / "reports" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB)

# Daily revenue per store, ordered by (store, date)
daily = pd.read_sql_query("""
SELECT r.store_id,
       date(r.sale_datetime) AS d,
       SUM(li.line_subtotal) AS revenue
FROM receipts r
JOIN line_items li ON li.receipt_id = r.receipt_id
GROUP BY r.store_id, date(r.sale_datetime)
ORDER BY r.store_id, d
""", conn)
conn.close()

daily["d"] = pd.to_datetime(daily["d"])
print("daily rows:", len(daily), "| stores:", sorted(daily.store_id.unique()))
print("date range:", daily.d.min().date(), "->", daily.d.max().date())

# completeness: how many store-days in grid
grid = pd.date_range(daily.d.min(), daily.d.max())
full = pd.MultiIndex.from_product([sorted(daily.store_id.unique()), grid],
                                  names=["store_id", "d"])
present = len(daily)
possible = len(full)
print(f"grid coverage: {present}/{possible} store-days "
      f"({100*present/possible:.1f}%)")

def add_features(df):
    df = df.copy()
    df["dow"] = df["d"].dt.dayofweek
    df["month"] = df["d"].dt.month
    df["dayofyear"] = df["d"].dt.dayofyear
    df["is_weekend"] = (df["dow"] >= 5).astype(int)
    return df

daily = add_features(daily)

# ---- time-based split: train Jan–Oct, test Nov–Dec ------------------------
train = daily[daily["d"] < "2024-11-01"].copy()
test = daily[daily["d"] >= "2024-11-01"].copy()
print(f"train: {len(train)} store-days | test: {len(test)} store-days")

train = train.sort_values(["store_id", "d"]).reset_index(drop=True)
test = test.sort_values(["store_id", "d"]).reset_index(drop=True)

# ---- naive baselines -------------------------------------------------------
# (a) persistence: yesterday's revenue for the same store
prev = (train.groupby("store_id")["d"].max()).reset_index()
last_rev = train.groupby("store_id")["revenue"].last().to_dict()
def naive_persist(df):
    y = []
    for s in df.store_id:
        y.append(last_rev.get(s, np.nan))
    return np.array(y)

# (b) seasonal naive: same weekday, one week earlier (last value in train for that store+dow)
dow_rev = (train.groupby(["store_id", "dow"])["revenue"].last().to_dict())
def naive_weekday(df):
    return np.array([dow_rev.get((s, w), np.nan) for s, w in zip(df.store_id, df.dow)])

y_test = test["revenue"].values
pred_persist = naive_persist(test)
pred_weekday = naive_weekday(test)

def metrics(ytrue, ypred):
    mask = ~np.isnan(ypred) & ~np.isnan(ytrue)
    yt, yp = ytrue[mask], ypred[mask]
    mae = mean_absolute_error(yt, yp)
    rmse = np.sqrt(mean_squared_error(yt, yp))
    mape = 100 * np.mean(np.abs((yt - yp) / yt))
    return mae, rmse, mape, mask.sum()

results = {}
results["persistence"] = metrics(y_test, pred_persist)
results["weekday_naive"] = metrics(y_test, pred_weekday)

# ---- RandomForest model ----------------------------------------------------
FEATS = ["store_id", "dow", "month", "dayofyear", "is_weekend"]
model = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=42,
                              n_jobs=-1)
model.fit(train[FEATS], train["revenue"])
pred_rf = model.predict(test[FEATS])
results["random_forest"] = metrics(y_test, pred_rf)

print("\n" + "=" * 58)
print(f"{'model':<16}{'MAE':>10}{'RMSE':>10}{'MAPE%':>9}{'n':>6}")
print("-" * 58)
for k, (mae, rmse, mape, n) in results.items():
    print(f"{k:<16}{mae:>10.1f}{rmse:>10.1f}{mape:>9.2f}{n:>6}")

# model diagnostics vs weekday-naive
m_rf = results["random_forest"]; m_wn = results["weekday_naive"]
print(f"\nRF improves MAPE vs weekday-naive by "
      f"{(m_wn[2]-m_rf[2]):.2f} pts")

# ---- figure: predicted vs actual (store 102) ------------------------------
best = model
s102 = test[test.store_id == 101].sort_values("d")
p102 = best.predict(s102[FEATS])
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.plot(s102.d, s102.revenue.values, color="#2c7fb8", label="Actual", lw=1.2)
ax.plot(s102.d, p102, color="#f03b20", label="Predicted (RF)", lw=1.2, alpha=0.85)
ax.set_title("Daily store revenue — test window (Store 101, Nov–Dec)")
ax.set_ylabel("Revenue ($)")
ax.legend()
plt.tight_layout()
plt.savefig(FIG / "fig7_forecast.png", bbox_inches="tight")
plt.close()

# feature importances (for the report)
imp = sorted(zip(FEATS, model.feature_importances_), key=lambda x: -x[1])
print("\nfeature importances:")
for f, v in imp:
    print(f"  {f:<12}{v:.3f}")

print("\nFigure written to", FIG / "fig7_forecast.png")