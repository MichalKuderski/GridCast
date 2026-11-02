# GridCast project blueprint

## Purpose and decision

Build a reproducible historical prototype that forecasts PJM regional electricity demand for the next 24 hours, once per day. The intended users are an operations analyst reviewing tomorrow's demand profile and a planning analyst assessing the forecast's strengths and failures. A portfolio reader should be able to trace a claim from the written analysis to a figure, scored forecast rows, and the original data.

The central question is whether a modest forecasting model improves on daily and weekly seasonal persistence, and whether the improvement holds across seasons, hours, and high-demand periods. The result supports reviewing the expected demand profile and identifying hours needing closer analyst attention. It does not establish dispatch readiness, reserve adequacy, avoided outages, customer reliability, electricity prices, emissions reductions, or realized financial savings.

## Scope and source contract

- **Population:** PJM balancing authority regional demand, as represented in the U.S. Energy Information Administration's hourly electric grid data; not a household sample or an individual utility's customer load.
- **Working period:** complete years 2019–2025. The data manifest and quality output control the actual accepted coverage.
- **Grain:** one observation per UTC hour for one region. Retain the original source metadata, URL, retrieval timestamp, file size, and SHA256 checksum.
- **Units:** the original hourly demand field is MWh. For a one-hour interval, this is numerically equal to average MW over the interval. The model and report label this rate `ActualMW`; summed hourly observations become MWh. Never sum MW across an arbitrary duration and label the result peak MW.
- **Time convention:** the EIA UTC timestamp marks the hour ending. Subtract one hour to represent the beginning of that interval. Store a unique UTC key; derive local calendar features in `America/New_York`, preserving daylight-saving offsets.
- **Source vintage:** the downloaded history may contain revisions. It is not an archive proving what a forecaster could have downloaded at each historical origin. Distinguish the retrieval date from the observation period.

The source research notes and download manifest provide the source-level evidence. If source coverage, definitions, or units change, version the input and rerun the pipeline rather than overwriting the provenance silently.

## Business questions and evidence

| Question | Evidence to inspect | Practical implication |
| --- | --- | --- |
| How does demand vary by time? | Hourly and weekday profiles, monthly distributions, annual totals and peaks | Identify recurring planning windows; describe associations, not causes |
| Does a model beat simple persistence? | Same test timestamps for all models; MAE, RMSE, WAPE, bias | Prefer added complexity only when the measured gain supports it |
| Where does it fail? | Error by month, local hour, weekday, forecast horizon, and high-demand subset | Direct analyst review to weak segments; define the next experiment |
| Are uncertainty bands useful? | Held-out interval coverage and mean width, with segment results where supported | Communicate uncertainty without treating a nominal band as a guarantee |
| Can another person reproduce the claim? | Pinned inputs, environment, executable pipeline, notebook, tests and reconciled BI measures | Make the portfolio evidence inspectable |

## Data cleaning and quality

1. Preserve the original download and verify its checksum before extraction. Extract only the intended region, target, and time field.
2. Parse the source UTC hour-ending timestamps explicitly, then shift to interval starts. Record the first and last accepted timestamps.
3. Sort and check unique UTC keys, an uninterrupted hourly grid, expected annual coverage, finite numeric demand, and physically invalid values. The pinned extract has 61,368 UTC hours and 178 invalid measured targets: 167 missing observations, seven additional source-flagged observations, and four contextual anomalies reviewed in the 2020 training period. Preserve the original field and the anomaly ledger.
4. Investigate suspicious jumps and extremes. High demand can be the very event the model needs to forecast; do not remove it merely because a generic outlier rule flags it. The four manually excluded training spikes are inferred anomalies supported by the review ledger, not corrections confirmed by PJM.
5. Keep all 178 invalid targets missing for fitting and scoring. Fill a separate historical feature-input series causally from 168 hours earlier, falling back to 24 hours and then one hour earlier; this may use already-filled past inputs but never a later observation. Record both the exclusion count and feature-fill count. Fail clearly on an unrecognized coverage, checksum, or duplicate-key conflict.
6. Reconcile hourly rate aggregation to energy totals and independently inspect a small sample of source records, including a daylight-saving transition and a year boundary.

