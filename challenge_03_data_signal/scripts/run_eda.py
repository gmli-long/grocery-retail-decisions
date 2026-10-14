"""Challenge 03 — signal & seasonality exploration.

Produces the evidence figures and a machine-readable signal_metrics.json that
the notebooks and reports build upon. Nothing here mutates source data; it only
*reads* the clean CSVs and derives signal.
"""
from __future__ import annotations

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

import helper_utils as hu  # noqa: E402

FIG = hu.FIG
REP = hu.REP

NAVY = "#1b4f72"; BLUE = "#2874a6"; AMBER = "#e67e22"; RED = "#c0392b"
GREEN = "#1e8449"; GREY = "#7f8c8d"

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 130, "font.size": 9,
    "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False,
})

CAT_COLORS = {"Beverages": BLUE, "Bakery": AMBER, "Meat": RED, "Produce": GREEN}
CAT_ORDER = ["Beverages", "Bakery", "Meat", "Produce"]
STORE_COLORS = {1: NAVY, 2: BLUE, 3: AMBER}
STORE_LABEL = {1: "Seattle (L)", 2: "Portland (M)", 3: "Boise (S)"}


def panel():
    return hu.build_panel()


def total(p=None):
    return hu.daily_total(p)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / name)


# ============================================================================
# fig1 — overview & trend
# ============================================================================
def fig_overview(s):
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.plot(s.index, s.values, color=GREY, alpha=0.45, lw=0.6, label="daily")
    ax.plot(s.index, s.rolling(30).mean(), color=BLUE, lw=1.2, label="30-day mean")
    ax.plot(s.index, s.rolling(365).mean(), color=NAVY, lw=2.2, label="365-day trend")
    ax.set_title("Total daily revenue, 2018–2022")
    ax.set_ylabel("Revenue ($)")
    ax.legend(loc="upper left", frameon=False)
    save(fig, "fig1_overview_trend.png")


# ============================================================================
# fig2 — periodogram (unsupervised seasonality detection)
# ============================================================================
def fig_periodogram(s):
    periods = hu.dominant_periods(s, top_n=6)
    fig, ax = plt.subplots(figsize=(9, 3.2))

    # full periodogram for the curve
    from scipy.signal import periodogram
    y = hu.detrend(s).to_numpy()
    f, Pxx = periodogram(y, detrend=False)
    mask = f > 0
    ax.plot(1 / f[mask], Pxx[mask] / Pxx[mask].max(), color=GREY, alpha=0.5, lw=0.7)
    ax.set_xscale("log")
    ax.set_xlim(2, 400)

    for p, pw in periods[:6]:
        ax.axvline(p, color=RED if abs(p - 365) < 3 or abs(p - 7) < 1 else AMBER,
                   ls="--", lw=1.1, alpha=0.8)
        ax.annotate(f"{p:.0f}d", (p, pw), xytext=(4, 3), textcoords="offset points",
                    fontsize=8, color=RED if abs(p - 365) < 3 else "#333")
    ax.set_xlabel("Period (days, log scale)")
    ax.set_ylabel("Normalised power")
    ax.set_title("Periodogram: dominant cycles are weekly (7d) and annual (~365d)")
    save(fig, "fig2_periodogram.png")


# ============================================================================
# fig3 — weekly seasonality by category
# ============================================================================
def fig_weekly(p):
    prof = p.groupby(["category_name", "dow"])["sales_revenue"].mean().reset_index()
    prof["day"] = prof["dow"].map(hu.ISO_WEEKDAY)
    fig, ax = plt.subplots(figsize=(9, 3.4))
    for c in CAT_ORDER:
        d = prof[prof.category_name == c].sort_values("dow")
        ax.plot(d.dow, d.sales_revenue, marker="o", ms=4, lw=1.4,
                color=CAT_COLORS[c], label=c)
    ax.set_xticks(range(7)); ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.set_ylabel("Mean revenue ($)")
    ax.set_title("Weekly seasonality by category (weekend lift, size varies)")
    ax.legend(frameon=False, ncol=4)
    save(fig, "fig3_weekly_seasonality.png")


# ============================================================================
# fig4 — annual seasonality by category (month-of-year)
# ============================================================================
def fig_annual(p):
    prof = p.groupby(["category_name", "month"])["sales_revenue"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(9, 3.4))
    for c in CAT_ORDER:
        d = prof[prof.category_name == c].sort_values("month")
        ax.plot(d.month, d.sales_revenue, marker="o", ms=4, lw=1.4,
                color=CAT_COLORS[c], label=c)
    ax.set_xticks(range(1, 13))
    ax.set_ylabel("Mean revenue ($)")
    ax.set_title("Annual seasonality by category (holiday-driven Q4 peak)")
    ax.legend(frameon=False, ncol=4)
    save(fig, "fig4_annual_seasonality.png")


# ============================================================================
# fig5 — store profiles (weekly)
# ============================================================================
def fig_stores(p):
    prof = p.groupby(["store_id", "dow"])["sales_revenue"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(9, 3.2))
    for s in [1, 2, 3]:
        d = prof[prof.store_id == s].sort_values("dow")
        ax.plot(d.dow, d.sales_revenue, marker="o", ms=4, lw=1.4,
                color=STORE_COLORS[s], label=STORE_LABEL[s])
    ax.set_xticks(range(7)); ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.set_ylabel("Mean revenue ($)")
    ax.set_title("Store-level weekly profile (scale, not shape, differs)")
    ax.legend(frameon=False, ncol=3)
    save(fig, "fig5_store_profiles.png")


