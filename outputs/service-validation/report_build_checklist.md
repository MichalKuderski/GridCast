# Faithful Service report construction checklist

This is an exact field/position map extracted from the authored PBIR. It is a plan, not evidence that the35 visuals have been built or rendered. Build one private report on the validated four-table Service model; do not create separate reports/semantic models per page.

## One-time setup

- Save the report as `GridCast — PJM Demand Validation` in My workspace. Set each page to custom1280×900. The coordinates below are canvas pixels, not browser screenshot coordinates.
- For each visual: choose the built-in type, assign the fields below in the stated order, set General → Properties position/size, and set the title. A date field must be the actual Date/DateTimeUTC field, not its automatic date hierarchy.
- Use existing measures under DimModel; do not use implicit sums of fact actuals/forecasts. Card units and percent formats come from the persistent measure metadata.
- Use date-range slicers on DimDate[Date]. Model slicers use DimModel[Model], single select; save HistGB_small selected on test, diagnostics and historical-next-day pages. Keep UTC date labels and local-profile labels explicit.
- Sort every chart axis ascending by its category; local weekday must use its model sort-by-number property. Keep actual and forecast/bound measures in the same Y-axis well, with no secondary axis.
- Style one card/slicer/chart first, then copy/paste existing visuals within the report and replace fields. Microsoft documents Service copy/paste and exact pixel position/size in the General pane.

## Fastest construction order

1. Build **Test scorecard (9 visuals)** as the reusable layout.
2. Duplicate/copy its header, model/date slicers and four cards for **Diagnostics (11 visuals)**. Replace measures; reuse the trend and table slots as the two column charts; add the bottom coverage card and definition note.
3. Build **Demand history (10 visuals)** from copied cards/date slicer/chart primitives. It has no model slicer.
4. Build **Historical next day (5 visuals)** from the model slicer, copied header, line chart and table; add the interval note.
5. Reorder pages into01 history,02 test,03 diagnostics,04 historical next day. Match all35 entries below before recording completion.

## Exact visual map

### 01 \| Demand history — 10 visuals

| ID / built-in type | Exact field wells or text | Title | X,Y,W,H |
|---|---|---|---|
| HistoryTitle / Text box | Text: EIA-930 PJM balancing authority demand. UTC dates; local pattern charts use America/New_York. | GridCast \| PJM electricity demand | 30,15,1220,70 |
| DateSlicer / Slicer | Field: DimDate[Date] | UTC date range | 30,95,520,70 |
| CompletenessCard / Card (one measure) | Data: DimModel[Observation Completeness] | Observation completeness | 625,95,285,75 |
| MissingCard / Card (one measure) | Data: DimModel[Missing Hours] | Missing actual hours | 945,95,285,75 |
| EnergyCard / Card (one measure) | Data: DimModel[Demand MWh] | Observed energy proxy \| MWh | 30,180,380,105 |
| MeanCard / Card (one measure) | Data: DimModel[Mean Demand MW] | Mean demand \| MW | 440,180,380,105 |
| PeakCard / Card (one measure) | Data: DimModel[Peak Demand MW] | Maximum hourly mean \| MW | 850,180,380,105 |
| DemandTrend / Line chart | X axis: DimDate[Date]; Y axis: DimModel[Mean Demand MW] | Daily mean PJM demand \| MW | 30,305,1200,285 |
| WeekdayDemand / Clustered column chart | X axis: FactDemand[DayOfWeekNameLocal]; Y axis: DimModel[Mean Demand MW] | Mean demand by local weekday \| MW | 30,610,570,245 |
| HourlyDemand / Line chart | X axis: FactDemand[HourLocal]; Y axis: DimModel[Mean Demand MW] | Mean demand by local hour \| MW | 630,610,600,245 |

### 02 \| Untouched 2025 test — 9 visuals

| ID / built-in type | Exact field wells or text | Title | X,Y,W,H |
|---|---|---|---|
| TestTitle / Text box | Text: All accuracy measures below use the untouched 2025 test set. Select one model for cards and the trend; compare models in the table. | GridCast \| Forecast validation | 30,15,1220,70 |
| TestModelSlicer / Slicer | Field: DimModel[Model] | Select one model | 30,95,300,75 |
| TestDateSlicer / Slicer | Field: DimDate[Date] | UTC date range (intersected with 2025) | 360,95,530,75 |
| MAECard / Card (one measure) | Data: DimModel[Test MAE MW] | Hourly MAE \| MW | 30,185,280,100 |
| WAPECard / Card (one measure) | Data: DimModel[Test WAPE] | Test WAPE | 340,185,280,100 |
| BiasCard / Card (one measure) | Data: DimModel[Test Bias MW] | Bias \| forecast − actual MW | 650,185,280,100 |
| CoverageCard / Card (one measure) | Data: DimModel[Test Coverage 80] | 80% interval coverage | 960,185,270,100 |
| ForecastTrend / Line chart | X axis: DimDate[Date]; Y axis: DimModel[Test Actual MW], DimModel[Test Forecast MW] | Daily mean actual and forecast \| MW (2025 only) | 30,305,1200,280 |
| ModelComparison / Table | Columns: DimModel[Model], DimModel[Test Hours], DimModel[Test MAE MW], DimModel[Test RMSE MW], DimModel[Test WAPE], DimModel[Test Bias MW], DimModel[Test Coverage 80] | Model comparison \| same scored test pairs | 30,610,1200,245 |