A passing schema check is insufficient evidence of quality. The saved quality report should state what was tested, how many rows were affected, and which caveats remain. Annual energy sums include valid observed hours only; report valid hours and total hours beside them, and do not describe these incomplete sums as complete annual consumption.

## Forecast protocol and information availability

At each origin `00:00 UTC`, predict the 24 hourly intervals beginning at that origin. Horizons run from 1 to 24. This is a reproducible daily experiment, not a claim that the issue time matches PJM's operational market deadline.

Use known calendar features and lagged demand. Lags of 24, 48, 168, and 336 hours and rolling summaries shifted by at least 24 hours remain available for every target hour in this protocol. The latest source observation any target-day feature can read must precede that day's origin. Tests perturb every target-day and later actual value and require all 24 forecast feature rows to remain unchanged.

Historical evaluation assumes the preceding demand observations are available at the origin. The revised source does not establish real-time publication lag. An operational system would need as-of snapshots and an explicit latency policy.

### Chronological separation

| Period | Role | Permitted use |
| --- | --- | --- |
| 2019–2022 | Initial training | Fit candidate models, preprocessing, and training-only summaries |
| 2023 | Model selection | Choose the candidate using MAE on identical timestamps; inspect the selection evidence |
| 2019–2023 | Final point-model fit | Refit the chosen specification once, before calibration and test scoring |
| 2024 | Interval calibration | Estimate 24 horizon-specific absolute-error interval radii for the selected model; do not select the point model here |
| 2025 | Final historical test | Report generalization once with the point model and interval rule already frozen |
| First 24 hours after the accepted history | Unscored demonstration | Show the pipeline's next-day output with missing actuals; do not include it in accuracy metrics |

Keep validation, calibration, test, and unscored rows visibly labeled in exports. If test results inspire a new feature or tuning choice, describe that work as a new experiment and obtain a fresh holdout before making a new untouched-test claim.

## Models, seasonality, and uncertainty

The initial candidates are yesterday's same UTC hour, last week's same UTC hour, Ridge regression, and two bounded histogram gradient boosting configurations. Daily and weekly persistence provide interpretable reference points. Calendar and Fourier features represent recurring patterns; demand lags carry recent level and shape. The weekly UTC baseline can move relative to local clock time at daylight-saving changes, which is a limitation to inspect.

Keep preprocessing inside each training pipeline. Select by validation MAE and retain the complete candidate score table. Refit the fixed specifications on 2019–2023 for a common later-period comparison; keep the selected champion fixed regardless of their test ranking. Do not infer that a more complex model is better before comparing its measured result.

For the selected point model, calibrate a nominal 80% band from 2024 valid-target absolute residuals using the finite-sample order statistic separately for each of the 24 horizons. Freeze those 24 radii before scoring 2025. Report realized 2025 coverage and width over valid test targets. Serial dependence, changing demand patterns, and extreme conditions mean this historical calibration does not guarantee 80% coverage for every month, horizon, peak, or future period.

Weather is a later extension. To use it in an honest next-day forecast, join archived forecasts with an issue timestamp no later than the origin and a valid target time. Realized target-hour weather would leak information unless the task were explicitly reframed as an explanatory or oracle experiment. Historical observations alone do not provide that deployment input.

## Evaluation and failure analysis

Compute metrics from individual aligned forecast rows, with `error = forecast − actual`:

