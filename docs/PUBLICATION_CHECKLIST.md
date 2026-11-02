# Publication checklist

Use this checklist before describing GridCast as completed on a resume, LinkedIn, or a portfolio. A checked box needs the named evidence, not just an intention or an existing file. Leave an unperformed check open and describe its effect on the claim.

The Power BI implementation is verified in **Service**. The Windows section records a separate, unclaimed compatibility scope; its open boxes do not negate the completed Service evidence. Public release still requires authorization and working public links.

## Sources and data

- [x] The source notes identify EIA's PJM regional hourly demand, its population, field definition, original MWh units, hour-ending timestamps, and relevant source caveats.
- [x] The saved manifest records direct download URLs, retrieval time, file sizes and SHA256 checksums; the pipeline verifies those hashes.
- [x] The reported observation period matches accepted records, rather than the retrieval date or an assumed full year.
- [x] The quality report records 61,368 UTC hours, 178 masked measured targets (167 missing, seven additional source-flagged, four reviewed training anomalies), duplicate checks, and a separate count of causally filled feature inputs.
- [x] The four manually excluded training anomalies have a source-backed review ledger and are described as inferred anomalies, not operator-confirmed corrections.
- [x] Invalid scored targets remain missing. The separate feature-input fill uses only prior week/day/hour observations and never becomes a scored actual.
- [x] A sample of original records reconciles to the extracted demand; interval start is hour ending minus one hour.
- [x] UTC uniqueness, hourly continuity, daylight-saving calendar conversion and annual boundaries have been checked.
- [x] The rate/energy distinction is correct: hourly average MW, hourly MWh, and peak MW have separate meanings. Annual energy is labeled as a sum of valid observed hours, with valid/total hour counts; missing targets are not silently counted as zero consumption.
- [x] Source attribution and redistribution terms are recorded. Any raw data included publicly is permitted; code licensing does not relicense the input data.

## Forecast design and evaluation

- [x] The issue time, 24 target intervals, horizon numbering, timezone and availability assumptions are stated.
- [x] Every lag and rolling feature reads observations before the daily origin for all 24 horizons; future-observation perturbation tests pass.
- [x] Preprocessing is fit only on the applicable training period; future labels do not influence feature filling, scaling, selection, or fitting.
- [x] Candidate selection uses 2023 validation MAE. The chosen specification is refit on 2019–2023 before interval calibration and final test scoring.
- [x] The 2024 calibration year and 2025 test year have separate roles; no test result is used to tune the published model or any of the 24 horizon-specific interval radii.
- [x] Daily/weekly persistence and the learned candidates are scored on identical test timestamps.
- [x] MAE, RMSE, WAPE, MAPE and signed bias reconcile from saved forecast rows. Improvement claims name the baseline, metric, period and denominator.
- [x] Nominal interval level, calibration method, realized test coverage and width are disclosed. The write-up does not promise guaranteed coverage under serial dependence or drift.
- [x] Error by season/time/horizon, largest misses, and a clearly defined high-demand diagnostic have been inspected; material weaknesses remain visible.
- [x] The next-day output is labeled an unscored historical demonstration. Its blank actuals are excluded from all accuracy calculations.
- [x] Historical revisions and unverified real-time reporting lag are disclosed; the exercise is not described as an operational as-of backtest.
- [x] Any weather extension uses archived forecasts issued by the origin, or is explicitly separated as an oracle/explanatory experiment.

## Reproducibility and evidence

- [x] Reproduced the full pipeline and tests in a separate fresh virtual environment installed from requirements-lock.txt; model, forecasts, history, and score files are byte-identical. Hosted CI has not run.
- [x] The saved model, split definitions, source hashes, export files and metric tables correspond to the same run.
- [x] The analysis notebook executes from top to bottom and retains its intended outputs; key figures have been visually inspected.
- [x] Charts state their units, population and period; their annotations and narrative claims match the computed values.
- [x] Core tests and export checks pass. Checks are recorded at their actual scope; a schema pass is not presented as an end-to-end visual pass.
- [x] No credentials, private paths, personal data, or accidental environment files appear in the material to be shared.
- [x] Repository instructions explain how to restore the pinned source and what to do if the upstream provider has revised a file.

## Power BI Service verification session · 31 October–1 November 2026