# ============================================================================
# fig6 — price trend + price level (external factor)
# ============================================================================
def fig_price(p):
    q = p.groupby(["date", "category_name"])["unit_price"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(9, 3.4))
    for c in CAT_ORDER:
        d = q[q.category_name == c]
        ax.plot(d.date, d.unit_price.rolling(30).mean(), lw=1.2, color=CAT_COLORS[c], label=c)
    ax.set_ylabel("Mean unit price ($/unit)")
    ax.set_title("Category unit-price trends (external price signal)")
    ax.legend(frameon=False, ncol=4)
    save(fig, "fig6_price_trend.png")


# ============================================================================
# fig7 — holiday uplift (validated against detected anomalies)
# ============================================================================
def fig_holiday(p):
    s = total(p)
    hol = hu.us_holiday_calendar(2018, 2022)
    day = s.loc[hol["date"].tolist()].rename("holiday")
    nonhol = s.loc[~s.index.isin(hol["date"])].rename("non_holiday")
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    ax.boxplot([nonhol.values, day.values], tick_labels=["Non-holiday", "Holiday"],
               widths=0.5, patch_artist=True,
               boxprops=dict(facecolor="white", color=NAVY),
               medianprops=dict(color=RED))
    ax.set_ylabel("Daily revenue ($)")
    ax.set_title("Holiday vs non-holiday daily revenue")
    save(fig, "fig7_holiday_uplift.png")
    return {"holiday_mean": float(day.mean()), "nonholiday_mean": float(nonhol.mean()),
            "uplift_pct": float(100 * (day.mean() / nonhol.mean() - 1))}


# ============================================================================
# fig8 — STL decomposition
# ============================================================================
def fig_stl(s):
    res = hu.stl_decompose(s, 7)
    fig, axes = plt.subplots(4, 1, figsize=(9, 7), sharex=True)
    axes[0].plot(s.index, s.values, color=NAVY, lw=1.0); axes[0].set_title("Observed")
    axes[1].plot(res.trend.index, res.trend, color=BLUE, lw=1.2); axes[1].set_title("Trend")
    axes[2].plot(res.seasonal.index, res.seasonal, color=AMBER, lw=1.0); axes[2].set_title("Seasonal (weekly)")
    axes[3].plot(res.resid.index, res.resid, color=GREY, lw=0.6); axes[3].set_title("Residual")
    save(fig, "fig8_stl_decomposition.png")
    return res


# ============================================================================
# fig9 — unsupervised anomaly detection vs holiday calendar
# ============================================================================
def fig_anomalies(s):
    an = hu.detect_anomalies(s, period=7, k=3.5)
    hol = hu.us_holiday_calendar(2018, 2022)
    an = an.merge(hol.assign(is_holiday=1), on="date", how="left")
    an["is_holiday"] = an["is_holiday"].fillna(0).astype(int)

    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(s.index, s.values, color=GREY, alpha=0.4, lw=0.6, label="observed")
    up = an[an.direction == "uplift"]
    dn = an[an.direction == "suppression"]
    ax.scatter(up.date, up.observed, color=GREEN, s=14, label="detected uplift", zorder=3)
    ax.scatter(dn.date, dn.observed, color=RED, s=14, label="detected suppression", zorder=3)
    ax.set_ylabel("Daily revenue ($)")
    ax.set_title("Unsupervised anomaly detection (STL residual, |z|>3.5)")
    ax.legend(frameon=False, loc="upper right")
    save(fig, "fig9_anomaly_detection.png")

    pred = set(an[an.is_anomaly].date)
    true = set(hol.date)
    n_det = len(an[an.is_anomaly])
    n_hit = len(pred & true)
    return {"n_anomalies": n_det, "n_hits_in_holiday": n_hit,
            "precision_vs_holiday": round(n_hit / max(n_det, 1), 3),
            "n_holidays": len(true)}


# ============================================================================
def main():
    p = panel()
    s = total(p)

    fig_overview(s)
    fig_periodogram(s)
    fig_weekly(p)
    fig_annual(p)
    fig_stores(p)
    fig_price(p)
    hol_stats = fig_holiday(p)
    stl_res = fig_stl(s)
    an_stats = fig_anomalies(s)

    # ---- signal metrics -------------------------------------------------
    periods = hu.dominant_periods(s, top_n=6)
    strength_total = hu.seasonal_strength(s, 7)
    strength_cat = {c: hu.seasonal_strength(
        p[p.category_name == c].groupby("date").sales_revenue.sum(), 7)
        for c in CAT_ORDER}
    strength_store = {int(sid): hu.seasonal_strength(
        p[p.store_id == sid].groupby("date").sales_revenue.sum(), 7)
        for sid in [1, 2, 3]}

    # price-quantity association (NOT causal elasticity): unit_price is derived
    # as sales_revenue/sales_qty, so qty appears in both variables and the
    # correlation is descriptive only. No exogenous price exists in this dataset.
    corr = {}
    for c in CAT_ORDER:
        d = p[p.category_name == c]
        lq, lp = np.log(d.sales_qty + 1), np.log(d.unit_price)
        corr[c] = round(float(np.corrcoef(lq, lp)[0, 1]), 3)

    metrics = {
        "n_days": int(s.shape[0]),
        "date_range": [str(s.index.min().date()), str(s.index.max().date())],
        "total_revenue": float(s.sum()),
        "dominant_periods_days": [round(per, 1) for per, _ in periods],
        "seasonal_strength_total": round(strength_total, 3),
        "seasonal_strength_category": strength_cat,
        "seasonal_strength_store": strength_store,
        "price_qty_corr": corr,
        "holiday_stats": hol_stats,
        "anomaly_stats": an_stats,
    }
    (REP / "signal_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print("wrote", REP / "signal_metrics.json")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()