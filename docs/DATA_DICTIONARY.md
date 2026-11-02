# GridCast data dictionary

The canonical observation grain is **one one-hour PJM balancing-authority interval**, keyed by its UTC start. Source data, cleaned observations, feature replacements, and model forecasts serve different purposes. Blank numeric CSV cells mean unavailable values, not zero. CSV numeric exports use six decimal places; analytical JSON and summary metrics retain fuller precision.

## Source snapshot

`data/raw/eia_pjm_hourly_2019_2025.csv` has 61,368 rows, one per UTC interval from 2019-01-01 00:00 through 2025-12-31 23:00. It is a checksummed extract of the official EIA workbook's `Published Hourly Data` sheet. Source descriptions and retrieval details are in `docs/SOURCES.md` and `data/raw/eia_pjm_manifest.json`.

| Field | Type / unit | Definition |
|---|---|---|
| `BalancingAuthority` | Text | EIA BA code; every row must be `PJM` |
| `DateTimeUTC` | ISO 8601 datetime ending `Z` | Interval start; unique canonical key; original EIA hour-ending instant minus one hour |
| `IntervalEndUTC` | ISO 8601 datetime ending `Z` | Original source UTC time; exactly one hour after `DateTimeUTC` |
| `OriginalDemandMWh` | Nullable number, MWh | Original demand reported to EIA; unchanged, including suspect values |
| `DemandForecastMWh` | Nullable number, MWh | Published BA demand forecast; retained for provenance, not used as a model input or aligned benchmark |
| `ImputedDemandMWh` | Nullable number, MWh | Explicit EIA replacement value when supplied; a nonblank value flags the original for exclusion |
| `AdjustedDemandMWh` | Nullable number, MWh | EIA's reported demand after its replacement policy; retained for comparison, not silently used as actual truth |
| `SourceLocalDate` | Date `YYYY-MM-DD` | Original source local reporting day |
| `SourceHour` | Integer-like source field | Original hour number within the source reporting day; do not use as the UTC key |
| `SourceLocalTime` | Naive ISO datetime | Original source local hour-ending label, retained for inspection |
| `SourceTimeZone` | Text | Original source timezone name, `Eastern` in this snapshot |

The raw workbook `eia_pjm_full_history.xlsx` remains unchanged locally and is excluded from Git. `eia_pjm_workbook_notes.json` contains source column definitions. `eia_pjm_initial_audit.json` records source structure and counts. No raw source field contains a guarantee that its historical value was available at a particular forecast issue time.

## Cleaned observations and history CSV

`data/processed/demand_hourly.csv` and `data/powerbi/FactDemand.csv` contain the same nine-column history export, with 61,368 rows. The filename `FactDemand.csv` refers to the export contract; Power Query imports a smaller semantic table, described below.

| Field | Type / unit | Definition and valid use |
|---|---|---|
| `DateTimeUTC` | UTC datetime string | Unique interval-start key; one regular hourly slot even when actual demand is null |
| `ActualMW` | Nullable number, average MW | Valid original hourly MWh divided by one hour; excluded source values remain blank; use for observed demand and scoring |
| `OriginalDemandMWh` | Nullable number, MWh | Untouched original source value; audit only, not the cleaned observation series |
| `IsActualValid` | Boolean | `True` if original demand passed the implemented quality rules; `False` for 178 excluded observations |
| `FeatureInputMW` | Number, average MW | Actual demand where valid; otherwise past-only replacement at 168, 24, or one hour, in that priority order; model input only |
| `Date` | Date | UTC calendar date of the interval start; foreign key to `DimDate` |
| `HourUTC` | Integer 0–23 | UTC hour of interval start |
| `DateLocal` | Date | Local date of interval start after converting UTC to `America/New_York`; the first row belongs locally to 2018-12-31 |
| `HourLocal` | Integer 0–23 | Eastern local hour of interval start, with daylight saving time handled by timezone conversion |

