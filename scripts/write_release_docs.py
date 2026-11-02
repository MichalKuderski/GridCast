"""Write the case study and career draft from reconciled saved outputs."""
from pathlib import Path
import json
import hashlib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    service_path = ROOT / "outputs/verification/service_session_status.json"
    service = json.loads(service_path.read_text()) if service_path.exists() else {}
    service_verified = all(service.get(key, False) for key in ("refresh_verified", "persistent_measures_verified", "dax_metric_parity_verified", "report_render_verified", "report_screenshots_verified"))
    # Runtime evidence belongs to the validated snapshot. A new CSV/model must
    # not inherit the previous Service pass merely because a receipt exists.
    try:
        upload = json.loads((ROOT / "outputs/verification/service_upload_manifest.json").read_text())
        metadata = json.loads((ROOT / "outputs/verification/service_exports/metadata_reconciliation.json").read_text())
        expected_sources = {item["file"]: item["sha256"] for item in upload["files"]}
        required_sources = [f"data/powerbi/{name}.csv" for name in ("FactDemand", "FactForecast", "DimDate", "DimModel")]
        source_match = all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected_sources[name] for name in required_sources)
        model_match = hashlib.sha256((ROOT / "powerbi/GridCast.SemanticModel/model.bim").read_bytes()).hexdigest() == metadata["source_model"]["sha256"]
        service_verified = service_verified and source_match and model_match
    except (OSError, KeyError, TypeError, ValueError):
        service_verified = False
    # Reproduction must not overwrite the reviewed public career/case-study
    # copy with a preliminary draft. Preserve only byte-verified documents for
    # the same validated data/model snapshot; changed inputs require new review.
    finalized = {}
    try:
        publication = json.loads((ROOT / 'outputs/publication/anonymous_access.json').read_text())
        verified = {row['path']: row['sha256'] for row in publication.get('checks', [])
                    if 'path' in row and row.get('matches_local')}
        if service_verified and publication.get('status') == 'passed_anonymous_public_access':
            for name in ['reports/CASE_STUDY.md', 'docs/PORTFOLIO_AND_CAREER.md']:
                content = (ROOT / name).read_bytes()
                if hashlib.sha256(content).hexdigest() == verified.get(name):
                    finalized[name] = content.decode('utf-8')
    except (OSError, KeyError, TypeError, ValueError):
        pass
    s = json.loads((ROOT / "outputs/run_summary.json").read_text())
    boot = json.loads((ROOT / "outputs/paired_bootstrap.json").read_text())
    residual = json.loads((ROOT / "outputs/residual_autocorrelation.json").read_text())
    scores = pd.read_csv(ROOT / "outputs/model_metrics.csv")
    test = scores.loc[scores.Split == "test"].set_index("Model")
    m = s["test_metrics"]
    forecasts = pd.read_csv(ROOT / 'data/powerbi/FactForecast.csv')
    high_rows = forecasts.loc[(forecasts.Model == s['selected_model']) & (forecasts.Split == 'test') & (forecasts.ActualMW >= s['training_p90_MW'])]
    high_coverage = 100 * high_rows.ActualMW.between(high_rows.Lower80MW, high_rows.Upper80MW).mean()
    gain = 100 * (1 - m["MAE_MW"] / test.loc["DailyNaive", "MAE_MW"])
    table = "| Model | MAE (MW) | RMSE (MW) | WAPE | Bias (MW) |\n| --- | ---: | ---: | ---: | ---: |\n"
    for name, row in test.sort_values("MAE_MW").iterrows():
        table += f"| {name} | {row.MAE_MW:,.0f} | {row.RMSE_MW:,.0f} | {row.WAPE_pct:.2f}% | {row.Bias_MW:+,.0f} |\n"
    case = f"""# GridCast: forecasting PJM demand with an honest test year

## Decision and result

Can a compact calendar-and-demand model improve on simple daily persistence while making its uncertainty and failures visible? On **{m['N']:,} valid hourly actuals in 2025**, the model selected using 2023 MAE achieved **{m['MAE_MW']:,.0f} MW MAE** and **{m['WAPE_pct']:.2f}% WAPE**. MAE was **{gain:.1f}% lower than yesterday's same-hour baseline**, the stronger of the two naïve comparators.

The result supports using this model as an analyst review aid. It underpredicts high demand and should not be described as dispatch-ready. Its nominal 80% pointwise intervals covered **{100*s['test_interval_coverage']:.1f}%** of valid test hours. **Only {high_coverage:.2f}% of high-demand hours are covered.** Aggregate accuracy hides weak uncertainty coverage during stressed demand.

This is a historical forecasting study and decision-support prototype. No outage, grid-reliability, price, savings, or emissions outcome was measured.

## Source and cleaning

The population is the **PJM balancing authority**, using official [EIA-930 hourly data](https://www.eia.gov/electricity/930-content/about.html). It is not a single PJM utility zone. The frozen workbook was retrieved on **27 October 2026**; observations cover UTC interval starts from 1 January 2019 through 31 December 2025. EIA reported demand is not asserted to equal PJM's market-settled load product.

The extract contains **61,368 unique UTC hours**. EIA's hour-ending timestamps are shifted back one hour. One-hour MWh divided by one hour is mean MW; peak MW and time-summed MWh have separate labels. Calendar features use America/New_York; splits, daily origins, and annual summaries use UTC.

Cleaning masks **178 target observations**: 167 missing originals, seven additional EIA-flagged values, and four reviewed spikes confined to the 2020 training period. The four are analyst-inferred anomalies, not operator-confirmed corrections. Raw originals and quality fields are preserved. Past-only replacements supply historical features where necessary, but never become scored actuals. Twenty-five 2025 actuals are missing, leaving {m['N']:,} scored hours. The source ledger, original checksums, and anomaly review are in [SOURCES](../docs/SOURCES.md) and [anomaly_review.csv](../docs/anomaly_review.csv).

The 25 missing test actuals form one contiguous gap from 2 November 2025 04:00 UTC through 3 November 04:00 UTC, around the Eastern autumn clock change. Observed-hour accuracy does not validate that missing transition. Annual energy tables sum only valid measured hours and show completeness. They do not estimate the missing hours' energy.

![Monthly mean demand](figures/demand_trend.png)

Recurring seasonal and local-hour patterns justify seasonal baselines and calendar features. These are descriptive associations; no weather or causal driver was measured in this release.

![Local demand profile](figures/hourly_profile.png)

## Protocol fixed before test evaluation

| Stage | Period | Use |
| --- | --- | --- |
| Initial fit | 2019–2022 | Fit fixed candidate specifications and preprocessing |
| Model selection | 2023 | Choose minimum hourly MAE on common valid timestamps |
| Final point-model fit | 2019–2023 | Refit each fixed candidate once for later comparison; selected champion fixed here |
| Interval calibration | 2024 | Derive 24 horizon-specific nominal 80% residual radii for the champion |
| Final test | 2025 | Evaluate frozen model and interval rule; no tuning |

At each midnight UTC origin, predict the 24 intervals beginning at the origin. Horizon 1 is the origin's first hour and horizon 24 its last. All features read demand strictly before the origin: lag 24/48/168/336, and rolling summaries shifted 24 hours. Target-day and later actuals can be perturbed without changing any of the 24 feature rows. Scaling lives inside the Ridge training pipeline.

This assumes access to the last completed hour. EIA's public reporting latency and revised history do not prove that assumption. Source quality flags are also retrospective. Therefore, this is a **cleaned historical benchmark**, not a vintage-preserving replay of a live EIA-only feed. A production protocol would require issued snapshots, latency handling, and a new evaluation.

The candidate set contains daily and weekly persistence, Ridge, and two bounded histogram gradient boosting configurations. The smaller tree configuration won 2023 MAE; test results did not choose it. Weather and holiday features are deferred, not hidden completed work.

## Test evidence and tradeoffs

{table}

All rows use the same {m['N']:,} valid test hours. The primary improvement is against **DailyNaive**, not the much weaker weekly baseline. Ridge has lower test RMSE than the selected model, so the conclusion depends on the fixed validation-MAE objective. The project does not compare against PJM's own operational forecast because issue times and revisions were not aligned.

![Candidate model comparison](figures/model_comparison.png)

A paired seven-day moving-block bootstrap estimates a mean MAE gain of **{boot['mean_MAE_gain_MW']:,.0f} MW**, with a descriptive 95% percentile interval of **{boot['lower95_MW']:,.0f}–{boot['upper95_MW']:,.0f} MW**. The bootstrap uses 2,000 samples and seed 42. One year's blocks do not establish future-year performance, causality, or realized savings.

## Where predictions fail

- **High demand:** above the fixed initial-training 90th percentile ({s['training_p90_MW']:,.1f} MW), {s['test_high_demand_metrics']['N']:,} test hours have **{s['test_high_demand_metrics']['MAE_MW']:,.0f} MW MAE** and **{s['test_high_demand_metrics']['Bias_MW']:+,.0f} MW bias**. Large underprediction is a practical reason for analyst review.
- **Seasonal stress:** June MAE is about 6,245 MW versus about 1,943 MW in October. June interval coverage is only 66.5%; January and July are also weak. Weather is a plausible next hypothesis, not an established explanation.
- **Peak magnitude:** daily peak MAE is **{s['test_daily_peak_MAE_MW']:,.0f} MW** over {s['test_complete_peak_days']} days with 24 valid measured hours. This compares daily maxima and does not measure peak timing accuracy.
- **Uncertainty:** average test interval width is **{s['test_interval_mean_width_MW']:,.0f} MW**. The bands are pointwise prediction intervals, with no simultaneous-path or guaranteed distribution-free coverage claim under serial dependence and drift.
- **Persistent misses:** residual autocorrelation is {residual['1']:.2f} at one hour and {residual['24']:.2f} at 24 hours on the regular UTC grid. Errors arrive in runs; independent-hour uncertainty assumptions would be misleading. The largest saved test miss is about 30.3 GW during the June stress event.

![Seasonal errors and coverage](figures/seasonal_errors.png)

![Error versus demand](figures/high_demand_bias.png)

The following stress view is deliberately selected to contain the largest valid 2025 demand. It exposes a failure case rather than representing a randomly chosen week.

![Stress week](figures/stress_week.png)

## Actionable next steps

1. Show the demand path, calibrated range, and high-demand underprediction warning together for analyst review. Do not use a mean accuracy number as an operational reserve rule.
2. Test archived, issued weather forecasts and explicit holiday calendar effects in a new experiment. For PJM, use representative regional stations or geographic weights; a single city's realized temperature is insufficient for an honest regional forecast.
3. Evaluate a rolling refit and regime drift using a new holdout or nested forward validation. Keep this 2025 result frozen as the initial benchmark.
4. Obtain an as-of data feed with a verified publication delay before attempting deployment. Re-evaluate every feature under that delay.

## Power BI implementation and evidence status

The authored [Power BI project](../powerbi/GridCast.pbip) includes native report definitions, an import semantic model, Power Query, DAX, a theme, and four CSV facts/dimensions. Demand totals use one history fact; forecast scores require one model, exclude missing actuals, and aggregate WAPE from its numerator and denominator. The source includes demand patterns, test comparison, uncertainty, and failure diagnostics.

Official report JSON schemas and field/relationship checks pass, and exported metric expectations reconcile to Python. Runtime evidence applies only to the source/model hashes it verified; a changed bundle needs new Service or Desktop checks. **Windows PBIP/Desktop compatibility remains untested.** Follow [the Power BI handoff](../powerbi/README.md) and [the snapshot-scoped Service receipt](../powerbi/SERVICE_VALIDATION.md).

The next-day output is a historical, unscored illustration for **1 January 2026 UTC**, based on the end of the 2025 snapshot. It is not today's forecast.

![Historical next-day demonstration](figures/historical_next_day.png)

## Reproduce and audit

Run the setup and pipeline commands in the [README](../README.md), then inspect [the executed notebook](../notebooks/GridCast_Analysis.ipynb). The independent tests reconcile all saved model scores, source mappings, missing-target exclusions, interval radii, export grains, and origin availability. Checks and remaining gates are recorded in [VALIDATION](../outputs/VALIDATION.md) and the [publication checklist](../docs/PUBLICATION_CHECKLIST.md).

Source: U.S. Energy Information Administration, Form EIA-930 PJM workbook, retrieved 2026-10-27. The source is revised historical data. This independent project is not endorsed by EIA or PJM.
"""
    if service_verified:
        case = case.replace(
            "Official report JSON schemas and field/relationship checks pass, and exported metric expectations reconcile to Python. Runtime evidence applies only to the source/model hashes it verified; a changed bundle needs new Service or Desktop checks. **Windows PBIP/Desktop compatibility remains untested.** Follow [the Power BI handoff](../powerbi/README.md) and [the snapshot-scoped Service receipt](../powerbi/SERVICE_VALIDATION.md).",
            "The separate saved **Power BI Service** report has four pages, 35 visuals and 28 persistent measures. A completed manual refresh, real standalone DAX parity, metadata exports, observed model/date filter states and genuine report screenshots are verified in [the Service receipt](../powerbi/SERVICE_VALIDATION.md). DailyNaive is the stronger of the two naive comparators, while the selected model has lower MAE than DailyNaive. **Windows PBIP/Desktop compatibility remains untested**; no PBIX download/export or public sharing is claimed.\n\n![Actual Service test scorecard](../outputs/verification/screenshots/06_service_test_page.jpg)"
        )
    (ROOT / "reports/CASE_STUDY.md").write_text(finalized.get('reports/CASE_STUDY.md', case))
    career = f"""# Portfolio and career materials

## Status to use now

Python analysis, evaluated forecasts, executed notebook, and authored Power BI source are available. Native Power BI Desktop validation is pending. Do not describe this as a deployed product or a fully validated published dashboard.

## Resume bullets supported by the current analysis

- Built a reproducible PJM hourly demand forecasting pipeline using 61,368 official EIA-930 observations; audited timestamp conventions and isolated 178 invalid targets while preserving source provenance.
- Selected a histogram gradient boosting model with chronological validation and achieved {m['WAPE_pct']:.2f}% WAPE on {m['N']:,} valid 2025 hours, reducing MAE {gain:.1f}% versus a daily seasonal naïve baseline; evaluated calibrated uncertainty and high-demand failure cases.

Optional technical skills line: Python, pandas, scikit-learn, time series validation, feature engineering, uncertainty calibration, data-quality auditing, dimensional modeling, DAX, Power Query.

Only after native Desktop gates pass, add a third bullet such as: “Implemented a Power BI report with demand profiles, model comparison, forecast intervals, and error diagnostics; reconciled DAX measures against Python and validated refresh and slicer behavior.” Do not use that completed wording before performing the checks.

## LinkedIn draft — review before posting

I built GridCast, a historical PJM energy-demand forecasting study using official EIA-930 data.

The challenge was more than fitting a model: the source uses hour-ending timestamps and includes missing and corrupt readings. I preserved the raw data, documented exclusions, and kept repaired historical inputs separate from measured targets.

The model was selected using 2023 data, calibrated on 2024, and tested on 2025. It achieved {m['WAPE_pct']:.2f}% WAPE and reduced MAE {gain:.1f}% versus yesterday's same-hour baseline across {m['N']:,} valid test hours.

The limitations were instructive: high-demand hours were systematically underpredicted, and nominal 80% intervals covered {100*s['test_interval_coverage']:.1f}% overall but only {high_coverage:.2f}% of high-demand hours. I treated those as findings to communicate, not numbers to hide.

The repository includes reproducible code, an executed notebook, and Power BI source prepared for native Desktop validation. The study does not claim production deployment, outage prevention, or financial savings.

[Add the verified repository/case-study links only after creating and reviewing them.]

## Portfolio page structure

Use `reports/CASE_STUDY.md` as the source narrative. Lead with the decision, MAE improvement, and high-demand limitation. Include the source/cleaning receipt, chronological protocol, comparison chart, seasonal coverage chart, stress-week plot, and actual native Power BI screenshots once verified. Link the executed notebook and reproduction commands.

Include a compact evidence strip: 2019–2025 observation period · 61,368 source hours · {m['N']:,} valid test hours · {m['WAPE_pct']:.2f}% test WAPE · {gain:.1f}% MAE improvement over DailyNaive · retrospective cleaned-data prototype.

## Interview preparation

- **Why a chronological split?** Random splits would mix later demand regimes into training and overstate forecasting performance.
- **Why use daily persistence as the headline baseline?** It has lower MAE than weekly persistence, while the champion has lower MAE than both. Citing only the weaker weekly result exaggerates the practical gain.
- **Why not include EIA's demand forecast or realized weather?** Their issue-time availability is not established for this origin; using them could leak unavailable information.
- **Why is Ridge still relevant?** It has slightly lower test RMSE, while the selected tree model wins the declared MAE objective. Model choice depends on the error cost.
- **What would you improve next?** Archived issued weather, holidays, explicit feed latency, rolling refits, and a fresh holdout. Do not retune on 2025 and label it untouched again.
- **Why not claim savings?** Error reduction is not a measured dispatch, procurement, reliability, or price outcome.
- **What remains before publication?** Native Power BI validation and screenshots, a reviewed repository/portfolio link, and a final claim check. No post has been sent automatically.
"""
    if service_verified:
        career = career.replace(
            "Python analysis, evaluated forecasts, executed notebook, and authored Power BI source are available. Native Power BI Desktop validation is pending. Do not describe this as a deployed product or a fully validated published dashboard.",
            "Python analysis and the saved Power BI Service report are verified. Real refresh, 28 persistent measures, numerical/context parity, metadata and observed visual/filter checks have evidence. Windows PBIP/Desktop compatibility and public-link access remain unverified. The report remains in the owner's workspace without sharing links; this is a historical prototype, not an operational deployment."
        ).replace(
            "Only after native Desktop gates pass, add a third bullet such as: “Implemented a Power BI report with demand profiles, model comparison, forecast intervals, and error diagnostics; reconciled DAX measures against Python and validated refresh and slicer behavior.” Do not use that completed wording before performing the checks.",
            "An additional supported resume bullet: Implemented a four-page Power BI Service report with 35 visuals and 28 persistent DAX measures; reconciled real engine results against Python, verified manual refresh and observed model/date filters, and documented high-demand forecast failures. Do not claim Windows compatibility, a downloaded PBIX or public sharing."
        ).replace(
            "The repository includes reproducible code, an executed notebook, and Power BI source prepared for native Desktop validation. The study does not claim production deployment, outage prevention, or financial savings.",
            "The repository includes reproducible code, an executed notebook and genuine screenshots of the validated four-page Power BI Service report. Service refresh, persistent DAX parity and observed model/date filters were verified. Windows PBIP compatibility remains untested; no operational deployment, public report sharing, outage prevention or financial savings is claimed."
        ).replace(
            "actual native Power BI screenshots once verified",
            "the verified Service screenshots listed in powerbi/SERVICE_VALIDATION.md"
        ).replace(
            "**What remains before publication?** Native Power BI validation and screenshots, a reviewed repository/portfolio link, and a final claim check. No post has been sent automatically.",
            "**What remains before public publication?** Separate release authorization and unauthenticated repository/portfolio link checks. Service validation is complete at its documented scope; Windows compatibility remains an unclaimed separate gate. No public post was sent automatically."
        )
    (ROOT / "docs/PORTFOLIO_AND_CAREER.md").write_text(finalized.get('docs/PORTFOLIO_AND_CAREER.md', career))
    print("Wrote evidence-backed case study and career drafts")


if __name__ == "__main__":
    main()
