# GridCast model card

## Purpose and status

GridCast is a retrospective study of hourly **PJM balancing-authority demand reported through EIA-930**, plus a Power BI decision-support prototype. It supports portfolio review, reproducible model comparison, and analyst investigation of demand patterns and forecast errors. It has not been validated for dispatch, reserve procurement, electricity trading, or other operational decisions.

The current champion is `HistGB_small`, selected using 2023 hourly mean absolute error (MAE). Its saved estimator is `models/champion.joblib`; feature construction and cleaning remain in `src/gridcast/core.py`. This binary contains fitted weights, not a live data feed or an independently deployable forecasting service. The illustrative next-day output is **1 January 2026 UTC**, based on the frozen history ending in 2025; it is not a forecast for the present date.

Numbers below come from `outputs/run_summary.json` and `outputs/model_metrics.csv` in the frozen run. Source acquisition, units, anomalies, and attribution are documented in `docs/SOURCES.md`.

## Forecast task and information set

Issue one batch at **00:00 UTC each day**, predicting the 24 one-hour intervals beginning at that origin. `HorizonHours` is a position numbered 1–24: position 1 predicts the interval starting at the origin, and position 24 starts 23 hours later. It is not a count of full elapsed hours from issuance to target start. UTC batches differ from PJM's local market days and stay 24 intervals long across daylight saving transitions.

The target is hourly average demand in MW. The source records MWh for an exactly one-hour interval, making the numerical conversion MWh / one hour. These are hourly means, not instantaneous peak readings.

The experiment assumes complete observations for intervals starting through `origin − 1 hour` are available at issuance. The newest lag used for the last target in a batch is that previous interval. **EIA's public release is typically about one hour after an operating hour ends**, so its public feed cannot satisfy this immediate-availability assumption. An operational implementation needs an appropriately timed feed or older features and a new evaluation. The frozen workbook also contains retrospective revisions and ex-post quality flags. This is a cleaned historical benchmark, not an as-of-vintage deployment replay.

## Data and exclusions

The selected source covers 61,368 continuous UTC hourly slots during 2019–2025. Of these, 178 target observations are excluded: 167 missing originals, seven nonmissing originals flagged by EIA imputation/adjustment, and four manually reviewed 2020 training-period spikes. The review ledger preserves those four original values and the inferential basis; they are not operator-confirmed corrections and do not impose a ceiling on future demand.

Excluded targets stay null. Their feature-history inputs use the first available prior value at 168, 24, or one hour, in that order; each replacement uses only earlier inputs. EIA's imputed demand is not substituted as observed target truth. The first 336 hours are unavailable for fitting because the longest lag needs a two-week history. Scoring excludes missing/invalid actuals, never treating them as zero or replacements.

## Features and candidates

There are 22 features, constructed for each target interval:

| Feature family | Implementation |
|---|---|
| Local calendar | Hour, weekday 0–6, month 1–12, weekend indicator, and UTC offset in hours, using `America/New_York` |
| Daily harmonics | Sine and cosine of local hour for harmonics 1, 2, and 3, with a 24-hour period |
| Annual harmonics | Sine and cosine of local day-of-year for harmonics 1 and 2, with a 365.25-day period |
| Demand lags | 24, 48, 168, and 336 elapsed UTC hours |
| Past windows | 24-hour and 168-hour rolling means, plus a 168-hour sample standard deviation, all calculated after shifting demand by 24 hours |

No future realized weather, generation, interchange, or demand enters these features. No holiday indicators, price inputs, or explicit long-term growth variable are included. A 168-hour lag preserves elapsed UTC time and can shift by an hour relative to local time around daylight saving changes.

All candidate settings are defined in `scripts/run_pipeline.py`. The run uses Python 3.12.14 and scikit-learn 1.9.1; the full environment is in `requirements-lock.txt`. Unspecified estimator arguments use that pinned version's defaults.

| Candidate | Exact configured settings |
|---|---|
| `DailyNaive` | Forecast equals the feature-history value 24 hours earlier |
| `WeeklyNaive` | Forecast equals the feature-history value 168 hours earlier |
| `Ridge` | `StandardScaler()` followed by `Ridge(alpha=100.0)` |
| `HistGB_small` | `HistGradientBoostingRegressor(max_iter=180, max_leaf_nodes=15, learning_rate=0.06, l2_regularization=10, early_stopping=False, random_state=42)` |
| `HistGB_large` | `HistGradientBoostingRegressor(max_iter=300, max_leaf_nodes=31, learning_rate=0.05, l2_regularization=10, early_stopping=False, random_state=42)` |

