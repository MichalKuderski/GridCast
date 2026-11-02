"""Data contracts and time-safe feature engineering; no network side effects."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd


def causal_fill(series):
    """Fill historical feature inputs from prior week, then prior day, then last hour.

    Never replaces scored actuals. At each time reads only already-available values.
    """
    values = series.to_numpy(dtype=float, copy=True)
    for i in np.flatnonzero(~np.isfinite(values)):
        candidates = [values[i - lag] for lag in (168, 24, 1) if i >= lag and np.isfinite(values[i - lag])]
        if not candidates:
            raise ValueError("Cannot fill initial missing observation without prior history")
        values[i] = candidates[0]
    return pd.Series(values, index=series.index, name="FeatureInputMW")


def clean_demand(root: Path):
    """Audit EIA-reported PJM demand, mask EIA-flagged targets; causal feature fill."""
    raw_path = root / "data/raw/eia_pjm_hourly_2019_2025.csv"
    audit = json.loads((root / "data/raw/eia_pjm_initial_audit.json").read_text())
    if hashlib.sha256(raw_path.read_bytes()).hexdigest() != audit["csv_sha256"]:
        raise ValueError("Canonical source CSV checksum mismatch")
    raw = pd.read_csv(raw_path)
    if not (raw.BalancingAuthority == "PJM").all():
        raise ValueError("Unexpected balancing authority")
    idx = pd.DatetimeIndex(pd.to_datetime(raw.DateTimeUTC, utc=True))
    ends = pd.DatetimeIndex(pd.to_datetime(raw.IntervalEndUTC, utc=True))
    if not ((ends - idx) == pd.Timedelta(hours=1)).all():
        raise ValueError("Source interval is not exactly one hour")
    original = pd.to_numeric(raw.OriginalDemandMWh, errors="raise")
    adjusted = pd.to_numeric(raw.AdjustedDemandMWh, errors="raise")
    imputed = pd.to_numeric(raw.ImputedDemandMWh, errors="raise")
    invalid = original.isna() | ~np.isfinite(original) | (original <= 0) | imputed.notna() | (adjusted.notna() & original.notna() & (adjusted != original))
    # Four isolated training-period spikes reviewed against adjacent readings and
    # PJM's pre-2026 peak context. Inferred anomalies, not operator corrections.
    # Exact ledger in docs/anomaly_review.csv; never extrapolate a demand ceiling.
    manual_train_anomalies = pd.to_datetime(["2020-04-10T03:00Z", "2020-07-13T22:00Z", "2020-07-28T16:00Z", "2020-07-29T20:00Z"], utc=True)
    manual_mask = idx.isin(manual_train_anomalies)
    invalid = invalid | manual_mask
    demand = pd.DataFrame({"ActualMW": original.mask(invalid).to_numpy(), "OriginalDemandMWh": original.to_numpy(), "IsActualValid": (~invalid).to_numpy()}, index=idx).sort_index()
    expected = pd.date_range("2019-01-01", "2025-12-31 23:00", freq="h", tz="UTC")
    if demand.index.has_duplicates or not demand.index.equals(expected):
        raise ValueError("Demand UTC index must completely cover 2019–2025 without duplicates")
    demand.index.name = "DateTimeUTC"
    demand["FeatureInputMW"] = causal_fill(demand.ActualMW)
    annual = demand.groupby(demand.index.year).agg(Hours=("ActualMW", "size"), ValidActuals=("ActualMW", "count"), MinMW=("ActualMW", "min"), MaxMW=("ActualMW", "max"))
    quality = {"hourly_rows": len(demand), "missing_hours": 0, "duplicate_utc_keys": 0,
               "excluded_actual_values": int(invalid.sum()), "causally_filled_feature_inputs": int(invalid.sum()),
               "source_original_nulls": int(original.isna().sum()), "source_imputation_candidates": int(imputed.notna().sum()),
               "source_adjusted_differs_from_reported": int((adjusted.notna() & original.notna() & (adjusted != original)).sum()),
               "manually_excluded_training_spikes": int(manual_mask.sum()),
               "annual": annual.reset_index().to_dict(orient="records"),
               "first_utc": str(demand.index.min()), "last_utc": str(demand.index.max()),
               "aggregation": "original hourly MWh / 1 hour = mean MW; timestamps interval starts (source hour ending minus 1h)",
               "feature_fill": "invalid original → prior week168h, fallback24h, fallback1h; historical inputs only, targets remain missing"}
    return demand, quality


def make_features(y: pd.Series):
    """For target t in UTC day origin o, newest observed input is t−24h < o.

    Requires a complete, regular hourly index. Missing future y is allowed for
    the next 24 hours, because every feature reads yesterday or earlier.
    """
    if y.index.has_duplicates or not y.index.equals(pd.date_range(y.index.min(), y.index.max(), freq="h")):
        raise ValueError("Features require a complete unique hourly UTC index")
    local = y.index.tz_convert("America/New_York")
    x = pd.DataFrame(index=y.index)
    x["hour_local"] = local.hour
    x["weekday_local"] = local.day_of_week
    x["month"] = local.month
    x["weekend"] = (local.day_of_week >= 5).astype(int)
    x["utc_offset_hours"] = [t.utcoffset().total_seconds() / 3600 for t in local]
    for k in (1, 2, 3):
        x[f"hour_sin{k}"] = np.sin(2 * np.pi * local.hour * k / 24)
        x[f"hour_cos{k}"] = np.cos(2 * np.pi * local.hour * k / 24)
    for k in (1, 2):
        x[f"year_sin{k}"] = np.sin(2 * np.pi * local.day_of_year * k / 365.25)
        x[f"year_cos{k}"] = np.cos(2 * np.pi * local.day_of_year * k / 365.25)
    for lag in (24, 48, 168, 336):
        x[f"lag_{lag}"] = y.shift(lag)
    x["rolling_mean_24"] = y.shift(24).rolling(24).mean()
    x["rolling_mean_168"] = y.shift(24).rolling(168).mean()
    x["rolling_std_168"] = y.shift(24).rolling(168).std()
    return x


def metrics(actual, forecast):
    a, p = np.asarray(actual, dtype=float), np.asarray(forecast, dtype=float)
    if a.ndim != 1 or p.ndim != 1 or a.shape != p.shape or a.size == 0:
        raise ValueError("Metrics require nonempty, matched one-dimensional arrays")
    if not np.isfinite(a).all() or not np.isfinite(p).all() or (a <= 0).any():
        raise ValueError("Demand metrics require finite forecasts and finite positive actuals")
    e = p - a
    return {"N": len(a), "MAE_MW": float(np.abs(e).mean()), "RMSE_MW": float(np.sqrt(np.mean(e ** 2))),
            "WAPE_pct": float(100 * np.abs(e).sum() / np.abs(a).sum()),
            "MAPE_pct": float(100 * np.mean(np.abs(e / a))), "Bias_MW": float(e.mean())}


def interval_radius(errors, level=.8):
    """Finite-sample absolute-residual order statistic; no IID coverage claim."""
    e = np.asarray(errors, dtype=float)
    if e.ndim != 1 or e.size == 0 or not np.isfinite(e).all():
        raise ValueError("Interval calibration requires nonempty finite one-dimensional residuals")
    if not np.isfinite(level) or not 0 < level < 1:
        raise ValueError("Interval level must be strictly between zero and one")
    e = np.sort(np.abs(e))
    rank = min(int(np.ceil((len(e) + 1) * level)), len(e))
    return float(e[rank - 1])