### 03 \| Error and peak-risk diagnostics — 11 visuals

| ID / built-in type | Exact field wells or text | Title | X,Y,W,H |
|---|---|---|---|
| DiagnosticsTitle / Text box | Text: Test diagnostics expose seasonal weaknesses and underforecasting during high observed demand. Select a model; date filters remain UTC. | GridCast \| Error and high-demand risk | 30,15,1220,70 |
| DiagnosticModelSlicer / Slicer | Field: DimModel[Model] | Select one model | 30,95,300,75 |
| DiagnosticDateSlicer / Slicer | Field: DimDate[Date] | UTC date range (intersected with 2025) | 360,95,530,75 |
| TrainingThresholdCard / Card (one measure) | Data: DimModel[Training High Demand Threshold MW] | Fixed training p90 threshold \| MW | 30,185,280,100 |
| HighHoursCard / Card (one measure) | Data: DimModel[Test High Demand Hours] | High observed-demand test hours | 340,185,280,100 |
| HighMAECard / Card (one measure) | Data: DimModel[Test High Demand MAE MW] | High-demand MAE \| MW | 650,185,280,100 |
| HighBiasCard / Card (one measure) | Data: DimModel[Test High Demand Bias MW] | High-demand bias \| MW | 960,185,270,100 |
| MonthlyMAE / Clustered column chart | X axis: DimDate[YearMonth]; Y axis: DimModel[Test MAE MW] | Hourly MAE by UTC month \| MW | 30,305,1200,235 |
| HourBias / Clustered column chart | X axis: FactForecast[HourUTC]; Y axis: DimModel[Test Bias MW] | Mean forecast − actual bias by UTC hour \| MW | 30,565,1200,235 |
| HighCoverageCard / Card (one measure) | Data: DimModel[Test High Demand Coverage 80] | High-demand 80% coverage | 30,820,300,65 |
| HighRiskNote / Text box | Text: High-demand subset: actual test demand ≥ the fixed 90th percentile of initial 2019–2022 training demand after feature warmup. This uses observed test demand for retrospective diagnosis, not an advance alert rule. | Diagnostic definition | 360,820,870,65 |

### 04 \| Historical next day — 5 visuals

| ID / built-in type | Exact field wells or text | Title | X,Y,W,H |
|---|---|---|---|
| FutureTitle / Text box | Text: A 24-hour forecast after the frozen historical source cutoff. This is a historical demonstration, not a live forecast for today. | GridCast \| Historical next-day forecast | 30,15,1220,80 |
| FutureModelSlicer / Slicer | Field: DimModel[Model] | Select one model | 30,95,300,75 |
| IntervalNote / Text box | Text: Only the selected champion has prediction intervals. Bounds are pointwise hourly 80% intervals; they do not give an 80% simultaneous guarantee for the entire day. | Interpret the uncertainty | 365,100,865,80 |
| FutureTrend / Line chart | X axis: FactForecast[DateTimeUTC]; Y axis: DimModel[Future Forecast MW], DimModel[Future Lower 80 MW], DimModel[Future Upper 80 MW] | Hourly forecast and pointwise 80% bounds \| MW, UTC | 30,205,1200,330 |
| FutureTable / Table | Columns: FactForecast[DateTimeUTC], DimModel[Future Forecast MW], DimModel[Future Lower 80 MW], DimModel[Future Upper 80 MW] | Forecast review \| UTC hour | 30,560,1200,285 |

## Interactions and proof checks

- On the test page select the model slicer → Edit interactions → set the model-comparison table to **None**. Keep slicer filtering enabled for its cards/trend. The date slicer must continue filtering the comparison table.
- The history page is observed-only: missing actuals stay blank and completeness/missing counts remain visible. Do not substitute the imputed feature series.
- The test page always scores2025 because the measures enforce Split=test. With all dates and HistGB_small, compare against expected_test_metrics.csv:8,735 valid pairs, MAE≈4,219.45MW, WAPE≈4.3820%, bias≈−1,464.97MW, coverage≈78.5804%.
- The diagnostics page must expose June error and high-demand underforecasting. With all dates/champion: training threshold111,972.4MW; high-demand count1,487; MAE≈7,891.57MW; bias≈−6,592.89MW; high-demand coverage≈47.9489%. These are check values for this context, not static text to paste on the canvas.
- Historical-next-day chart/table: exactly24 UTC hourly timestamps for1January2026, all actuals blank. Use Future Forecast MW and the two future bounds, not Test Forecast MW. If blank dates remain visible, disable Show items with no data; a page filter FactForecast[Split]=future is a semantically equivalent safeguard for this page.
- Test no-model/multiple-model behavior; guarded forecast KPIs must be blank, not summed across models. Test June date filtering and compare the actual/forecast trend on the same axis.
- Add meaningful alt text and check the top-to-bottom/left-to-right keyboard order. Inspect every title and the small bottom high-demand coverage card for clipping at100% and Fit to page.
- Save/reopen the Service report, verify the four page names and source-model connection, then retain genuine screenshot evidence for each page plus the key slicer/interaction cases. A field-map checklist alone is not rendering proof.

References: [Service copy/paste](https://learn.microsoft.com/en-us/power-bi/visuals/power-bi-visualization-copy-paste), [General properties and pixel sizes](https://learn.microsoft.com/en-us/power-bi/visuals/power-bi-visualization-format-pane-overview), [visual interaction controls](https://learn.microsoft.com/en-us/power-bi/create-reports/service-reports-visual-interactions).
