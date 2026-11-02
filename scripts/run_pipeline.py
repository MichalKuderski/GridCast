"""Run locked historical experiment and export clean Power BI facts."""
from pathlib import Path
import sys
import os
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".cache/matplotlib"))
os.environ.setdefault("OMP_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import json
import platform
from datetime import datetime, timezone
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from gridcast.core import clean_demand, make_features, metrics, interval_radius


def candidates():
    return {
        "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=100.0)),
        "HistGB_small": HistGradientBoostingRegressor(max_iter=180, max_leaf_nodes=15, learning_rate=.06, l2_regularization=10, early_stopping=False, random_state=42),
        "HistGB_large": HistGradientBoostingRegressor(max_iter=300, max_leaf_nodes=31, learning_rate=.05, l2_regularization=10, early_stopping=False, random_state=42),
    }


def fact_frame(y, pred, name, split):
    idx = y.index
    return pd.DataFrame({"DateTimeUTC": idx, "Date": idx.strftime("%Y-%m-%d"), "HourUTC": idx.hour,
                         "ForecastOriginUTC": idx.floor("D"), "HorizonHours": idx.hour + 1,
                         "Model": name, "Split": split, "ActualMW": y.to_numpy(), "ForecastMW": np.maximum(0, pred),
                         "Lower80MW": np.nan, "Upper80MW": np.nan})


def write_csv(frame, path):
    frame = frame.copy()
    for col in ("DateTimeUTC", "ForecastOriginUTC"):
        if col in frame:
            frame[col] = frame[col].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    frame.to_csv(path, index=False, float_format="%.6f")


def main():
    for folder in ("data/processed", "data/powerbi", "outputs", "models", "reports/figures"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    demand, quality = clean_demand(ROOT)
    y = demand.ActualMW
    x = make_features(demand.FeatureInputMW)
    eligible = x.notna().all(axis=1)
    # Lock chronology before any scores are observed.
    train = eligible & y.notna() & (x.index < "2023-01-01")
    val = eligible & (x.index >= "2023-01-01") & (x.index < "2024-01-01")
    final_fit = eligible & y.notna() & (x.index < "2024-01-01")
    cal = eligible & (x.index >= "2024-01-01") & (x.index < "2025-01-01")
    test = eligible & (x.index >= "2025-01-01") & (x.index < "2026-01-01")
    assert [sum(val), sum(cal), sum(test)] == [8760, 8784, 8760], "Complete scoring years required"
    models = candidates()
    facts, scores = [], []
    for name in ["DailyNaive", "WeeklyNaive", *models]:
        if name.endswith("Naive"):
            lag = 24 if name == "DailyNaive" else 168
            pred_val = x.loc[val, f"lag_{lag}"].to_numpy()
        else:
            models[name].fit(x.loc[train], y.loc[train])
            pred_val = models[name].predict(x.loc[val])
        facts.append(fact_frame(y.loc[val], pred_val, name, "validation"))
        valid = y.loc[val].notna().to_numpy()
        scores.append({"Model": name, "Split": "validation", **metrics(y.loc[val].to_numpy()[valid], np.maximum(0, pred_val)[valid])})
    val_scores = pd.DataFrame(scores).sort_values(["MAE_MW", "Model"])
    champion = str(val_scores.iloc[0].Model)
    print(f"Selected on 2023 MAE: {champion}", flush=True)
    # Refit once on 2019–2023; parameters and weights remain frozen in 2024–2025.
    for name, model in models.items():
        model.fit(x.loc[final_fit], y.loc[final_fit])
    for split, mask in (("calibration", cal), ("test", test)):
        for name in ["DailyNaive", "WeeklyNaive", *models]:
            if name.endswith("Naive"):
                pred = x.loc[mask, "lag_24" if name == "DailyNaive" else "lag_168"].to_numpy()
            else:
                pred = models[name].predict(x.loc[mask])
            facts.append(fact_frame(y.loc[mask], pred, name, split))
            valid = y.loc[mask].notna().to_numpy()
            scores.append({"Model": name, "Split": split, **metrics(y.loc[mask].to_numpy()[valid], np.maximum(0, pred)[valid])})
    forecasts = pd.concat(facts, ignore_index=True)
    calibration = forecasts.loc[(forecasts.Model == champion) & (forecasts.Split == "calibration") & forecasts.ActualMW.notna()].copy()
    calibration["AbsError"] = (calibration.ActualMW - calibration.ForecastMW).abs()
    radii = calibration.groupby("HorizonHours").AbsError.apply(interval_radius).to_dict()
    for h, radius in radii.items():
        mask = (forecasts.Model == champion) & (forecasts.Split.isin(["calibration", "test"])) & (forecasts.HorizonHours == h)
        forecasts.loc[mask, "Lower80MW"] = np.maximum(0, forecasts.loc[mask, "ForecastMW"] - radius)
        forecasts.loc[mask, "Upper80MW"] = forecasts.loc[mask, "ForecastMW"] + radius
    # Forecast following source endpoint; this is a historical illustration, not today's forecast.
    future_index = pd.date_range(y.index[-1] + pd.Timedelta(hours=1), periods=24, freq="h")
    assert future_index[0].hour == 0
    extended = demand.FeatureInputMW.reindex(y.index.append(future_index))
    future_x = make_features(extended).loc[future_index]
    if champion.endswith("Naive"):
        future_pred = future_x["lag_24" if champion == "DailyNaive" else "lag_168"].to_numpy()
    else:
        future_pred = models[champion].predict(future_x)
        joblib.dump(models[champion], ROOT / "models/champion.joblib")
    future = fact_frame(extended.loc[future_index], future_pred, champion, "future")
    radius = future.HorizonHours.map(radii)
    future["Lower80MW"] = np.maximum(0, future.ForecastMW - radius)
    future["Upper80MW"] = future.ForecastMW + radius
    forecasts = pd.concat([forecasts, future], ignore_index=True)
    history = demand.reset_index()
    history["Date"] = history.DateTimeUTC.dt.strftime("%Y-%m-%d")
    history["HourUTC"] = history.DateTimeUTC.dt.hour
    local_index = history.DateTimeUTC.dt.tz_convert("America/New_York")
    history["DateLocal"] = local_index.dt.strftime("%Y-%m-%d")
    history["HourLocal"] = local_index.dt.hour
    write_csv(history, ROOT / "data/powerbi/FactDemand.csv")
    write_csv(history, ROOT / "data/processed/demand_hourly.csv")
    write_csv(forecasts, ROOT / "data/powerbi/FactForecast.csv")
    dates = pd.date_range(y.index.min().date(), future_index[-1].date(), freq="D")
    dim_date = pd.DataFrame({"Date": dates.strftime("%Y-%m-%d"), "Year": dates.year, "MonthNumber": dates.month, "MonthName": dates.strftime("%B"), "YearMonth": dates.strftime("%Y-%m"), "DayOfWeekNumber": dates.day_of_week + 1, "DayOfWeekName": dates.strftime("%A"), "IsWeekend": dates.day_of_week >= 5})
    dim_date.to_csv(ROOT / "data/powerbi/DimDate.csv", index=False)
    pd.DataFrame({"Model": ["DailyNaive", "WeeklyNaive", *models]}).to_csv(ROOT / "data/powerbi/DimModel.csv", index=False)
    pd.DataFrame(scores).to_csv(ROOT / "outputs/model_metrics.csv", index=False)
    quality["excluded_feature_warmup_hours"] = int((~eligible).sum())
    (ROOT / "outputs/data_quality.json").write_text(json.dumps(quality, indent=2))
    champ_test = forecasts.loc[(forecasts.Model == champion) & (forecasts.Split == "test") & forecasts.ActualMW.notna()].copy()
    threshold = float(y.loc[train].quantile(.90))
    high = champ_test.ActualMW >= threshold
    high_metrics = metrics(champ_test.loc[high, "ActualMW"], champ_test.loc[high, "ForecastMW"])
    complete_days = champ_test.groupby("Date").size().loc[lambda v: v == 24].index
    daily_peaks = champ_test.loc[champ_test.Date.isin(complete_days)].groupby("Date")[["ActualMW", "ForecastMW"]].max()
    peak_mae = float((daily_peaks.ActualMW - daily_peaks.ForecastMW).abs().mean())
    coverage = float(((champ_test.ActualMW >= champ_test.Lower80MW) & (champ_test.ActualMW <= champ_test.Upper80MW)).mean())
    width = float((champ_test.Upper80MW - champ_test.Lower80MW).mean())
    summary = {"selected_model": champion, "selection_criterion": "minimum 2023 hourly MAE, tie model name", "fit_rows_initial": int(sum(train)), "fit_rows_final": int(sum(final_fit)), "test_metrics": metrics(champ_test.ActualMW, champ_test.ForecastMW),
               "test_interval_coverage": coverage, "test_interval_mean_width_MW": width, "training_p90_MW": threshold, "test_high_demand_metrics": high_metrics, "test_daily_peak_MAE_MW": peak_mae, "test_complete_peak_days": len(daily_peaks),
               "interval_radius_by_horizon_MW": radii, "test_year": 2025, "future_start_utc": future_index[0].isoformat(), "run_time_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
               "experiment": "Daily midnight UTC origins; horizon1=origin hour; complete observed demand assumed available through origin−1h; final model frozen at 2023 end."}
    (ROOT / "outputs/run_summary.json").write_text(json.dumps(summary, indent=2))
    for column, group_column in (("horizon", "HorizonHours"), ("month", None)):
        table = champ_test.copy()
        if group_column is None:
            table["Month"] = table.DateTimeUTC.dt.month
            group_column = "Month"
        rows = [{group_column: key, **metrics(group.ActualMW, group.ForecastMW)} for key, group in table.groupby(group_column)]
        pd.DataFrame(rows).to_csv(ROOT / f"outputs/test_metrics_by_{column}.csv", index=False)
    annual = history.groupby(history.DateTimeUTC.dt.year).ActualMW.agg(["mean", "max", "sum", "count", "size"])
    annual.columns = ["MeanMW", "PeakMW", "ObservedEnergyMWh", "ValidHours", "TotalHours"]
    annual["CoveragePct"] = 100 * annual.ValidHours / annual.TotalHours
    annual.to_csv(ROOT / "outputs/annual_demand.csv")
    print(json.dumps({"quality": quality, "result": summary}, indent=2), flush=True)


if __name__ == "__main__":
    main()