Tree models retain the default squared-error loss; MAE is the external selection criterion. Forecasts are clipped below at zero before export and scoring. The ridge scaler is fitted on the applicable fit partition, not on the full dataset. Disabling early stopping avoids an internal random validation split.

## Chronology and selection

| Partition | UTC years | Use |
|---|---|---|
| Initial fit | 2019–2022 | Fit three estimators on 34,647 eligible, valid target rows |
| Validation | 2023 | Compare all five candidates on 8,735 valid actuals; select minimum MAE, with model name as a deterministic tie-breaker |
| Final fit | 2019–2023 | Refit estimators once on 43,382 eligible, valid target rows |
| Calibration | 2024 | Calibrate champion intervals on 8,737 valid actuals; no model reselection |
| Test | 2025 | Evaluate frozen estimators on 8,735 valid actuals from 8,760 predicted intervals |

Weights remain frozen after the final fit. Observed demand from later days updates permissible lagged inputs, but no retraining occurs in 2024 or 2025. All models use identical scored actuals within a partition. Missing 2025 actuals remove 25 hours from the accuracy denominator. There is no random train/test split.

## Results and tradeoffs

| Model | 2025 MAE, MW | 2025 RMSE, MW | 2025 WAPE |
|---|---:|---:|---:|
| Daily persistence | 4,863.03 | 6,438.58 | 5.05% |
| Weekly persistence | 8,418.11 | 11,583.51 | 8.74% |
| Ridge | 4,331.87 | **5,704.55** | 4.50% |
| Selected `HistGB_small` | **4,219.45** | 5,793.44 | **4.38%** |
| `HistGB_large` | 4,487.09 | 6,225.50 | 4.66% |

The selected model reduces test MAE by **13.23%**, or 643.58 MW, relative to the stronger naïve comparator, daily persistence. It is not best on every metric: **Ridge has lower test RMSE**. Selection remains tied to the predeclared validation MAE criterion; the observed test tradeoff does not justify retroactively changing that criterion.

Champion mean error, defined as forecast minus actual, is **−1,464.97 MW**. On the high-demand diagnostic subset, fixed at the initial training 90th percentile of **111,972.4 MW**, there are 1,487 scored test hours, MAE is **7,891.57 MW**, and bias is **−6,592.89 MW**. This systematic underforecasting is material. The model cannot be presented as reliably handling the most stressed hours.

Daily peak magnitude MAE is 5,024.70 MW across 363 complete UTC days. This compares each day's maximum predicted hourly mean with its maximum actual hourly mean; it does not test peak-time accuracy or instantaneous peaks. `outputs/test_metrics_by_month.csv` and `outputs/test_metrics_by_horizon.csv` preserve finer diagnostics.

## Prediction intervals

The champion has nominal 80% **pointwise** prediction intervals. For each of the 24 horizon positions, sort the absolute 2024 calibration residuals and choose order statistic `ceil((n + 1) × 0.80)`, capped at `n`. Add/subtract that radius from the point prediction; clip the lower bound at zero. Radii remain fixed in test and historical next-day output. Other candidates and the validation rows have no interval bounds.

On the fixed high-demand subset, coverage is only **47.95% (713 of 1,487 hours)**. The 25 missing test actuals are a contiguous25-hour block around the autumn clock change, so measured accuracy does not validate that missing transition.

Test coverage is **78.58%**, with a mean width of **13,185.13 MW** on valid scored hours. This is measured empirical coverage, not a guaranteed probability for the next forecast. Serial dependence, demand shifts, subset behavior, and differing historical data vintages limit exchangeability assumptions. The bounds do not provide simultaneous 80% coverage of all 24 intervals, and summing bounds does not produce a calibrated daily-energy interval. Calibration-row coverage is in-sample with respect to the radii and is not an independent interval test.

## Limits and next release

The study does not establish superiority over PJM's own issued forecasts, realized savings, fewer outages, lower emissions, or improved dispatch. There is no causal identification or measured weather effect. The test year has now been examined; any weather, holiday, latency, or retraining experiment must use a fresh holdout or clearly labeled nested historical evaluation.

Before operational use, resolve source latency and historical vintage availability, define issuance against the intended PJM business day, add archived forecast-weather inputs if appropriate, stress-test extremes, and monitor bias and coverage. The separate Power BI Service implementation has now passed real refresh, persistent DAX parity and the observed visual/filter checks; see `powerbi/SERVICE_VALIDATION.md`. Windows PBIP/Desktop compatibility remains untested. No operational deployment or public sharing has been performed.
