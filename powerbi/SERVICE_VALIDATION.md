# Power BI Service validation receipt

The saved Service implementation has **four pages, 35 visuals and 28 persistent DAX measures**. Real refresh, numerical/context parity, model metadata, the observed slicer states and report rendering have been verified. Genuine screenshots are linked below. This validates the reconstructed **Service** report; it does not establish Windows PBIP/Desktop compatibility or a downloaded PBIX.

The session began on 31 October 2026 and continued into 1 November, in America/Chicago. The machine-readable [session status](../outputs/verification/service_session_status.json) controls the current scope.

## Source transfer and model

The user authorized transferring the four frozen GridCast CSV contents to the signed-in organizational OneDrive and creating the validation model. Those contents were wrapped in one workbook with exactly four native Excel Tables; no additional records, formulas or analysis were added. A read-only comparison verified all **2,019,765 data cells**, exact headers and table ranges, with zero numeric differences and exact ISO text, boolean and blank preservation. See the [workbook round-trip receipt](../outputs/service-validation/workbook_roundtrip.json).

The legacy local-Excel route was rejected by the Service backend, and the modern CSV/Excel iframe chooser timed out. The successful supported route was:

1. Upload the approved workbook through the ordinary organizational OneDrive UI.
2. Confirm its visible filename, 8.67 MB size, **Private** label and **“This item is not shared”** details.
3. Use **Power BI Service → Excel → Link to file**, selecting exactly the four Table entries rather than the four duplicate Worksheet entries.
4. Preserve the generated cloud source while applying the canonical Power Query transforms.
5. Create the semantic model **GridCastValidation**, three explicit active one-way many-to-one relationships, and 28 persistent measures on `DimModel`.

The canonical visible tables are `FactDemand` (61,368 rows), `FactForecast` (131,544), `DimDate` (2,558) and `DimModel` (5). Their transformed column counts are 8, 11, 8 and 1. Source observations are EIA-930 PJM balancing-authority demand; hourly MWh divided by one hour is average MW. Timestamps are converted explicitly to UTC before removing the zone for the model's datetime type. Invalid actuals remain blank.

The measure-only TMDL patch was applied successfully at **10/31/2026 10:46:39 PM** in the local UI without changing source partitions. A manual **OnDemand** refresh reached **Completed**, from **10:49:34 PM to 10:49:39 PM**. The [actual refresh screenshot](../outputs/verification/screenshots/04_service_refresh_completed.jpg) and [relationship screenshot](../outputs/verification/screenshots/03_service_relationships.jpg) record those native observations.

## Real engine and metadata checks

The five standalone validation queries were executed against the persistent model **without DEFINE declarations**. Their editor text was verified through native copy; full-precision **Copy Entire table** output was retained as raw TSV and CSV. These are real Service results, not Python expectations relabeled as native output.

| Query | Actual result | Evidence |
|---|---|---|
| History totals | 1 row, 7 columns | [history.csv](../outputs/verification/service_exports/history.csv) |
| Candidate test comparison | 5 rows, 18 columns | [models.csv](../outputs/verification/service_exports/models.csv) |
| Filter-context matrix | 12 rows, 29 columns | [contexts.csv](../outputs/verification/service_exports/contexts.csv) |
| Blank/zero primitives | 1 row, 5 columns | [primitives.csv](../outputs/verification/service_exports/primitives.csv) |
| Import integrity | 1 row, 24 columns | [import_integrity.csv](../outputs/verification/service_exports/import_integrity.csv) |

The first four comparisons pass the [native export reconciliation](validation/native_export_reconciliation.json). All 24 import-integrity values also match the independent CSV oracle, including counts, uniqueness, future actual blanks and date/hour/origin/horizon consistency. The [independent import receipt](../outputs/verification/service_exports/import_integrity_reconciliation.json) retains the comparison and raw-cell preservation checks. [Query provenance](../outputs/verification/service_exports/query_provenance.json) records source files, copy times, model identity and observed execution success.

The [metadata reconciliation](../outputs/verification/service_exports/metadata_reconciliation.json) independently checks the 28 persisted measures, expressions, descriptions, display folders, compatible canonical column types, sort settings, date table and three canonical relationships. All 27 numeric measure formats match actual native measure-only TMDL. The INFO.VIEW FormatString cells were blank; native TMDL resolved that metadata-view limitation. Documented Service-generated hidden artifacts and the dimension-key annotation difference are retained in that receipt rather than presented as exact structural equality with the local BIM.