- [x] Signed-in account and My workspace were inspected in the local browser.
- [x] The supported CSV import workflow was opened; its UI identifies organizational OneDrive for Business as the upload destination.
- [x] Explicit approval for the four GridCast CSV contents and validation model creation was received after the numerical, lineage and consistency checks.
- [x] The four approved CSV contents were packaged as exactly four typed Excel Tables in `outputs/service-validation/GridCastValidation.xlsx`. Independent read-only verification compared all 2,019,765 data cells, exact headers and saved table ranges; ISO keys, booleans, numbers and blank actuals were preserved with zero numeric differences. See `outputs/service-validation/workbook_roundtrip.json`.
- [x] The workbook was uploaded through the ordinary organizational OneDrive UI. Its row shows the expected filename, 8.67 MB and **Private**; the details state **“This item is not shared.”** No public sharing was performed.
- [x] Power BI Service **Excel → Link to file** loaded the cloud workbook in Navigator. Exactly four Table entries were selected; the four duplicate Worksheet entries were left unselected. The session mapping is recorded without a personal cloud path in `outputs/verification/service_session_status.json`.
- [x] The Power Query editor loaded and the four canonical query transformations were applied while preserving the cloud workbook source. The resulting column counts are FactDemand 8, FactForecast 11, DimDate 8 and DimModel 1. Full imported row-count and metric parity checks remain separate.
- [x] The Service semantic model **GridCastValidation** was created. Its initial **Data refreshed** label shows **10/31/2026 10:40:29 PM** in the local UI; the subsequent manual refresh is documented separately below.
- [x] Exactly three active, single-direction, many-to-one relationships were manually created and verified in the Service list: FactDemand Date → DimDate Date; FactForecast Date → DimDate Date; FactForecast Model → DimModel Model. Actual screenshot: `outputs/verification/screenshots/03_service_relationships.jpg`.
- [x] The 28-measure TMDL patch on **DimModel** was applied successfully at **10/31/2026 10:46:39 PM** in the local UI, without changing source partitions. Persistence is supported by subsequent standalone queries that use the measures without **DEFINE** declarations. The earlier temporary syntax probe was preparatory evidence only.
- [x] A manual **OnDemand** refresh reached **Completed**, starting **10/31/2026 10:49:34 PM** and ending **10:49:39 PM** in the local UI. Actual screenshot: `outputs/verification/screenshots/04_service_refresh_completed.jpg`.
- [x] Five standalone queries were verified against their source through native copy, executed in the real Service engine without temporary measure definitions, and copied at full precision. Raw TSV, CSV and provenance are retained under `outputs/verification/service_exports/`. The first four exports pass `powerbi/validation/native_export_reconciliation.json`: history totals, five model comparisons, twelve contexts and blank/zero primitives.
- [x] The fifth native export's 24 import-integrity values match the independent oracle: four table row counts, split counts, unique keys, blank future actuals, and date/hour/origin/horizon consistency. These checks do not by themselves prove semantic-model column types.
- [x] Actual Service metadata and native measure-only TMDL reconcile all 28 measure expressions, descriptions and display folders, 27 numeric formats, compatible canonical column types, sort settings and the three canonical relationships. INFO.VIEW format blanks and documented Service differences are explained in `outputs/verification/service_exports/metadata_reconciliation.json`.
- [x] The saved Service report was reopened and its four pages/35 visuals were reviewed: history 10, test 9, diagnostics 11 and historical next day 5. Page order and landing page were saved, numeric units and clipping were corrected, category ordering and shared axes were checked, and genuine screenshots 06/09/10/11 were retained. See `outputs/verification/service_visual_acceptance.json`.
- [x] Actual DailyNaive and June 2025 model/date selections match expected card values; the comparison retains all five models. Screenshots 07/08 record those observed interactions. DAX context tests cover additional numerical edge cases without claiming every UI state was exhaustively exercised.
- [x] All 24 hourly timestamps and 72 rendered whole-MW future forecast/bound values reconcile to expected rounding. This is labeled **rendered UI evidence**, not a successful full-precision per-hour CSV download; the attempted download timed out.
- [x] Report/model Manage permissions were inspected: one owner direct-access result each, no report sharing links and no related model report shares. No ACL, user or link was added. This is the inspected workspace UI state, subject to organizational policies; no public sharing was authorized or performed. See `outputs/verification/privacy_access_check.json`.

The legacy local-Excel import was rejected by the Service backend, and the modern CSV/Excel iframe file chooser timed out. Screenshot `outputs/verification/screenshots/02_local_excel_upload_rejected.jpg` records the rejection. The successful cloud-file route now verifies transfer, model creation, persistent measures, refresh, DAX parity and the observed report/interaction states. No PBIX download/export or Windows compatibility is claimed. The Service unexpectedly displayed an automatic 60-day trial notice and then a 59-day header; no Start trial, upgrade, billing or terms action was taken. Access after expiry remains unverified. See the [Service receipt](../powerbi/SERVICE_VALIDATION.md) for evidence and limits.

## Native Power BI acceptance

Browser alternative: a connected Power BI Service session may support real model refresh, DAX evaluation and report screenshots on this Mac. Record Service evidence separately; do not mark Windows Desktop checks complete based on Service results. Native account/runtime checks below remain open.

