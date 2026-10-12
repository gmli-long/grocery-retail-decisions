"""Challenge 03 — interpretable, reproducible SARIMA/SARIMAX forecasting.

Design choices (documented in docs/architecture.md):
  * daily series -> weekly seasonal order (s=7), the dominant market cycle
  * SARIMA(1,1,1)(1,0,1)[7]   — weekly-only baseline
  * SARIMAX + calendar exog    — adds is_holiday + 2 annual Fourier pairs, so the
                                 model *sees* holiday & annual structure the weekly
                                 term cannot reach
  * two naive baselines (persistence, seasonal-naive) anchor the comparison
  * MAPE reported only on non-zero days
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from helper_utils import calendar_exog, forecast_metrics

ARIMA_ORDER = (1, 1, 1)
S_ORDER = (1, 0, 1, 7)          # (P, D, Q, s)


def _ensure_daily(s: pd.Series) -> pd.Series:
    s = s.copy()
    if s.index.freq is None:
        s.index = pd.DatetimeIndex(s.index)
        s = s.asfreq("D")
    return s


# --------------------------------------------------------------------------- #
# baselines
# --------------------------------------------------------------------------- #
def persistence_naive(train: pd.Series, h: int) -> np.ndarray:
    return np.full(h, train.iloc[-1])


def seasonal_naive(train: pd.Series, h: int, m: int = 7) -> np.ndarray:
    last = train.iloc[-m:].to_numpy()
    return np.resize(last, h)


# --------------------------------------------------------------------------- #
# SARIMA / SARIMAX
# --------------------------------------------------------------------------- #
def fit_sarimax(y: pd.Series, exog: pd.DataFrame | None = None,
                order=ARIMA_ORDER, seasonal_order=S_ORDER):
    model = SARIMAX(y.astype(float), exog=exog, order=order,
                    seasonal_order=seasonal_order,
                    enforce_stationarity=False, enforce_invertibility=False)
    return model.fit(disp=False, maxiter=500)


def sarimax_forecast(results, h: int, exog: pd.DataFrame | None = None,
                     alpha: float = 0.05) -> pd.DataFrame:
    fc = results.get_forecast(h, exog=exog)
    mean = fc.predicted_mean
    ci = fc.conf_int(alpha=alpha)
    return pd.DataFrame({
        "forecast": mean.to_numpy(),
        "lower": ci.iloc[:, 0].to_numpy(),
        "upper": ci.iloc[:, 1].to_numpy(),
    }, index=mean.index)


# --------------------------------------------------------------------------- #
# end-to-end evaluation
# --------------------------------------------------------------------------- #
def evaluate_series(series: pd.Series, train_end: pd.Timestamp, m: int = 7,
                    verbose: bool = True) -> dict:
    """Split at train_end; compare persistence, seasonal-naive, SARIMA, SARIMAX."""
    series = _ensure_daily(series)
    train = series.loc[:train_end]
    test = series.loc[series.index > train_end]
    h = len(test)
    if h == 0:
        raise ValueError("empty test window")

    pers = persistence_naive(train, h)
    naive = seasonal_naive(train, h, m) if len(train) >= m else pers

    # weekly-only SARIMA
    res_plain = fit_sarimax(train)
    fc_plain = sarimax_forecast(res_plain, h)

    # SARIMAX with calendar exog (holiday + annual Fourier)
    exog = calendar_exog(series.index)
    res_ex = fit_sarimax(train, exog=exog.loc[train.index])
    fc_ex = sarimax_forecast(res_ex, h, exog=exog.loc[test.index])

    out = {
        "n_train": int(len(train)),
        "n_test": int(h),
        "persistence": forecast_metrics(test, pers),
        "seasonal_naive": forecast_metrics(test, naive),
        "sarima": forecast_metrics(test, fc_plain["forecast"]),
        "sarimax": forecast_metrics(test, fc_ex["forecast"]),
        "sarima_aic": float(res_plain.aic),
        "sarimax_aic": float(res_ex.aic),
        "forecast_df": fc_ex.assign(date=test.index),
        "test": test,
    }
    if verbose:
        print(f"  train={len(train)} test={h} | "
              f"SARIMA MAPE={out['sarima']['MAPE']:.1f}% -> "
              f"SARIMAX MAPE={out['sarimax']['MAPE']:.1f}% "
              f"(naive={out['seasonal_naive']['MAPE']:.1f}%) "
              f"AIC={out['sarimax_aic']:.1f}")
    return out


def evaluate_panels(series_dict: dict[str, pd.Series], train_end: pd.Timestamp,
                    m: int = 7) -> pd.DataFrame:
    """Fit SARIMAX (calendar exog) per named series; return a metrics table."""
    rows = []
    for name, s in series_dict.items():
        try:
            r = evaluate_series(s, train_end, m, verbose=False)
        except Exception as exc:  # pragma: no cover - keep pipeline resilient
            rows.append({"name": name, "sarimax_MAPE": None, "error": str(exc)})
            continue
        rows.append({
            "name": name,
            "sarima_MAPE": r["sarima"]["MAPE"],
            "sarimax_MAPE": r["sarimax"]["MAPE"],
            "sarimax_RMSE": r["sarimax"]["RMSE"],
            "sarimax_MAE": r["sarimax"]["MAE"],
            "naive_MAPE": r["seasonal_naive"]["MAPE"],
            "sarimax_aic": r["sarimax_aic"],
            "n_test": r["n_test"],
        })
    return pd.DataFrame(rows)