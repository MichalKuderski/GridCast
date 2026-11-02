"""Post-release sensitivity audit; never alters the frozen experiment or model.

The examined 2025 year is now a diagnostic set. Variants below are deliberately
not model selection, deployment evidence, or fresh untouched-test estimates.
"""
from pathlib import Path
import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
import sys
import json
import hashlib
from datetime import datetime, timezone
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gridcast.core import clean_demand, causal_fill, make_features, metrics
from run_pipeline import candidates


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def available_batch(series, origin, release_delay_hours=0):
    """Simulate release exactly delay hours after interval END.

    Only missing recent historical input slots are carried forward. The target
    day remains unknown. This is an explicit diagnostic input policy, not an
    assertion about EIA's variable real-time publication timing.
    """
    if release_delay_hours < 0 or int(release_delay_hours) != release_delay_hours:
        raise ValueError("Delay must be a nonnegative integer")
    origin = pd.Timestamp(origin)
    if origin.tz is None or origin.hour != 0 or origin.minute or origin.second:
        raise ValueError("Origin must be timezone-aware midnight")
    origin = origin.tz_convert("UTC")
    if origin.hour != 0:
        raise ValueError("Origin must be midnight UTC")
    index = pd.date_range(origin - pd.Timedelta(hours=400), origin + pd.Timedelta(hours=23), freq="h")
    inputs = series.reindex(index).copy()
    cutoff = origin - pd.Timedelta(hours=1 + release_delay_hours)
    inputs.loc[inputs.index > cutoff] = np.nan
    history = inputs.loc[inputs.index < origin].ffill()
    inputs.loc[history.index] = history
    return make_features(inputs).loc[origin:]


