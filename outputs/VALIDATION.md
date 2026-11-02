# Validation receipt · GridCast first release

Validated locally on 27 October 2026 with Python 3.12.14 and the package versions in `requirements-lock.txt`. Observation window: 2019–2025. This receipt describes performed checks; it does not certify native Power BI execution.

| Check | Result and scope |
| --- | --- |
| Official source acquisition | EIA PJM full-history XLSX downloaded, source URL/time/bytes/SHA256 recorded. Canonical 2019–2025 CSV reproduced by repeat extraction with identical hash. |
| Source and UTC mapping | 61,368 unique consecutive hourly starts; all source intervals exactly one hour; ending-to-start conversion and year boundaries reconciled. |
| Cleaning | 178 invalid targets retained as missing; valid originals preserved; causal replacements exist only in feature inputs. Four training-only inferred anomalies have an explicit review ledger. |
| Forecast availability | All 24 target-hour feature rows unchanged when target-day/future actuals are perturbed or hidden. Lag/rolling boundary and causal-fill fallback checks pass. |
| Full experiment | Two same-environment runs and a third full fit in a separate fresh environment installed from requirements-lock.txt selected HistGB_small and produced byte-identical demand/forecast CSVs, score tables, and selected model. See `reproduction_check.json` and `clean_reproduction_check.json`. Run timestamps intentionally differ. |
| Automated tests | **17 passed in both environments**, including independent recomputation of all 15 candidate/split metric rows, horizon-specific calibration ranks and test coverage, missing actuals, origins, horizons, fact grains and dimension keys. |
| Notebook | Valid nbformat, executed top-to-bottom; 16 cells including eight executed code cells and seven embedded figures. No cell errors. Seven saved chart images were visually inspected for labels, units, clipping and consistency. |
| Notebook HTML preview | Generated from saved notebook outputs. Browser visual inspection of this HTML was not completed because the browser rejected local-file URLs; the notebook's saved chart outputs were inspected directly. |
| Power BI source | **44 PBIP/PBIR JSON files** passed cached official Microsoft schemas; **34 visuals**, **four model tables**, **27 measures**. Relationship/field reference checks passed. `model.bim` loading and formula execution are outside this schema check. |
| Power BI exports | 61,368 history rows; 131,544 forecast rows; five models; 8,735 valid test pairs per model. Local timezone, actual/history agreement, bounds, future nulls and aggregate expectations reconcile to Python. |
| Native Power BI | **Pending:** Windows Desktop loading, M refresh, DAX execution, slicer behavior, native rendering and real report screenshots. See `powerbi/NATIVE_ACCEPTANCE.md`. |
| CI workflow | Authored in `.github/workflows/validate.yml`; no hosted GitHub Actions run has been performed. |
| Public release | No GitHub repository, Power BI workspace report, LinkedIn post or portfolio page was published. |

## Reconciled numerical claims

- Selected model: HistGB_small, chosen using 2023 MAE and frozen after fitting through 2023.
- Valid 2025 test hours: 8,735 of 8,760 forecast intervals.
- MAE: 4,219.447131 MW; WAPE: 4.38200249%; RMSE: 5,793.435217 MW.
- DailyNaive MAE: 4,863.027819 MW; improvement: 13.23%.
- Nominal 80% interval coverage: 78.5804%; mean width: 13,185.131655 MW.
- High-demand subset: 1,487 hours above training p90 111,972.4 MW; bias −6,592.893198 MW.
- Ridge RMSE is lower than the champion's; do not claim the champion wins every objective.

The exact inputs, model scores, quality decisions and experiment roles remain in the manifest, `model_metrics.csv`, `data_quality.json`, `run_summary.json`, and the executed notebook. This is a retrospective cleaned-data benchmark using revised history and ex-post quality flags. Real-time data availability has not been established.

## Follow-up verification · 31 October 2026

The expanded review supersedes the original counts above for the current Power BI source: 45 schema files, 35 visuals, and 28 measures; 22 tests now pass. Full Linux pipeline, forecast, score and seven-chart notebook parity also pass. The [pre-Service review](verification/REVIEW_2026-10-31.md) records that phase; its then-open Service runtime gates were completed subsequently as recorded below.

## Actual Service verification · 31 October–1 November 2026

The separate saved **Power BI Service** report now passes the documented runtime scope. This update does not retroactively claim that the original authoring checks ran a native engine, and it does not close any Windows Desktop/PBIP compatibility item.

| Actual Service check | Verified evidence |
| --- | --- |
| Source transfer | Four approved CSV contents packaged as four Excel Tables; all2,019,765 data cells independently round-tripped with exact ISO strings/booleans/blanks and zero numeric differences; workbook upload observed in organizational OneDrive. |
| Model and refresh | GridCastValidation with28 persistent measures; three canonical active one-way relationships; manual OnDemand refresh Completed10/31/2026 10:49:39PM local UI. Actual screenshots03/04 retained. |
| Numerical parity | Five standalone no-DEFINE queries with native-copied source text, full-precision TSV/CSV and provenance. History, all five models, twelve contexts and blank/zero primitives reconcile; all24 import-integrity values also match. |
| Metadata | Actual INFO.VIEW exports and native measure-only TMDL verify definitions, compatible column types, sorting/date-table settings and27 numeric format strings; Service-generated artifacts and metadata-view limitations are documented. |
| Rendering and interactions | Saved/reopened four-page report with35 visuals; all pages reviewed. Actual DailyNaive and June model/date states match expected values; comparison retains five models. Genuine screenshots06–11 retained. |
| Future display | All24 timestamps and72 rounded rendered UI forecast/bound values reconcile. This is whole-MW display evidence, not a successful full-precision per-hour visual CSV download. |
| Access scope | Actual Manage permissions shows one owner direct-access result for report/model and no sharing links; no ACL changes or public sharing. Organizational policies still apply. |

Current receipts: [Service overview](../powerbi/SERVICE_VALIDATION.md), [session status](verification/service_session_status.json), [visual acceptance](verification/service_visual_acceptance.json), [access/licensing](verification/privacy_access_check.json), [native DAX reconciliation](../powerbi/validation/native_export_reconciliation.json) and [metadata audit](verification/service_exports/metadata_reconciliation.json).

Windows Desktop and local PBIP compatibility remain untested; no PBIX download/export is claimed. Public release requires separate authorization and unauthenticated link checks. The Service unexpectedly issued an automatic trial notice; no Start trial, upgrade, billing or terms action was taken, and continued access after expiry is unverified. No operational outcomes or financial savings were measured.
