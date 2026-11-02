# Windows Power BI Desktop compatibility gate

Status: **untested — no Windows Power BI Desktop runtime was available.** This checklist applies to the local PBIP/Desktop artifact. The separate real Service report has passed refresh, persistent DAX parity and observed rendering/filter checks; see [Service evidence](SERVICE_VALIDATION.md). Those results do not close any Windows item below.

Record the Desktop version, Windows version, date, reviewer, Python run identifier, and the four CSV file hashes with the completed review. Store screenshots and the refreshed report alongside the release evidence.

| Check | Expected behavior | Evidence to retain |
|---|---|---|
| Open project | `GridCast.pbip` loads all four pages and the four-table model without a blocking error. | Desktop version and open-project screenshot. |
| Set path and refresh | `DataFolder` points at this run's `data/powerbi`; all four facts/dimensions refresh with no query/type errors. | Refresh success and table row counts. |
| Source provenance | Report describes EIA-930 PJM balancing authority demand; it does not claim direct PJM metered ingestion. | Source attribution screenshot. |
| Date model | Unique `DimDate[Date]`, marked date table, active 1:* single-direction relationships, no fact-to-fact relationship. | Model view screenshot. |
| Missing actuals | Blank actuals remain blank; there are no imputed actuals and no conversion to zero. | Inspect known missing rows from the export. |
| Historical totals | Clear date filters; compare observed energy, mean, hourly peak, expected/observed/missing hours and completeness with `validation/export_reconciliation.json`. | Comparison receipt; relative tolerance 1e-6 for numeric aggregates. |
| UTC/local labels | Main date slicers use UTC; profile charts use America/New_York local hour/weekday. Repeated DST hour remains two UTC observations. | Check one spring-forward and one fall-back date against the CSV. |
| Single-model safeguard | Clear the model slicer, then attempt multi-selection if the UI permits it; aggregate forecast KPI values are blank unless exactly one model is in context. | Screenshot and reviewer note. |
| Full test metric parity | Clear test date filter. For every model, compare valid test hours, actual/forecast MWh, mean MW, MAE, RMSE, WAPE and bias with `validation/expected_test_metrics.csv`. | Exported Desktop table joined to expected CSV; absolute tolerance 1e-4 MW/MWh or relative 1e-8, fractions tolerance 1e-8. |
| Interval parity | Only champion has interval metrics. Champion interval count, coverage and mean width agree with expected metrics. | Exported table; verify percent formatting uses fraction ×100. |
| Empty/zero/filter edge cases | Execute all four read-only queries in `queries/`; compare actual raw exports with `verify_native_results.py`. Twelve context cases must preserve no/multiple/zero-model BLANKs, empty count0, missing actual exclusion, zero covered of one interval0%, and future/validation isolation. | Real query exports, execution screenshot, model/refresh identifiers and successful export comparison receipt. |
| High-demand diagnostics | Threshold is the fixed initial-training p90, not a test-derived percentile. Selected champion high-demand test count/MAE/bias/80% coverage match `expected_test_metrics.csv`. Coverage uses only valid bounded high-demand pairs and changes with model/date filters. Monthly MAE and UTC-hour bias recompute on the filtered test pairs. | Exported values and diagnostic-page screenshot, including the small coverage card and resized definition note. |
| Model comparison interaction | Select champion in slicer; scorecard cards/trend respond, comparison table still shows all models. | Screenshot with selected model and complete comparison table. |
| Date filter behavior | Select a month in 2025; metrics recompute from hourly pairs, and both actual/forecast trend lines filter together. Compare WAPE with a recomputation of that month's rows, not an average of daily percentages. | Month-specific export/calculation. |
| Future isolation | Test cards never count `future` rows. Historical-next-day page has only 24 hourly timestamps beyond source cutoff and no actuals. Select champion for the interval display. | Future table export. |
| Shared axis | Actual and forecast are on one MW axis. The daily chart is explicitly mean MW. Future bound lines share the forecast axis. | Screenshot and formatting inspection. |
| Sort order | Month, weekday and local-hour categories are chronological rather than alphabetic. | Profile chart screenshots. |
| Visual fit | Import the theme, inspect every page at 100% and Fit to page: no clipped titles, unexplained blank card, overlapping controls or unreadable numbers. | All four page screenshots. |
| Accessibility | Add meaningful alternative text to charts/cards, verify keyboard tab order, color contrast and text labels. Do not encode actual/forecast distinction only by color. | Reviewer notes; line style/legend inspection. |
| Save/reopen | Save refreshed project, close, reopen and verify slicer state and visuals. Produce PBIX through Desktop Save as if required. | Refreshed PBIP/PBIX and final screenshots. |

Known expected differences: visual number formats round values; underlying exports must match within the stated tolerance. The date-window controls can legitimately change totals. Nonchampion interval measures are intentionally blank. Historical energy excludes missing/invalid intervals. The next-day forecast is historical, not current.

Release decision: mark complete only after native errors are corrected, metric parity is demonstrated, and screenshots are reviewed. Do not turn this checklist into a completed claim merely because the authored JSON passes validation.
