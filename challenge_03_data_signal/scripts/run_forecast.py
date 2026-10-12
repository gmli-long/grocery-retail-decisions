"""Challenge 03 — interpretable SARIMA/SARIMAX forecasting + baselines.

Trains on 2018–2021, tests on 2022 (a full unseen year). Forecasts the business
hierarchy at three levels: total, per-category, per-store. The headline model is
SARIMAX with calendar exog (holiday + annual Fourier); SARIMA (weekly-only) and
two naive baselines anchor the comparison so the 'external factor' gain is honest.
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

import helper_utils as hu          # noqa: E402
import forecast as fc               # noqa: E402

FIG = hu.FIG
REP = hu.REP
TRAIN_END = pd.Timestamp("2021-12-31")

NAVY = "#1b4f72"; BLUE = "#2874a6"; AMBER = "#e67e22"; GREY = "#9aa4b0"
GREEN = "#1e8449"

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 130, "font.size": 9,
    "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False,
})

CAT_ORDER = ["Beverages", "Bakery", "Meat", "Produce"]
STORE_LABEL = {1: "Seattle (L)", 2: "Portland (M)", 3: "Boise (S)"}


def series_category(p):
    return {c: p[p.category_name == c].groupby("date").sales_revenue.sum()
            for c in CAT_ORDER}


def series_store(p):
    return {STORE_LABEL[s]: p[p.store_id == s].groupby("date").sales_revenue.sum()
            for s in [1, 2, 3]}


def plot_total(res, save_path):
    test = res["test"]
    fdf = res["forecast_df"]
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(test.index, test.values, color=NAVY, lw=1.1, label="actual")
    ax.plot(fdf.index, fdf["forecast"], color=AMBER, lw=1.1, label="SARIMAX forecast")
    ax.fill_between(fdf.index, fdf["lower"], fdf["upper"], color=AMBER, alpha=0.18,
                    label="95% CI")
    ax.set_ylabel("Revenue ($)")
    ax.set_title("2022 daily revenue — SARIMAX vs actual  "
                 f"(MAPE {res['sarimax']['MAPE']:.1f}%; SARIMA {res['sarima']['MAPE']:.1f}%)")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", save_path)


def plot_hierarchy(panel_metrics, save_path):
    """Naive -> SARIMA -> SARIMAX MAPE across segments (three-bar comparison)."""
    df = panel_metrics.dropna(subset=["sarimax_MAPE"]).copy()
    df = df.sort_values("sarimax_MAPE")
    y = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(9.0, 3.8))
    ax.barh(y + 0.25, df["naive_MAPE"], height=0.22, color=GREY, label="seasonal naive")
    ax.barh(y, df["sarima_MAPE"], height=0.22, color=BLUE, label="SARIMA (weekly)")
    ax.barh(y - 0.25, df["sarimax_MAPE"], height=0.22, color=AMBER, label="SARIMAX (+ holiday/annual)")
    ax.set_yticks(y); ax.set_yticklabels(df["name"])
    ax.invert_yaxis()
    ax.set_xlabel("MAPE (%)")
    ax.set_title("Forecast error by segment (lower is better)")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", save_path)


def main():
    p = hu.build_panel()

    # ---- total -----------------------------------------------------------
    s_total = hu.daily_total(p)
    res = fc.evaluate_series(s_total, TRAIN_END, m=7, verbose=True)
    plot_total(res, FIG / "fig10_forecast_total.png")

    # ---- category + store panels ----------------------------------------
    cat = series_category(p)
    cat_df = fc.evaluate_panels(cat, TRAIN_END, m=7)
    cat_df.insert(0, "level", "category")

    sto = series_store(p)
    sto_df = fc.evaluate_panels(sto, TRAIN_END, m=7)
    sto_df.insert(0, "level", "store")

    plot_hierarchy(pd.concat([cat_df, sto_df], ignore_index=True),
                   FIG / "fig11_hierarchy_mape.png")

    # ---- seasonal strength (interpretability) ----------------------------
    strength = {
        "Beverages": hu.seasonal_strength(cat["Beverages"], 7),
        "Bakery": hu.seasonal_strength(cat["Bakery"], 7),
        "Meat": hu.seasonal_strength(cat["Meat"], 7),
        "Produce": hu.seasonal_strength(cat["Produce"], 7),
        "Seattle": hu.seasonal_strength(sto["Seattle (L)"], 7),
        "Portland": hu.seasonal_strength(sto["Portland (M)"], 7),
        "Boise": hu.seasonal_strength(sto["Boise (S)"], 7),
    }
    fig, ax = plt.subplots(figsize=(8.0, 3.0))
    names = list(strength); vals = [strength[n] for n in names]
    colors = [GREEN if n in CAT_ORDER else NAVY for n in names]
    ax.bar(names, vals, color=colors, alpha=0.85)
    ax.set_ylim(0, 0.5)
    ax.set_ylabel("Seasonal strength (weekly)")
    ax.set_title("Seasonal strength by segment (STL)")
    for i, v in enumerate(vals):
        ax.text(i, v + 0.008, f"{v:.2f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fig12_seasonal_strength.png", bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / "fig12_seasonal_strength.png")

    # ---- persist metrics ------------------------------------------------
    payload = {
        "train_end": str(TRAIN_END.date()),
        "total": {k: res[k] for k in ["persistence", "seasonal_naive", "sarima",
                                      "sarimax", "sarima_aic", "sarimax_aic"]},
        "category": cat_df.to_dict(orient="records"),
        "store": sto_df.to_dict(orient="records"),
        "seasonal_strength": strength,
    }
    (REP / "forecast_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("wrote", REP / "forecast_metrics.json")
    print(json.dumps({k: v for k, v in payload.items() if k in ("total", "seasonal_strength")},
                     indent=2))


if __name__ == "__main__":
    main()