## Saved report and observed interactions

The actual report is saved in this order, with **Demand history as the landing page**:

| Page | Visuals | Verified purpose | Actual screenshot |
|---|---:|---|---|
| Demand history | 10 | Valid-hour energy/completeness, daily mean demand, Monday–Sunday ordering and local-hour profile | [History](../outputs/verification/screenshots/10_service_history_page.jpg) |
| 2025 test scorecard | 9 | One-model accuracy cards, shared-axis actual/forecast comparison and all-five-model table | [Test](../outputs/verification/screenshots/06_service_test_page.jpg) |
| Error diagnostics | 11 | Monthly error and high-demand bias/coverage | [Diagnostics](../outputs/verification/screenshots/09_service_diagnostics_page.jpg) |
| Historical next day | 5 | Historical 1 January 2026 UTC point forecast and pointwise bounds | [Next day](../outputs/verification/screenshots/11_service_future_page.jpg) |

All four pages were independently reviewed after live formatting fixes. The review covers full-number display, clipped text, disabled table totals, ascending year-month order, Monday–Sunday ordering, an unsummed hour axis, actual DateTimeUTC rather than a date hierarchy, and a shared primary demand axis. The historical-next-day model filter was restored before saving.

Two additional actual UI states establish the observed filter behavior:

- [DailyNaive selection](../outputs/verification/screenshots/07_service_baseline_filter.jpg): **4,863.0 MW MAE, 5.05% WAPE, −62.5 MW bias**, with interval coverage blank. The comparison table retains five models.
- [June 2025 selection](../outputs/verification/screenshots/08_service_june_filter.jpg): **6,245.4 MW MAE, 6.03% WAPE, −5,026.2 MW bias and 66.5% coverage**. The date filter updates the scorecard and comparison.

These observations complement the numerical context matrix; they do not claim that every possible interaction or accessibility configuration was exhaustively tested.

The historical-next-day table's rendered accessibility rows cover all **24 UTC hours** and **72 whole-MW forecast/bound values**. The [rendered-display reconciliation](../outputs/verification/service_exports/future_visual_display_reconciliation.json) matches the expected rounding with zero integer differences and retains overlapping top/bottom captures. This is **rounded UI display evidence**, not a successful full-precision per-hour CSV download. The attempted CSV download timed out; no synthetic native CSV is substituted. Future actuals remain blank according to the canonical source and separate native import-integrity query.

## Access and licensing observations

The actual **Manage permissions** UI showed one direct-access result—the workspace owner—for both report and model. The report had no sharing links; the model stated that no related reports had been shared. No user, link or ACL was added. This establishes the inspected owner-only workspace UI state, subject to organizational administrator policies; it is not a blanket confidentiality guarantee. No public sharing was authorized or performed. The final [access receipt](../outputs/verification/privacy_access_check.json) records the observations without an email or personal cloud path.

During that inspection, the Service unexpectedly displayed an automatic free-trial notice mentioning 60 days; the subsequent header showed 59 days left. The notice was dismissed with Close. No Start trial, upgrade, billing or terms action was taken. Continued access after the trial ends has not been established, and no charge or expiry guarantee is made.

## Remaining boundaries

- All nine **Windows Desktop** acceptance items remain open. Service validation does not prove that the authored PBIP opens or refreshes in Windows.
- No PBIX download/export is claimed. The local PBIP/BIM/PBIR source and the saved Service report are distinct artifacts.
- Full-precision per-hour future-table CSV download was not completed; the 24-row rendered display check is labeled at its actual scope.
- No unauthenticated public report, repository or portfolio URL has been validated. Publishing or sharing remains a separate authorized action.
- This remains a historical forecasting prototype. No operational dispatch, reliability, outage, price, procurement-savings or emissions outcome was measured.

For separate Windows validation, follow [NATIVE_ACCEPTANCE.md](NATIVE_ACCEPTANCE.md). The official [Service model-editing documentation](https://learn.microsoft.com/en-us/power-bi/transform-model/service-edit-data-models) describes the supported editing surface; the actual receipts above, rather than a product capability description, establish what succeeded in this session.