An original value is invalid if missing, nonfinite, nonpositive, accompanied by an EIA imputation, different from a nonblank EIA adjusted value, or listed among the four reviewed 2020 spikes in `docs/anomaly_review.csv`. The frozen run flags 178 rows. Feature replacement never changes `ActualMW` or supplies ground truth for scoring. A missing observation does not remove its UTC row.

There is no naive local-datetime join key. The autumn repeated local hour is represented by two different UTC rows; the missing spring hour does not gain a synthetic actual. `Date`/`HourUTC` and `DateLocal`/`HourLocal` must not be interchanged silently. Annual summaries use UTC calendar years.

## Forecast fact export

`data/powerbi/FactForecast.csv` has grain **UTC target interval × model × split**. Its composite key is (`DateTimeUTC`, `Model`, `Split`), with 131,544 rows in the frozen run: five models over 8,760 validation hours, 8,784 calibration hours, and 8,760 test hours, plus 24 historical next-day rows for the champion only. No training predictions are included.

| Field | Type / unit | Definition |
|---|---|---|
| `DateTimeUTC` | UTC datetime string | Target interval start |
| `Date` | Date | UTC date of target start; foreign key to `DimDate` |
| `HourUTC` | Integer 0–23 | UTC target hour |
| `ForecastOriginUTC` | UTC datetime string | Target day's midnight UTC batch origin |
| `HorizonHours` | Integer 1–24 | Position within the batch, `HourUTC + 1`; target starts `(HorizonHours − 1)` hours after origin |
| `Model` | Text | Foreign key to `DimModel`: `DailyNaive`, `WeeklyNaive`, `Ridge`, `HistGB_small`, or `HistGB_large` |
| `Split` | Text | `validation` = 2023; `calibration` = 2024; `test` = 2025; `future` = historical 2026-01-01 demonstration |
| `ActualMW` | Nullable number, average MW | Cleaned actual matching the history fact; blank for invalid observations and all `future` rows |
| `ForecastMW` | Number, average MW | Nonnegative point forecast from the indicated model |
| `Lower80MW` | Nullable number, average MW | Champion-only pointwise nominal 80% lower bound for calibration, test, and future rows, clipped at zero |
| `Upper80MW` | Nullable number, average MW | Corresponding upper bound |

The actual is repeated across model rows. Do not sum it across models or mix splits when calculating accuracy. Test metrics use one model and valid actual/forecast pairs; 2025 supplies 8,735 such pairs per model. Future rows have no actual and never enter error denominators. Interval bounds are not demand observations, capacity limits, or simultaneous bounds for an entire day.

## Power BI semantic tables

The authored semantic model imports four tables. Power Query parses ISO timestamps, normalizes to UTC explicitly, then removes the timezone marker for the Desktop datetime type. This retains UTC wall-clock values; it does not convert them to the computer's timezone.

### `FactDemand`

The imported semantic table keeps `DateTimeUTC` (datetime), `Date` (date), `HourUTC` (integer), `DateLocal` (date), `HourLocal` (integer), and `ActualMW` (nullable double) from the export. Power Query adds:

| Field | Type | Definition |
|---|---|---|
| `DayOfWeekNumberLocal` | Integer 1–7 | Monday = 1 through Sunday = 7, derived from `DateLocal` |
| `DayOfWeekNameLocal` | Text | English local weekday name; sort by `DayOfWeekNumberLocal` |

`FeatureInputMW`, `OriginalDemandMWh`, and `IsActualValid` are deliberately excluded from the imported semantic table. Completeness is inferred from the complete UTC grid and nonblank `ActualMW`. Model feature replacements cannot accidentally appear as observed demand in the report.

### `FactForecast`

All eleven forecast-export fields above are imported. `DateTimeUTC` and `ForecastOriginUTC` use Desktop datetime; `Date` uses date; `HourUTC` and `HorizonHours` use integer; `Model` and `Split` use text; actuals, forecasts, and interval bounds use nullable double.

