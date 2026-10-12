"""Challenge 03 — Data → Signal. Core helpers.

Deterministic, dependency-light utilities shared by the pipeline, the forecast
module and the notebooks:

  * load_raw / build_panel  — ingest the four flat files into a tidy daily panel
  * us_holiday_calendar      — reproducible US federal + retail-relevant holidays
  * signal metrics           — seasonal strength, dominant-period (periodogram)
  * stl_decompose            — robust trend / seasonal / residual split
  * detect_anomalies         — unsupervised spike/flat-spot detection on residuals
  * forecast_metrics         — MAE / RMSE / MAPE

No injected error is expected: this dataset is clean by construction. The value of
Challenge 03 is turning that trustworthy base into *signal*, so every function here
favours explicitness (named columns, integer flags) over magic.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
PROC = BASE / "data" / "processed"
FIG = BASE / "reports" / "figures"
REP = BASE / "reports"
FIG.mkdir(parents=True, exist_ok=True)
PROC.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# 1. Ingest
# --------------------------------------------------------------------------- #
def load_raw() -> dict[str, pd.DataFrame]:
    """Load the four flat files with parsed dates."""
    dates = pd.read_csv(RAW / "dates.csv", parse_dates=["date"])
    sales = pd.read_csv(RAW / "sales.csv", parse_dates=["date"])
    categories = pd.read_csv(RAW / "categories.csv")
    stores = pd.read_csv(RAW / "stores.csv")
    return {"dates": dates, "sales": sales, "categories": categories, "stores": stores}


ISO_WEEKDAY = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}


def build_panel() -> pd.DataFrame:
    """Merge sales with calendar, category and store attributes.

    Adds deterministic features: unit_price, is_weekend, holiday flags and
    cyclic encodings used throughout the signal work.
    """
    d = load_raw()
    hl = us_holiday_calendar(2018, 2022).set_index("date")

    p = (
        d["sales"]
        .merge(d["dates"], on="date", how="left")
        .merge(d["categories"], on="category_id", how="left")
        .merge(d["stores"], on="store_id", how="left")
    )
    p = p.rename(columns={"name": "category_name"})
    p["unit_price"] = p["sales_revenue"] / p["sales_qty"]
    p["is_weekend"] = p["dow"].isin([5, 6]).astype(int)
    p["day_name"] = p["dow"].map(ISO_WEEKDAY)
    p["is_holiday"] = p["date"].isin(hl.index).astype(int)
    p["holiday_name"] = p["date"].map(hl["name"])

    # cyclic date encodings (sin/cos) — one full cycle = 1 week / 1 year
    p["week_sin"] = np.sin(2 * np.pi * p["dow"] / 7)
    p["week_cos"] = np.cos(2 * np.pi * p["dow"] / 7)
    p["year_sin"] = np.sin(2 * np.pi * p["dom"] / 365)
    p["year_cos"] = np.cos(2 * np.pi * p["dom"] / 365)
    return p


def daily_total(panel: pd.DataFrame | None = None, value: str = "sales_revenue") -> pd.Series:
    """Aggregate the panel to a daily total (all stores x categories)."""
    if panel is None:
        panel = build_panel()
    s = panel.groupby("date")[value].sum().sort_index()
    s.index.name = "date"
    return s


# --------------------------------------------------------------------------- #
# 2. Holiday calendar (reproducible, no external dependency)
# --------------------------------------------------------------------------- #
def _nth_weekday(year: int, month: int, weekday: int, n: int) -> pd.Timestamp:
    """The n-th *weekday* (0=Mon) of a given month."""
    first = pd.Timestamp(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + pd.Timedelta(days=offset + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> pd.Timestamp:
    """The last *weekday* of a given month."""
    last = pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(0)
    offset = (last.weekday() - weekday) % 7
    return last - pd.Timedelta(days=offset)


def _observed(dt: pd.Timestamp) -> pd.Timestamp:
    """US 'observed' rule: Sat -> Fri, Sun -> Mon."""
    if dt.weekday() == 5:
        return dt - pd.Timedelta(days=1)
    if dt.weekday() == 6:
        return dt + pd.Timedelta(days=1)
    return dt


def us_holiday_calendar(start: int, end: int) -> pd.DataFrame:
    """US federal holidays (+ retail-relevant Black Friday / Christmas Eve).

    Federal rules follow the OPM observed-day convention; the two non-federal
    additions are flagged explicitly since they carry heavy grocery signal.
    """
    rows = []
    for y in range(start, end + 1):
        fed = [
            ("New Year's Day", _observed(pd.Timestamp(y, 1, 1))),
            ("MLK Day", _nth_weekday(y, 1, 0, 3)),
            ("Presidents' Day", _nth_weekday(y, 2, 0, 3)),
            ("Memorial Day", _last_weekday(y, 5, 0)),
            ("Independence Day", _observed(pd.Timestamp(y, 7, 4))),
            ("Labor Day", _nth_weekday(y, 9, 0, 1)),
            ("Columbus Day", _nth_weekday(y, 10, 0, 2)),
            ("Veterans Day", _observed(pd.Timestamp(y, 11, 11))),
            ("Thanksgiving", _nth_weekday(y, 11, 3, 4)),
            ("Christmas Day", _observed(pd.Timestamp(y, 12, 25))),
        ]
        # Juneteenth became a federal holiday in 2021
        if y >= 2021:
            fed.append(("Juneteenth", _observed(pd.Timestamp(y, 6, 19))))
        # retail-relevant, non-federal
        fed.append(("Black Friday", _nth_weekday(y, 11, 3, 4) + pd.Timedelta(days=1)))
        fed.append(("Christmas Eve", pd.Timestamp(y, 12, 24)))
        for name, dt in fed:
            rows.append((dt, name))
    df = pd.DataFrame(rows, columns=["date", "name"]).drop_duplicates().sort_values("date")
    # observed-day rules can pile two holidays onto one date (e.g. Christmas Day
    # observed on Dec 24 = Christmas Eve) — collapse to a single label per date.
    df = df.groupby("date", as_index=False)["name"].agg(lambda x: " / ".join(sorted(set(x))))
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 3. Signal metrics
# --------------------------------------------------------------------------- #
def calendar_exog(dates) -> pd.DataFrame:
    """Deterministic exogenous regressors for SARIMAX.

    Captures the two 'external factor' families that pure weekly seasonality
    cannot reach: the *holiday* shock (0/1 flag) and the *annual* cycle encoded
    as two Fourier harmonic pairs. Weekend/day-of-week is left to the seasonal
    AR component to avoid collinearity.
    """
    idx = pd.DatetimeIndex(pd.to_datetime(dates))
    hol = us_holiday_calendar(idx.min().year, idx.max().year)
    hol_dates = pd.to_datetime(hol["date"]).dt.normalize()
    doy = idx.dayofyear.to_numpy()
    year_len = np.where(idx.is_leap_year, 366, 365)
    ang = 2 * np.pi * doy / year_len
    return pd.DataFrame({
        "is_holiday": idx.normalize().isin(hol_dates).astype(int),
        "annual_sin1": np.sin(ang),
        "annual_cos1": np.cos(ang),
        "annual_sin2": np.sin(2 * ang),
        "annual_cos2": np.cos(2 * ang),
    }, index=idx)


def detrend(series: pd.Series) -> pd.Series:
    """Remove linear trend + mean, for periodogram analysis."""
    x = np.arange(len(series))
    s = series.astype(float).to_numpy()
    lo = np.polyfit(x, s, 1)
    return pd.Series(s - np.polyval(lo, x), index=series.index)


def dominant_periods(series: pd.Series, top_n: int = 6, min_period: int = 2,
                     max_period: int = 400) -> list[tuple[float, float]]:
    """Top periodicities (day period, power) from a periodogram.

    Returns [(period_in_days, normalised_power)] sorted by power, excluding the
    trivial DC/long-trend component.
    """
    from scipy.signal import periodogram
    y = detrend(series).to_numpy()
    n = len(y)
    f, Pxx = periodogram(y, detrend=False)
    periods = 1.0 / f[1:]  # drop f=0 (infinite period)
    power = Pxx[1:]
    mask = (periods >= min_period) & (periods <= max_period)
    periods, power = periods[mask], power[mask]
    # take the strongest local maxima instead of raw top-k (avoids harmonics)
    order = np.argsort(power)[::-1]
    picked, out = [], []
    for i in order:
        p = periods[i]
        if any(abs(p - q) / max(q, 1e-9) < 0.05 for q in picked):
            continue
        out.append((float(p), float(power[i] / power.max())))
        picked.append(float(p))
        if len(out) == top_n:
            break
    return out


def seasonal_strength(series: pd.Series, period: int) -> float:
    """STL-based seasonal strength in [0, 1]; 1 = perfectly seasonal."""
    res = stl_decompose(series, period)
    var_s = np.var(res.seasonal)
    var_r = np.var(res.resid)
    return float(max(0.0, 1.0 - var_r / (var_s + var_r + 1e-12)))


def stl_decompose(series: pd.Series, period: int = 7):
    """Robust STL decomposition; returns the fitted DecomposeResult."""
    from statsmodels.tsa.seasonal import STL
    return STL(series.astype(float), period=period, robust=True).fit()


# --------------------------------------------------------------------------- #
# 4. Unsupervised anomaly / holiday detection
# --------------------------------------------------------------------------- #
def detect_anomalies(series: pd.Series, period: int = 7, k: float = 3.5) -> pd.DataFrame:
    """Flag days whose STL residual deviates from the seasonal baseline by > k sigma.

    A positive Z-score marks an uplift spike, a negative one a suppression —
    the natural signature of holidays / demand shocks, detected with *no* holiday
    labels. Callers cross-reference against the calendar to validate.
    """
    res = stl_decompose(series, period)
    resid = res.resid.dropna()
    mu, sd = resid.mean(), resid.std()
    z = (resid - mu) / sd
    out = pd.DataFrame({
        "date": resid.index,
        "observed": series.loc[resid.index].to_numpy(),
        "expected": (res.trend + res.seasonal).loc[resid.index].to_numpy(),
        "residual": resid.to_numpy(),
        "zscore": z.to_numpy(),
    })
    out["is_anomaly"] = out["zscore"].abs() > k
    out["direction"] = np.where(out["zscore"] > k, "uplift",
                                np.where(out["zscore"] < -k, "suppression", "normal"))
    return out


# --------------------------------------------------------------------------- #
# 5. Forecast evaluation
# --------------------------------------------------------------------------- #
def forecast_metrics(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> dict[str, float]:
    """MAE, RMSE, MAPE on aligned arrays (MAPE in percent)."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    ok = yt != 0
    mae = float(np.mean(np.abs(yt - yp)))
    rmse = float(np.sqrt(np.mean((yt - yp) ** 2)))
    mape = float(np.mean(np.abs((yt[ok] - yp[ok]) / yt[ok])) * 100)
    return {"MAE": mae, "RMSE": rmse, "MAPE": mape}