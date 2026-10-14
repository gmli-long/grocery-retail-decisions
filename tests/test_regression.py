"""Minimal regression tests for the three challenges.

These tests do NOT re-run the heavy modelling pipelines. They validate the
*machine-readable artifacts* (metrics JSON) and the portability/word-choice
contracts that the review flagged as credibility risks, so a regress is caught
cheaply. Stdlib only — no matplotlib/scipy/statsmodels import required.

Run from the repo root with either:

    python -m unittest discover -s tests -v
    pytest -q
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent

CH01 = ROOT / "challenge_01_spaghetti_schema"
CH02 = ROOT / "challenge_02_errors_integrity"
CH03 = ROOT / "challenge_03_data_signal"

CH02_METRICS = CH02 / "reports" / "metrics.json"
CH02_AUDIT_LOG = CH02 / "data" / "clean" / "audit_log.csv"
CH03_SIGNAL = CH03 / "reports" / "signal_metrics.json"
CH03_FORECAST = CH03 / "reports" / "forecast_metrics.json"


def _load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Challenge 01 — config portability (#17)
# ---------------------------------------------------------------------------
class TestChallenge01Config(unittest.TestCase):
    def _import_config(self):
        sys.path.insert(0, str(CH01))
        if "config" in sys.modules:
            importlib.reload(sys.modules["config"])
        else:
            import config  # noqa: F401
        return sys.modules["config"]

    def test_default_data_dir_is_non_empty(self):
        cfg = self._import_config()
        self.assertTrue(cfg.DEFAULT_DATA_DIR, "DEFAULT_DATA_DIR must be defined")

    def test_env_var_overrides_default_data_dir(self):
        self._import_config()
        with mock.patch.dict(os.environ, {"CHALLENGE_01_DATA_DIR": "X:/override"}):
            cfg = importlib.reload(sys.modules["config"])
        self.assertEqual(cfg.DEFAULT_DATA_DIR, "X:/override")
        importlib.reload(sys.modules["config"])  # restore to real environment


# ---------------------------------------------------------------------------
# Challenge 02 — data quality invariants (#24 wording, integrity)
# ---------------------------------------------------------------------------
class TestChallenge02Metrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_json(CH02_METRICS)

    def test_validation_passed(self):
        self.assertTrue(self.m["validation_passed"])
        for name, ok in self.m["validation"].items():
            self.assertTrue(ok, f"validation flag '{name}' must be True")

    def test_cleaning_reduces_revenue(self):
        # The x100 corruption and x1000 qty outliers are the only sources of
        # spurious revenue; cleaning them must lower the total.
        self.assertLess(self.m["revenue_clean"], self.m["revenue_raw"])

    def test_row_count_is_consistent(self):
        self.assertEqual(
            self.m["n_sales_clean"],
            self.m["n_sales_raw"] - self.m["rows_dropped"],
        )

    def test_product_id_impute_wording_is_not_causal_uniform(self):
        # #24: product_id is independent but NOT uniformly distributed.
        bad = "uniform iid"
        for rec in self.m["change_log"]:
            self.assertNotIn(bad, rec["rationale"].lower())
        self.assertNotIn(bad, CH02_AUDIT_LOG.read_text(encoding="utf-8").lower())


# ---------------------------------------------------------------------------
# Challenge 03 — signal: descriptive (non-causal) price-quantity association (#42)
# ---------------------------------------------------------------------------
class TestChallenge03Signal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = _load_json(CH03_SIGNAL)

    def test_price_qty_corr_key_used_not_elasticity(self):
        self.assertIn("price_qty_corr", self.s)
        self.assertNotIn("price_elasticity_corr", self.s)
        # source must write the corrected key
        src = (CH03 / "scripts" / "run_eda.py").read_text(encoding="utf-8")
        self.assertIn('"price_qty_corr"', src)
        self.assertNotIn('"price_elasticity_corr"', src)

    def test_seasonal_strength_in_unit_interval(self):
        strengths = [self.s["seasonal_strength_total"]]
        strengths += list(self.s["seasonal_strength_category"].values())
        strengths += list(self.s["seasonal_strength_store"].values())
        for v in strengths:
            self.assertTrue(0.0 <= v <= 1.0, f"seasonal strength {v} outside [0,1]")

    def test_dominant_periods_include_weekly_and_annual(self):
        periods = self.s["dominant_periods_days"]
        self.assertTrue(any(abs(p - 365) < 3 for p in periods), "annual cycle missing")
        self.assertTrue(any(abs(p - 7) < 1 for p in periods), "weekly cycle missing")


# ---------------------------------------------------------------------------
# Challenge 03 — forecast: honest model ordering
# ---------------------------------------------------------------------------
class TestChallenge03Forecast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = _load_json(CH03_FORECAST)

    def test_model_ordering_is_honest(self):
        total = self.f["total"]
        mape = {
            "sarimax": total["sarimax"]["MAPE"],
            "sarima": total["sarima"]["MAPE"],
            "seasonal_naive": total["seasonal_naive"]["MAPE"],
        }
        self.assertLess(mape["sarimax"], mape["sarima"])
        self.assertLess(mape["sarima"], mape["seasonal_naive"])

    def test_metrics_are_finite_non_negative(self):
        import math
        total = self.f["total"]
        for model in ("persistence", "seasonal_naive", "sarima", "sarimax"):
            for metric in ("MAE", "RMSE", "MAPE"):
                v = total[model][metric]
                self.assertTrue(math.isfinite(v) and v >= 0, f"{model}.{metric}={v}")


if __name__ == "__main__":
    unittest.main(verbosity=2)