- [ ] Open the native project in supported Power BI Desktop, set the data folder, and refresh successfully.
- [ ] Inspect all relationships and table grains; use unique demand rows for total energy and peak demand.
- [ ] Verify each model slicer and date slicer. Multiple/no-model selections do not produce misleading combined accuracy values.
- [ ] Reconcile the selected model's test MAE, WAPE and bias to Python for the full test period and a smaller date slice.
- [ ] Verify interval coverage against Python and keep bounds unavailable for models/splits without calibrated intervals.
- [ ] Confirm future actuals remain blank and unscored. Test an empty date selection and a partial period.
- [ ] Inspect every report page at normal reading size for labels, clipping, axis units, sorting, time conventions and useful interactions.
- [ ] Save actual Desktop report screenshots and record the Desktop version and refresh date. Do not substitute mockups for implementation evidence.
- [ ] If publishing to Power BI Service, verify the intended audience, permissions, refresh setup and report link. Public sharing is a separate, deliberate action.

Describe the local PBIP as a **source project prepared for Windows Desktop validation**. The separately saved report can be described as a **Power BI Service implementation with verified refresh, DAX and observed visual/filter checks**. Its genuine Service screenshots establish that scope; they do not establish Windows rendering or exhaustive accessibility testing.

## Case study and career claims

- [x] The case study explains the decision, population, data quality, protocol, model selection, final test findings, operational implications and limitations in that order.
- [x] Every numerical headline has a traceable table/figure, period, metric and comparison. Rounded numbers remain consistent across README, case study, resume and LinkedIn draft.
- [x] Interpretations are distinguished from observations. Feature importance and seasonality are not presented as causal findings.
- [x] Recommendations are proportional to the evidence, such as analyst review of weak hours or a proposed next experiment.
- [x] No claim implies deployed production use, avoided outages, improved reliability, procurement savings, price forecasts, or emissions reductions unless independently implemented and measured.
- [x] Scope and status are accurate: one regional historical prototype, any unperformed native BI checks, and any unimplemented weather/deployment extension are disclosed.
- [x] Public repository and rendered case-study links return HTTP 200 without authentication; four dashboard screenshots, the executed notebook and raw data downloads match local SHA256 values. See `outputs/publication/anonymous_access.json`. This does not claim a public interactive Power BI link.
- [x] The final resume/LinkedIn wording reflects work actually completed and tested. Proposed future work is not phrased in the past tense.

## Suggested evidence receipt

Record the following beside the published release or case study:

| Item | Record |
| --- | --- |
| Source retrieval timestamp and manifest | 2026-10-27T19:32:18Z; data/raw/eia_pjm_manifest.json |
| Accepted observation coverage and row count | 2019–2025 UTC; 61,368 hourly slots; 61,190 valid actuals |
| Pipeline run identifier or commit | Local uncommitted run; outputs/run_summary.json (2026-10-27); not publicly released |
| Environment/lock file | Python 3.12.14; requirements-lock.txt |
| Selected specification and final fit period | HistGB_small; 2019–2023; see docs/MODEL_CARD.md |
| Calibration period, level and 24 horizon-specific radii | 2024; nominal 80%; outputs/run_summary.json |
| Test period and metric table | 2025; outputs/model_metrics.csv; 8,735 valid hours per model |
| Tests and reproduction command results | 22 tests pass; outputs/reproduction_check.json; outputs/VALIDATION.md |
| Power BI Desktop version and refresh result | Pending native Windows Desktop check |
| Power BI Service model and runtime result | GridCastValidation; 28 persistent measures; three canonical/manual active relationships (seven engine relationships including four automatic-date edges); manual OnDemand refresh Completed 10/31/2026 10:49:39 PM local UI |
| Service numerical evidence | Five real standalone query exports and provenance under outputs/verification/service_exports/; first four reconciled by powerbi/validation/native_export_reconciliation.json; fifth import-integrity export matches all 24 expected values |
| Service visual evidence | Saved/reopened four-page report, 35 visuals; actual screenshots 06/09/10/11; baseline/June states 07/08; service_visual_acceptance.json |
| Service metadata/access evidence | Native metadata/TMDL reconciled; owner-only direct access and no sharing links in inspected UI; metadata_reconciliation.json and privacy_access_check.json |
| Screenshot locations and inspected pages | outputs/verification/screenshots; actual relationships/refresh 03/04, all four Service pages and two filter states; Python chart figures also inspected |
| Remaining limitations or unperformed checks | Nine Windows Desktop checks, PBIX download/export, public release authorization and unauthenticated links, exhaustive accessibility and post-trial Service access; full-precision per-hour future CSV download was not completed |

Follow-up evidence: outputs/verification/REVIEW_2026-10-31.md is the historical pre-Service audit. Current runtime, metadata, visual and access receipts document the subsequent Service pass. Windows compatibility remains untested. Public GitHub repository/case-study publication was authorized on 1 November 2026 and anonymous access was verified; interactive Power BI sharing remains separate.

This receipt is a factual handoff record. It does not require publishing to an external service or sending a post before the underlying work is ready for review.