- **MAE (MW):** average absolute hourly miss; the primary selection metric.
- **RMSE (MW):** highlights large misses.
- **WAPE (%):** `100 × sum(abs(error)) / sum(abs(actual))`; aggregate the numerator and denominator, not subgroup percentages.
- **MAPE (%):** average per-hour percentage miss, with a positive-demand input contract.
- **Bias (MW):** mean signed error; positive means overforecasting.
- **80% interval coverage and mean width:** measured only where the selected model's calibrated bounds exist.

Compare every model on identical test rows. Inspect the error distribution, largest misses, monthly and hourly errors, and a clearly defined high-demand subset. If a high-demand threshold is derived from test demand, label it a retrospective diagnostic rather than an advance alert rule. Treat partial months or small subsets as limited evidence. Present both absolute and percentage improvements against a named baseline, and preserve regressions in the discussion.

Use feature sensitivity or permutation results only with their stated method and limitations. Correlated lags can share signal; importance is not a causal effect. Without external event evidence, describe an unusual day as a forecast failure rather than inventing a weather, outage, or market explanation.

## Power BI implementation

Deliver a native report project, import queries, semantic measures, theme, and a build/QA runbook. The dimensional model separates unique hourly actual history from forecasts that repeat an actual value once for each model. Date and model dimensions filter the appropriate facts through single-direction relationships.

The report should let a reader inspect demand history, compare historical test performance, and review the unscored next-day demonstration. Make the selected model, date range, split, units, and historical nature visible. Demand energy totals come from the unique demand fact; accuracy comes from forecast rows for a single selected model. Missing future actuals must stay blank, not become zero errors.

The native source project has been authored; native Power BI Desktop refresh and visual acceptance remain a separate validation step. Source-schema validation and static measure checks do not establish that Desktop renders the report correctly. Open the project in supported Desktop, configure the export folder, refresh, reconcile its cards to the saved Python metrics, test slicers and empty selections, inspect every page, and save genuine report screenshots before claiming the Power BI implementation has been tested visually.

## Reproducibility and handoff

Keep a single executable path from pinned raw data to cleaned history, features, candidate scores, selected model, calibrated predictions, diagnostics, figures, and BI exports. Record package versions, parameters, random seeds, source hashes, and the split configuration. Provide a notebook that executes top to bottom and includes the figures and interpretation necessary to review the result.

The project is complete for publication when the reproduction commands succeed, calculations and forecast-time invariants pass, quantitative claims match saved outputs, the native BI report has been refreshed and checked, and the publication checklist records any remaining gap honestly. Deployment and monitoring belong to a later production extension unless actually implemented and tested.

## Suggested 10-week working plan

This is a planning estimate of 7–9 hours per week, not an assertion of time spent or a prerequisite to use completed work. Aim for an inspectable baseline result in the first three weeks.

| Week | Deliverable | Acceptance evidence |
| --- | --- | --- |
| 1 | Decision frame, scope, source selection and data contract | Source definitions, rights, direct URL, checksum and sample records |
| 2 | Cleaning and quality audit | Complete UTC grid, missing/duplicate counts, unit and time checks |
| 3 | EDA and daily/weekly baselines | First reproducible seasonal charts and chronological validation scores |
| 4 | Time-safe features and candidate models | Availability tests and validation comparison on identical rows |
| 5 | Freeze chosen model and calibrate intervals | Saved selection rationale, final fit period and 2024 interval rule |
| 6 | Score 2025 and diagnose failures | Untouched-test table, segment errors, worst cases and coverage |
| 7 | Power BI model and report pages | Correct relationships, measures and no multiplied actual totals |
| 8 | Native report QA and reproducibility | Desktop refresh, Python/BI reconciliation and genuine screenshots |
| 9 | Write the case study and review limitations | Source-backed findings, defensible actions and calibrated claims |
| 10 | Package portfolio, resume and LinkedIn materials | Working links, clean repository, publication checklist and final review |

Weather, operational monitoring, automated refresh, or cost scenarios should enter a later iteration only when their source and validation needs are met. They should not delay a well-scoped historical demand forecasting case study.
