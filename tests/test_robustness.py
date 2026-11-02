"""Adversarial ingestion and availability checks beyond the saved row contract."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gridcast.core import clean_demand, make_features
from audit_robustness import available_batch


class AdversarialIngestionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = pd.read_csv(ROOT / "data/raw/eia_pjm_hourly_2019_2025.csv")

    def test_rejects_wrong_region_interval_and_duplicate_grid(self):
        cases = []
        wrong_ba = self.raw.copy()
        wrong_ba.loc[100, "BalancingAuthority"] = "MISO"
        cases.append(wrong_ba)
        wrong_end = self.raw.copy()
        wrong_end.loc[100, "IntervalEndUTC"] = wrong_end.loc[100, "DateTimeUTC"]
        cases.append(wrong_end)
        duplicate = self.raw.copy()
        duplicate.iloc[-1] = duplicate.iloc[-2]
        cases.append(duplicate)
        for n, frame in enumerate(cases):
            with self.subTest(case=n), patch("gridcast.core.pd.read_csv", return_value=frame), self.assertRaises(ValueError):
                clean_demand(ROOT)

    def test_future_source_values_and_quality_flags_cannot_change_issued_day_features(self):
        origin = pd.Timestamp("2025-03-09", tz="UTC")
        baseline, _ = clean_demand(ROOT)
        changed = self.raw.copy()
        future = pd.to_datetime(changed.DateTimeUTC, utc=True) >= origin
        changed.loc[future, "OriginalDemandMWh"] = 9999999.
        changed.loc[future, "AdjustedDemandMWh"] = 1111111.
        changed.loc[future, "ImputedDemandMWh"] = 2222222.
        with patch("gridcast.core.pd.read_csv", return_value=changed):
            altered, _ = clean_demand(ROOT)
        targets = pd.date_range(origin, periods=24, freq="h")
        assert_frame_equal(make_features(baseline.FeatureInputMW).loc[targets],
                           make_features(altered.FeatureInputMW).loc[targets])


class ReleaseAvailabilityTest(unittest.TestCase):
    def setUp(self):
        self.origin = pd.Timestamp("2025-11-02", tz="UTC")
        index = pd.date_range(self.origin - pd.Timedelta(hours=500),
                              self.origin + pd.Timedelta(hours=48), freq="h")
        self.y = pd.Series(100000 + np.arange(len(index)), index=index, dtype=float)

    def test_delayed_batch_ignores_values_that_have_not_been_released(self):
        expected = available_batch(self.y, self.origin, 1)
        changed = self.y.copy()
        changed.loc[self.origin - pd.Timedelta(hours=1):] = 9999999
        assert_frame_equal(expected, available_batch(changed, self.origin, 1))
        self.assertEqual(24, len(expected))
        self.assertFalse(expected.isna().any().any())

    def test_one_hour_delay_affects_only_last_horizon_and_latest_hour_is_not_read(self):
        immediate = available_batch(self.y, self.origin, 0)
        delayed = available_batch(self.y, self.origin, 1)
        assert_frame_equal(immediate.iloc[:23], delayed.iloc[:23])
        self.assertEqual(self.y.loc[self.origin - pd.Timedelta(hours=2)], delayed.iloc[-1].lag_24)
        self.assertNotEqual(immediate.iloc[-1].lag_24, delayed.iloc[-1].lag_24)

    def test_zero_delay_batch_matches_full_history_features(self):
        expected = make_features(self.y).loc[self.origin:self.origin + pd.Timedelta(hours=23)]
        actual = available_batch(self.y, self.origin, 0)
        np.testing.assert_allclose(expected.to_numpy(), actual.to_numpy(), atol=1e-7, rtol=0)


if __name__ == "__main__":
    unittest.main()