def main():
    out = ROOT / "outputs/verification"
    out.mkdir(parents=True, exist_ok=True)
    demand, quality = clean_demand(ROOT)
    x = make_features(demand.FeatureInputMW)
    summary = json.loads((ROOT / "outputs/run_summary.json").read_text())
    selected = summary["selected_model"]
    if selected.endswith("Naive"):
        raise ValueError("This audit expects the saved learned champion; extend explicitly for naive champions")
    model_path = ROOT / "models/champion.joblib"
    model = joblib.load(model_path)
    f = pd.read_csv(ROOT / "data/powerbi/FactForecast.csv")
    f["DateTimeUTC"] = pd.to_datetime(f.DateTimeUTC, utc=True)
    release = f.loc[(f.Model == selected) & (f.Split == "test")].set_index("DateTimeUTC").sort_index()
    valid = release.ActualMW.notna()
    baseline_pred = np.maximum(0, model.predict(x.loc[release.index]))
    delta = float(np.max(np.abs(baseline_pred - release.ForecastMW.to_numpy())))
    if delta > 2e-6:
        raise ValueError(f"Saved champion does not reproduce exported test predictions: {delta}")
    raw_path = ROOT / "data/raw/eia_pjm_hourly_2019_2025.csv"
    raw = pd.read_csv(raw_path)
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw.DateTimeUTC, utc=True))
    source_invalid = (raw.OriginalDemandMWh.isna() | ~np.isfinite(raw.OriginalDemandMWh) |
                      (raw.OriginalDemandMWh <= 0) | raw.ImputedDemandMWh.notna() |
                      (raw.AdjustedDemandMWh.notna() & raw.OriginalDemandMWh.notna() &
                       (raw.AdjustedDemandMWh != raw.OriginalDemandMWh)))
    # Retain all four manually adjudicated training spikes; preserve source flags.
    alternative_y = raw.OriginalDemandMWh.mask(source_invalid)
    alternative_x = make_features(causal_fill(alternative_y))
    fit = alternative_x.notna().all(axis=1) & alternative_y.notna() & (alternative_x.index < "2024-01-01")
    alternative_model = candidates()[selected]
    alternative_model.fit(alternative_x.loc[fit], alternative_y.loc[fit])
    alternative_pred = np.maximum(0, alternative_model.predict(alternative_x.loc[release.index]))
    alternative_result = metrics(release.loc[valid, "ActualMW"], alternative_pred[valid])
    canonical_result = metrics(release.loc[valid, "ActualMW"], baseline_pred[valid])
    # Latency diagnostic keeps weights fixed; approximates one-hour-after-end
    # release with last-available carry-forward for the unavailable latest hour.
    delayed_parts = []
    max_no_delay_difference = 0.
    for origin in pd.date_range("2025-01-01", "2025-12-31", freq="D", tz="UTC"):
        no_delay = available_batch(demand.FeatureInputMW, origin, 0)
        expected = x.loc[no_delay.index]
        max_no_delay_difference = max(max_no_delay_difference,
                                     float(np.max(np.abs(no_delay.to_numpy() - expected.to_numpy()))))
        delayed = available_batch(demand.FeatureInputMW, origin, 1)
        delayed_parts.append(pd.Series(np.maximum(0, model.predict(delayed)), index=delayed.index))
    delayed_pred = pd.concat(delayed_parts).loc[release.index]
    latency_result = metrics(release.loc[valid, "ActualMW"], delayed_pred.loc[valid])
    last_horizon = valid & (release.index.hour == 23)
    # Fill missing test truth with provider estimates ONLY as a labeled stress
    # calculation. These are not observed truth and one interval remains absent.
    proxy = release.ActualMW.fillna(raw.ImputedDemandMWh.reindex(release.index))
    proxy_valid = proxy.notna()
    proxy_result = metrics(proxy.loc[proxy_valid], baseline_pred[proxy_valid])
    missing = release.index[~valid]
    original_missing = raw.loc[missing, "OriginalDemandMWh"].isna()
    test_valid = release.loc[valid].copy()
    test_valid["Covered"] = test_valid.ActualMW.between(test_valid.Lower80MW, test_valid.Upper80MW)
    daily_coverage = test_valid.groupby(test_valid.index.floor("D")).agg(N=("ActualMW", "size"), AllCovered=("Covered", "all"))
    complete_days = daily_coverage.loc[daily_coverage.N == 24]
    high = test_valid.ActualMW >= summary["training_p90_MW"]
    by_month = test_valid.groupby(test_valid.index.month).Covered.mean()
    manifest = json.loads((ROOT / "data/raw/eia_pjm_manifest.json").read_text())
    source_audit = json.loads((ROOT / "data/raw/eia_pjm_initial_audit.json").read_text())
    actual_source_hash = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    if not actual_source_hash == manifest["extracted_snapshot"]["sha256"] == source_audit["csv_sha256"]:
        raise ValueError("Canonical CSV, extraction audit and source manifest disagree")
    workbook = ROOT / manifest["file"]
    workbook_hash = file_sha256(workbook) if workbook.exists() else None
    if workbook_hash is not None and workbook_hash != manifest["sha256"]:
        raise ValueError("Present original workbook differs from its pinned source manifest")
    record = {
        "audit_time_utc": datetime.now(timezone.utc).isoformat(),
        "status": "post-release diagnostic sensitivity; no model or experiment replacement",
        "selected_specification_unchanged": selected,
        "source_csv_sha256": actual_source_hash,
        "source_manifest_and_audit_hashes_agree": True,
        "original_workbook_currently_present": workbook.exists(),
        "original_workbook_sha256": workbook_hash,
        "original_workbook_hash_matches_manifest": workbook_hash == manifest["sha256"] if workbook_hash is not None else None,
        "code_sha256": {str(p): hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                        for p in ("src/gridcast/core.py", "scripts/run_pipeline.py", "scripts/audit_robustness.py")},
        "saved_model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "saved_model_max_export_prediction_difference_MW": delta,
        "canonical_test": canonical_result,
        "manual_exclusion_sensitivity": {
            "policy": "retain four manual training spikes; retain all source quality exclusions; same frozen selected specification refit through2023; unchanged valid2025truth",
            "canonical_fit_rows": summary["fit_rows_final"], "alternative_fit_rows": int(fit.sum()),
            "alternative_test": alternative_result,
            "MAE_change_MW": alternative_result["MAE_MW"] - canonical_result["MAE_MW"],
        },
        "one_hour_release_delay_sensitivity": {
            "policy": "fixed saved weights; observations released exactly1hourafterintervalend; unavailable latest input carried forward; future targets unknown",
            "latest_available_interval_start_relative_origin_hours": -2,
            "changed_target_rows": int((np.abs(delayed_pred.to_numpy() - baseline_pred) > 2e-6).sum()),
            "changed_horizons": sorted(set((release.index.hour[np.abs(delayed_pred.to_numpy() - baseline_pred) > 2e-6] + 1).tolist())),
            "all_valid_test": latency_result,
            "MAE_change_MW": latency_result["MAE_MW"] - canonical_result["MAE_MW"],
            "canonical_horizon24": metrics(release.loc[last_horizon, "ActualMW"], baseline_pred[last_horizon]),
            "delayed_horizon24": metrics(release.loc[last_horizon, "ActualMW"], delayed_pred.loc[last_horizon]),
            "zero_delay_batch_max_feature_difference": max_no_delay_difference,
            "limit": "approximate latency stress, not archived releases, not recalibrated intervals, not operational validation",
        },
        "excluded_test_truth": {
            "count": len(missing), "first_utc": missing.min().isoformat(), "last_utc": missing.max().isoformat(),
            "contiguous": bool(((missing[1:] - missing[:-1]) == pd.Timedelta(hours=1)).all()),
            "originals_missing": int(original_missing.sum()),
            "provider_estimate_count": int(raw.loc[missing, "ImputedDemandMWh"].notna().sum()),
            "provider_estimate_stress_metrics": proxy_result,
            "limit": "provider imputation is estimated truth; stress metrics are not substitute observed accuracy; onehour still unavailable",
        },
        "interval_stress_diagnostics": {
            "nominal_pointwise_level": .8,
            "overall_valid_hour_coverage": float(test_valid.Covered.mean()),
            "high_demand_threshold_initial_training_p90_MW": summary["training_p90_MW"],
            "high_demand_valid_hours": int(high.sum()),
            "high_demand_coverage": float(test_valid.loc[high, "Covered"].mean()),
            "lowest_month_number": int(by_month.idxmin()), "lowest_month_coverage": float(by_month.min()),
            "complete_UTC_days": len(complete_days),
            "complete_day_all_24_hours_covered_fraction": float(complete_days.AllCovered.mean()),
            "limit": "pointwise intervals are not simultaneous path intervals; no new recalibration or guarantee",
        },
        "source_quality_flags_retrospective": True,
        "no_fresh_holdout_claim": True,
    }
    (out / "robustness.json").write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
