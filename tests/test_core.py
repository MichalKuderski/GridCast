"""Forecasting invariants; synthetic inputs isolate timing from downloaded data."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gridcast.core import interval_radius, make_features, metrics


class FeatureAvailabilityTest(unittest.TestCase):
    def setUp(self):
        self.index = pd.date_range("2024-02-01", "2024-03-12 23:00", freq="h", tz="UTC")
        self.y = pd.Series(20000 + np.arange(len(self.index)) * .1, index=self.index)

    def test_all_24_horizons_ignore_actuals_at_or_after_origin(self):
        # The day spans the US spring DST transition, so calendar features are
        # also exercised without changing the UTC forecast horizon.
        origin = pd.Timestamp("2024-03-10", tz="UTC")
        targets = pd.date_range(origin, periods=24, freq="h")
        expected = make_features(self.y).loc[targets]
        altered = self.y.copy()
        altered.loc[origin:] = 9000000
        assert_frame_equal(expected, make_features(altered).loc[targets])
        self.assertFalse(expected.isna().any().any())

    def test_unobserved_future_target_day_does_not_require_imputation(self):
        origin = pd.Timestamp("2024-03-10", tz="UTC")
        targets = pd.date_range(origin, periods=24, freq="h")
        expected = make_features(self.y).loc[targets]
        future_unknown = self.y.copy()
        future_unknown.loc[origin:] = np.nan
        assert_frame_equal(expected, make_features(future_unknown).loc[targets])

    def test_last_horizon_lag24_uses_last_preorigin_observation(self):
        origin = pd.Timestamp("2024-03-10", tz="UTC")
        last = origin + pd.Timedelta(hours=23)
        x = make_features(self.y)
        self.assertEqual(self.y.loc[origin - pd.Timedelta(hours=1)], x.loc[last, "lag_24"])

    def test_missing_or_duplicate_hours_fail(self):
        for invalid in (self.y.drop(self.index[10]), pd.concat([self.y, self.y.iloc[:1]])):
            with self.subTest(length=len(invalid)), self.assertRaises(ValueError):
                make_features(invalid)


class ScoreAndIntervalTest(unittest.TestCase):
    def test_metrics_reconcile_to_hand_calculation(self):
        result = metrics([10, 20, 30], [8, 23, 35])
        self.assertEqual(3, result["N"])
        self.assertAlmostEqual(10 / 3, result["MAE_MW"])
        self.assertAlmostEqual(np.sqrt(38 / 3), result["RMSE_MW"])
        self.assertAlmostEqual(100 * 10 / 60, result["WAPE_pct"])
        self.assertAlmostEqual(2, result["Bias_MW"])
        self.assertAlmostEqual(100 * ((2 / 10 + 3 / 20 + 5 / 30) / 3), result["MAPE_pct"])

    def test_metrics_reject_broadcasting_and_undefined_denominators(self):
        cases = [([10, 20], [10]), ([10, 20], [[10], [20]]),
                 ([], []), ([0, 20], [10, 20]), ([10, np.nan], [10, 20]),
                 ([10, 20], [10, np.inf])]
        for actual, forecast in cases:
            with self.subTest(actual=actual, forecast=forecast), self.assertRaises(ValueError):
                metrics(actual, forecast)

    def test_interval_uses_absolute_finite_sample_order_statistic(self):
        # ceil((n+1)*0.8)=4; interpolation would incorrectly return3.4.
        self.assertEqual(4, interval_radius([-1, 2, -3, 4], .8))
        self.assertEqual(8, interval_radius(list(range(1, 10)), .8))

    def test_invalid_interval_inputs_fail(self):
        for residuals, level in [([], .8), ([np.nan], .8), ([[1, 2]], .8),
                                 ([1, 2], 0), ([1, 2], 1), ([1, 2], np.nan)]:
            with self.subTest(residuals=residuals, level=level), self.assertRaises(ValueError):
                interval_radius(residuals, level)


if __name__ == "__main__":
    unittest.main()
