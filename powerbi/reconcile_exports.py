"""Prepare exact expected values for a real Power BI Desktop reconciliation.

Uses stdlib only. Does not execute M or DAX. All comparisons are to the CSV
exports, so these checks are independent of the Power BI report runtime.
"""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import fmean
from zoneinfo import ZoneInfo
import csv
import json
import math

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data" / "powerbi"


def rows(name):
    with (DATA / f"{name}.csv").open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def num(value):
    if value is None or value.strip() == "":
        return None
    number = float(value)
    assert math.isfinite(number), value
    return number


def dt(value):
    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert value.tzinfo is not None and value.utcoffset() == timedelta(0)
    return value


def main():
    demand = rows("FactDemand")
    forecast = rows("FactForecast")
    dates = rows("DimDate")
    models = rows("DimModel")
    assert len({r["Date"] for r in dates}) == len(dates)
    assert len({r["Model"] for r in models}) == len(models)
    date_keys = {r["Date"] for r in dates}
    model_keys = {r["Model"] for r in models}
    actuals = {}
    for r in demand:
        t = dt(r["DateTimeUTC"])
        assert r["DateTimeUTC"] not in actuals
        actuals[r["DateTimeUTC"]] = num(r["ActualMW"])
        assert r["Date"] == t.date().isoformat() and int(r["HourUTC"]) == t.hour
        local = t.astimezone(ZoneInfo("America/New_York"))
        assert r["DateLocal"] == local.date().isoformat() and int(r["HourLocal"]) == local.hour
        assert r["Date"] in date_keys
    timestamps = sorted(dt(t) for t in actuals)
    assert all(b - a == timedelta(hours=1) for a, b in zip(timestamps, timestamps[1:])), "Incomplete UTC grid"
    grouped = defaultdict(list)
    unique = set()
    for r in forecast:
        key = (r["DateTimeUTC"], r["Model"], r["Split"])
        assert key not in unique
        unique.add(key)
        t = dt(r["DateTimeUTC"])
        assert r["Date"] == t.date().isoformat() and int(r["HourUTC"]) == t.hour
        assert r["Date"] in date_keys and r["Model"] in model_keys
        assert 1 <= int(r["HorizonHours"]) <= 24
        assert dt(r["ForecastOriginUTC"]) <= t
        actual, pred = num(r["ActualMW"]), num(r["ForecastMW"])
        assert pred is not None
        lo, hi = num(r["Lower80MW"]), num(r["Upper80MW"])
        assert (lo is None) == (hi is None)
        if lo is not None:
            assert lo <= pred <= hi
        if r["Split"] != "future":
            assert r["DateTimeUTC"] in actuals and actual == actuals[r["DateTimeUTC"]]
        else:
            assert actual is None and r["DateTimeUTC"] not in actuals
        if r["Split"] == "test":
            grouped[r["Model"]].append((actual, pred, lo, hi))
    metrics = []
    run = json.loads((HERE.parent / "outputs/run_summary.json").read_text())
    high_threshold = run["training_p90_MW"]
    for model, values in sorted(grouped.items()):
        pairs = [(a, p, lo, hi) for a, p, lo, hi in values if a is not None and p is not None]
        interval = [(a, p, lo, hi) for a, p, lo, hi in pairs if lo is not None and hi is not None]
        high = [(a, p) for a, p, _, _ in pairs if a >= high_threshold]
        high_interval = [(a, p, lo, hi) for a, p, lo, hi in interval if a >= high_threshold]
        metrics.append({
            "Model": model,
            "Test Hours": len(pairs),
            "Test Actual MWh": sum(a for a, _, _, _ in pairs),
            "Test Forecast MWh": sum(p for _, p, _, _ in pairs),
            "Test Actual MW": fmean(a for a, _, _, _ in pairs),
            "Test Forecast MW": fmean(p for _, p, _, _ in pairs),
            "Test MAE MW": fmean(abs(p - a) for a, p, _, _ in pairs),
            "Test RMSE MW": math.sqrt(fmean((p - a) ** 2 for a, p, _, _ in pairs)),
            "Test WAPE": sum(abs(p - a) for a, p, _, _ in pairs) / sum(abs(a) for a, _, _, _ in pairs),
            "Test Bias MW": fmean(p - a for a, p, _, _ in pairs),
            "Test Interval Hours": len(interval),
            "Test Coverage 80": sum(lo <= a <= hi for a, _, lo, hi in interval) / len(interval) if interval else None,
            "Test Mean Interval Width MW": fmean(hi - lo for _, _, lo, hi in interval) if interval else None,
            "Training High Demand Threshold MW": high_threshold,
            "Test High Demand Hours": len(high),
            "Test High Demand MAE MW": fmean(abs(p-a) for a,p in high) if high else None,
            "Test High Demand Bias MW": fmean(p-a for a,p in high) if high else None,
            "Test High Demand Coverage 80": sum(lo <= a <= hi for a, _, lo, hi in high_interval) / len(high_interval) if high_interval else None,
        })
    selected = next(m for m in metrics if m["Model"] == run["selected_model"])
    for dax, key in [("Test MAE MW", "MAE_MW"), ("Test RMSE MW", "RMSE_MW"), ("Test Bias MW", "Bias_MW")]:
        assert math.isclose(selected[dax], run["test_metrics"][key], rel_tol=1e-8, abs_tol=1e-4)
    assert math.isclose(selected["Test WAPE"]*100, run["test_metrics"]["WAPE_pct"], abs_tol=1e-8)
    assert selected["Test Hours"] == run["test_metrics"]["N"]
    assert selected["Test High Demand Hours"] == run["test_high_demand_metrics"]["N"]
    assert math.isclose(selected["Test High Demand MAE MW"], run["test_high_demand_metrics"]["MAE_MW"], rel_tol=1e-8, abs_tol=1e-4)
    assert math.isclose(selected["Test High Demand Bias MW"], run["test_high_demand_metrics"]["Bias_MW"], rel_tol=1e-8, abs_tol=1e-4)
    target = HERE / "validation"
    target.mkdir(exist_ok=True)
    with (target / "expected_test_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows(metrics)
    observed = [x for x in actuals.values() if x is not None]
    receipt = {"status": "passed", "input_folder": "data/powerbi", "demand_rows": len(demand), "forecast_rows": len(forecast), "model_count": len(models), "expected_hours": len(demand), "observed_hours": len(observed), "missing_hours": len(demand) - len(observed), "observation_completeness": len(observed) / len(demand), "demand_mwh": sum(observed), "mean_demand_mw": fmean(observed), "peak_demand_mw": max(observed), "checks": ["unique fact grain and dimension keys", "one-hour UTC grid", "UTC date/hour fields", "America/New_York local date/hour fields", "referential integrity", "forecast actuals equal history actuals, including nulls", "non-null predictions", "origin no later than target and horizons 1–24", "paired interval bounds contain point prediction", "future rows have no actual"], "native_runtime_verified": False}
    (target / "export_reconciliation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
