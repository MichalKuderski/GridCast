"""Audit the pinned PJM ingestion and generated handoff without retraining models.

Run scripts/run_pipeline.py first. Recomputations here use saved per-hour rows,
not the project's metric helper, so reconciliation checks are independent.
"""

import hashlib
import json
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gridcast.core import causal_fill


class CausalInputFillTest(unittest.TestCase):
    def test_fill_uses_week_day_hour_in_order_and_preserves_observed_values(self):
        original = pd.Series(np.arange(400, dtype=float) + 1000,
                             index=pd.date_range("2025-01-01", periods=400, freq="h", tz="UTC"))
        incomplete = original.copy()
        incomplete.iloc[[5, 50, 200, 368]] = np.nan
        filled = causal_fill(incomplete)
        self.assertEqual(original.iloc[4], filled.iloc[5])
        self.assertEqual(original.iloc[26], filled.iloc[50])
        self.assertEqual(original.iloc[32], filled.iloc[200])
        self.assertEqual(filled.iloc[200], filled.iloc[368])
        np.testing.assert_array_equal(original[incomplete.notna()], filled[incomplete.notna()])
        # Filling changes only the feature copy; invalid scored actuals stay missing.
        self.assertEqual(4, int(incomplete.isna().sum()))

    def test_missing_initial_value_cannot_borrow_from_future(self):
        with self.assertRaises(ValueError):
            causal_fill(pd.Series([np.nan, 10., 20.]))


class PipelineContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_path = ROOT / "data/raw/eia_pjm_hourly_2019_2025.csv"
        cls.raw = pd.read_csv(cls.raw_path)
        cls.history = pd.read_csv(ROOT / "data/powerbi/FactDemand.csv")
        cls.forecasts = pd.read_csv(ROOT / "data/powerbi/FactForecast.csv")
        cls.history["DateTimeUTC"] = pd.to_datetime(cls.history.DateTimeUTC, utc=True)
        for column in ("DateTimeUTC", "ForecastOriginUTC"):
            cls.forecasts[column] = pd.to_datetime(cls.forecasts[column], utc=True)
        cls.summary = json.loads((ROOT / "outputs/run_summary.json").read_text())
        cls.scores = pd.read_csv(ROOT / "outputs/model_metrics.csv")

    def test_source_hash_time_mapping_and_unique_hourly_history(self):
        audit = json.loads((ROOT / "data/raw/eia_pjm_initial_audit.json").read_text())
        self.assertEqual(audit["csv_sha256"], hashlib.sha256(self.raw_path.read_bytes()).hexdigest())
        manifest = json.loads((ROOT / "data/raw/eia_pjm_manifest.json").read_text())
        self.assertEqual(audit["csv_sha256"], manifest["extracted_snapshot"]["sha256"])
        self.assertEqual({"PJM"}, set(self.raw.BalancingAuthority))
        begin = pd.to_datetime(self.raw.DateTimeUTC, utc=True)
        end = pd.to_datetime(self.raw.IntervalEndUTC, utc=True)
        self.assertTrue(((end - begin) == pd.Timedelta(hours=1)).all())
        expected = pd.date_range("2019-01-01", "2025-12-31 23:00", freq="h", tz="UTC")
        np.testing.assert_array_equal(expected, self.history.DateTimeUTC)
        self.assertFalse(self.history.DateTimeUTC.duplicated().any())
        self.assertEqual(61368, len(self.history))

    def test_scored_actuals_remain_missing_and_valid_original_values_are_preserved(self):
        h = self.history
        self.assertEqual(178, int(h.ActualMW.isna().sum()))
        self.assertEqual(167, int(self.raw.OriginalDemandMWh.isna().sum()))
        self.assertTrue(np.isfinite(h.FeatureInputMW).all())
        self.assertTrue((h.ActualMW.notna() == h.IsActualValid).all())
        valid = h.ActualMW.notna()
        np.testing.assert_allclose(h.loc[valid, "ActualMW"], h.loc[valid, "OriginalDemandMWh"], atol=0, rtol=0)
        np.testing.assert_allclose(h.loc[valid, "FeatureInputMW"], h.loc[valid, "ActualMW"], atol=0, rtol=0)
        manual = pd.to_datetime(["2020-04-10T03:00Z", "2020-07-13T22:00Z",
                                 "2020-07-28T16:00Z", "2020-07-29T20:00Z"], utc=True)
        self.assertTrue(h.loc[h.DateTimeUTC.isin(manual), "ActualMW"].isna().all())

    def test_forecast_grain_origins_horizons_and_split_coverage(self):
        f = self.forecasts
        self.assertFalse(f.duplicated(["DateTimeUTC", "Model", "Split"]).any())
        self.assertEqual({"validation": 43800, "calibration": 43920, "test": 43800, "future": 24},
                         f.groupby("Split").size().to_dict())
        self.assertTrue((f.ForecastOriginUTC == f.DateTimeUTC.dt.floor("D")).all())
        self.assertTrue((f.HorizonHours == f.DateTimeUTC.dt.hour + 1).all())
        self.assertTrue((f.HourUTC == f.DateTimeUTC.dt.hour).all())
        self.assertTrue((f.Date == f.DateTimeUTC.dt.strftime("%Y-%m-%d")).all())
        self.assertTrue(np.isfinite(f.ForecastMW).all())
        self.assertTrue((f.ForecastMW >= 0).all())
        by_day = f.groupby(["ForecastOriginUTC", "Model", "Split"]).size()
        self.assertTrue((by_day == 24).all())
        for split, year in (("validation", 2023), ("calibration", 2024), ("test", 2025), ("future", 2026)):
            self.assertEqual({year}, set(f.loc[f.Split == split, "DateTimeUTC"].dt.year))

    def test_actuals_reconcile_across_models_and_future_is_unscored(self):
        expected = self.history.set_index("DateTimeUTC").ActualMW
        historical = self.forecasts.loc[self.forecasts.Split != "future"]
        np.testing.assert_allclose(historical.ActualMW, historical.DateTimeUTC.map(expected),
                                   rtol=0, atol=0, equal_nan=True)
        future = self.forecasts.loc[self.forecasts.Split == "future"]
        self.assertTrue(future.ActualMW.isna().all())
        self.assertEqual({self.summary["selected_model"]}, set(future.Model))
        self.assertEqual(pd.Timestamp("2026-01-01", tz="UTC"), future.DateTimeUTC.min())
        self.assertEqual(set(range(1, 25)), set(future.HorizonHours))

    def test_metrics_recomputed_from_exported_rows_match_saved_scores(self):
        for record in self.scores.to_dict("records"):
            f = self.forecasts.loc[(self.forecasts.Model == record["Model"]) &
                                   (self.forecasts.Split == record["Split"]) & self.forecasts.ActualMW.notna()]
            a = f.ActualMW.to_numpy()
            e = f.ForecastMW.to_numpy() - a
            computed = {"MAE_MW": np.mean(np.abs(e)), "RMSE_MW": np.sqrt(np.mean(e ** 2)),
                        "WAPE_pct": 100 * np.sum(np.abs(e)) / np.sum(np.abs(a)),
                        "MAPE_pct": 100 * np.mean(np.abs(e / a)), "Bias_MW": np.mean(e)}
            with self.subTest(model=record["Model"], split=record["Split"]):
                self.assertEqual(record["N"], len(f))
                for key, value in computed.items():
                    self.assertAlmostEqual(record[key], value, delta=2e-6)
        test = self.scores.loc[self.scores.Split == "test"]
        self.assertEqual({8735}, set(test.N))
        selected = self.scores.loc[self.scores.Split == "validation"].sort_values(["MAE_MW", "Model"]).iloc[0].Model
        self.assertEqual(selected, self.summary["selected_model"])

    def test_horizon_intervals_use_only_calibration_and_match_test_summary(self):
        f = self.forecasts
        selected = self.summary["selected_model"]
        intended = (f.Model == selected) & f.Split.isin(["calibration", "test", "future"])
        self.assertTrue(f.loc[intended, ["Lower80MW", "Upper80MW"]].notna().all().all())
        self.assertTrue(f.loc[~intended, ["Lower80MW", "Upper80MW"]].isna().all().all())
        for horizon in range(1, 25):
            cal = f.loc[(f.Model == selected) & (f.Split == "calibration") &
                        (f.HorizonHours == horizon) & f.ActualMW.notna()]
            residuals = np.sort(np.abs(cal.ActualMW.to_numpy() - cal.ForecastMW.to_numpy()))
            rank = min(int(np.ceil((len(residuals) + 1) * .8)), len(residuals))
            radius = residuals[rank - 1]
            self.assertAlmostEqual(self.summary["interval_radius_by_horizon_MW"][str(horizon)], radius, delta=2e-6)
            target = f.loc[intended & (f.HorizonHours == horizon)]
            np.testing.assert_allclose(target.Lower80MW, np.maximum(0, target.ForecastMW - radius), rtol=0, atol=2e-6)
            np.testing.assert_allclose(target.Upper80MW, target.ForecastMW + radius, rtol=0, atol=2e-6)
        test = f.loc[(f.Model == selected) & (f.Split == "test") & f.ActualMW.notna()]
        coverage = ((test.ActualMW >= test.Lower80MW) & (test.ActualMW <= test.Upper80MW)).mean()
        self.assertAlmostEqual(self.summary["test_interval_coverage"], coverage)

    def test_dimension_keys_cover_facts_without_many_to_many_join(self):
        dates = pd.read_csv(ROOT / "data/powerbi/DimDate.csv")
        models = pd.read_csv(ROOT / "data/powerbi/DimModel.csv")
        self.assertFalse(dates.Date.duplicated().any())
        self.assertFalse(models.Model.duplicated().any())
        self.assertTrue(set(self.history.Date).issubset(set(dates.Date)))
        self.assertTrue(set(self.forecasts.Date).issubset(set(dates.Date)))
        self.assertEqual(set(self.forecasts.Model), set(models.Model))


if __name__ == "__main__":
    unittest.main()