### `DimDate`

One row per UTC calendar date, 2019-01-01 through 2026-01-01 inclusive: 2,558 rows. The final date supports the historical next-day forecast and does not imply observed demand exists for that date.

| Field | Type | Definition |
|---|---|---|
| `Date` | Date | Unique date key |
| `Year` | Integer | UTC calendar year |
| `MonthNumber` | Integer 1–12 | Month sort key |
| `MonthName` | Text | English month name; sort by `MonthNumber` |
| `YearMonth` | Text `YYYY-MM` | UTC year-month label |
| `DayOfWeekNumber` | Integer 1–7 | UTC weekday, Monday = 1 |
| `DayOfWeekName` | Text | English UTC weekday; sort by `DayOfWeekNumber` |
| `IsWeekend` | Boolean | UTC date falls on Saturday or Sunday |

### `DimModel` and relationships

`DimModel` has one text field, `Model`, with five unique rows matching the candidate names above. The three active relationships filter from dimension to fact, single direction:

| One side | Many side |
|---|---|
| `DimDate[Date]` | `FactDemand[Date]` |
| `DimDate[Date]` | `FactForecast[Date]` |
| `DimModel[Model]` | `FactForecast[Model]` |

There is no fact-to-fact join. The model selector affects forecasts; historical observations are a single source series. Test cards require exactly one selected model. DAX measures named `Test …` enforce `Split = "test"`. See `powerbi/measures.dax` for exact formulas and `powerbi/validation/expected_test_metrics.csv` for expected Desktop results.

## Analytical summary outputs

| File | Grain / fields |
|---|---|
| `outputs/model_metrics.csv` | Model × split; `Model`, `Split`, `N`, `MAE_MW`, `RMSE_MW`, `WAPE_pct`, `MAPE_pct`, `Bias_MW`; 15 rows |
| `outputs/test_metrics_by_horizon.csv` | Champion test horizon 1–24; `HorizonHours` plus the same metric fields; 24 rows |
| `outputs/test_metrics_by_month.csv` | Champion UTC test month; `Month` plus the same metric fields; 12 rows |
| `outputs/test_monthly_diagnostics.csv` | Champion UTC test month; `Month`, `MAE_MW`, `Bias_MW`, `Coverage`, `N`; `Coverage` is a fraction 0–1 |
| `outputs/annual_demand.csv` | UTC year; historical column `DateTimeUTC` contains the **integer year**, then `MeanMW`, `PeakMW`, `ObservedEnergyMWh`, `ValidHours`, `TotalHours`, `CoveragePct`; seven rows |
| `outputs/data_quality.json` | Structural/quality counts, annual completeness and valid extrema, UTC limits, replacement rule, and warmup count |
| `outputs/run_summary.json` | Selected model and criterion, fit counts, final test metrics, interval coverage/width/radii, training high-demand threshold, peak diagnostics, experiment description, and run metadata |
| `outputs/paired_bootstrap.json` | Descriptive paired seven-day circular-block bootstrap, 2,000 repetitions with seed 42; mean MAE gain and 95% quantile bounds; generated by the executed notebook |

For metric CSVs, error is forecast minus actual; negative bias means underforecasting. `N` counts valid scored hourly pairs. MAE and RMSE are MW; WAPE and MAPE fields suffixed `_pct` are stored on a **0–100 percent scale**. Power BI's formatted WAPE and coverage measures are stored as fractions, so their raw values use a different scale. Never average subgroup WAPE percentages: recompute aggregate absolute error divided by aggregate actual demand.

`ObservedEnergyMWh` sums only valid one-hour demand observations. It omits missing-hour energy and must not be called complete annual consumption. `MeanMW` averages valid observations, and `PeakMW` is the maximum valid hourly mean, not an instantaneous peak. `CoveragePct` is valid observed hours divided by all expected hourly slots, multiplied by 100.
