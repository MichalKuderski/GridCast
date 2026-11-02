# Read-only native DAX checks

These queries **have now been executed against the real Power BI Service model** after a completed manual refresh. Five standalone checks and the Service metadata queries have retained actual exports and provenance; see [Service validation](../SERVICE_VALIDATION.md) and [query provenance](../../outputs/verification/service_exports/query_provenance.json). Windows Desktop execution remains untested. The expected CSV/JSON files are still independent Python oracles, distinct from the actual Service results.

`00_define_persistent_measures.dax` is a separate **model-setup aid** containing all28 exact measure definitions from the current `model.bim`. Its definitions remain query-scoped unless explicitly committed through supported model editing; a row reporting28 prepared definitions alone does not prove persistence. In the completed Service session, a measure-only TMDL patch was applied, then01–05 were run without DEFINE. Actual native TMDL and metadata verify persistence/formats; `validation/measure_ui_metadata.json` remains a preparation reference, not native evidence.

For a repeat check after a successful real refresh, run each `.dax` file in the supported Service or Desktop DAX query view for that same semantic model. Run them standalone; report slicer state is intentionally replaced by the query's contexts. Retain raw, full-precision results as UTF-8 CSV. The completed Service session used **Copy Entire table**, preserving raw TSV before CSV quoting. Keep DAX BLANK empty and numeric zero as zero. Rounded visual values are insufficient for strict engine reconciliation.

| Query | Result | Compare with |
|---|---|---|
| `01_history_totals.dax` | One row of valid observed totals, counts and completeness. | `validation/export_reconciliation.json` |
| `02_test_models.dax` | One test-metric row for each of five models. | `validation/expected_test_metrics.csv` |
| `03_context_matrix.dax` | Twelve named contexts evaluating the **actual model measures**, including no/multiple/zero models, June, an empty date range, a missing-actual singleton, uncovered ordinary/high-demand interval singletons, future-only and validation-only dates. | `validation/expected_context_metrics.csv` and the filter definitions in `validation/context_cases.json` |
| `04_blank_zero_semantics.dax` | Primitive engine check: empty COUNTROWS is BLANK; normalized count is0; zero covered of one interval is0; missing/zero denominator stays BLANK. | `true, 0, 0, true, true` in column order |
| `05_import_integrity.dax` | One row of24 integer diagnostics: table/split counts, uniqueness, blank future actuals and key/time consistency. | `validation/expected_import_integrity.json`; actual comparison in `outputs/verification/service_exports/import_integrity_reconciliation.json` |

Once the actual exports exist, run from the repository root:

```bash
python powerbi/verify_native_results.py \
  --history /path/to/actual-history.csv \
  --models /path/to/actual-models.csv \
  --contexts /path/to/actual-contexts.csv \
  --primitives /path/to/actual-primitives.csv
```

The comparator accepts headers such as `[Case]` and `DimModel[Model]`, checks exact case/model keys, distinguishes BLANK from0, and uses tight numeric tolerances. It writes `validation/native_export_reconciliation.json` **only when all supplied values match**. The [actual Service comparison receipt](../validation/native_export_reconciliation.json) now passes all four supplied export groups. The separate [import receipt](../../outputs/verification/service_exports/import_integrity_reconciliation.json) passes all24 fields. File equality alone does not establish provenance; the retained native-copy records, model identity and refresh evidence establish the observed session.

Use `python powerbi/prepare_native_checks.py` after changed pipeline exports to regenerate the expected contexts and queries. The selected champion and missing/uncovered singleton timestamps come from the current frozen exports; the training demand threshold comes from `outputs/run_summary.json`.

The query suite establishes numerical behavior for its executed contexts. The separately documented Service refresh and report screenshots cover the observed browser workflow; they do not certify Windows project loading or exhaustive accessibility. `NATIVE_ACCEPTANCE.md` is the separate Windows Desktop gate.

## Executed Service metadata audit

`06_service_metadata.dax` contains four read-only result sets; `06a_service_measures.dax` through `06d_service_relationships.dax` contain the same sets separately. All four separate queries were executed in the Service, with actual raw/CSV exports and native-copy provenance retained. The [metadata reconciliation](../../outputs/verification/service_exports/metadata_reconciliation.json) records the pass and documented Service differences. They export no partition source, M expression, connection string or personal cloud path.

- Measures: all measures homed on `DimModel`, including expression, format, description and folder. Compare the exact28 names and definitions with `outputs/service-validation/expected_metadata.json`.
- Columns: the four canonical tables' user columns, with data type, sort-by column, key/uniqueness/nullability, format and summarization metadata. Internal RowNumber columns are excluded. INFO.VIEW's human-readable type labels can differ from canonical TOM enum names, so compare their meaning rather than raw spelling.
- Tables: all model tables' names/storage/category, including hidden auto-generated tables if present. The derived `IsDateTableByCategory` is `DataCategory = "Time"`; it is not an undocumented INFO field. A marked `DimDate` should have Time category, and its Date column should be the key with DateTime type.
- Relationships: all endpoints, cardinalities, active state and one-way filtering. The canonical scope has exactly three active fact-to-dimension relationships. Actual Service metadata also records five generated hidden date tables/template artifacts and four additional generated date edges; these are documented separately rather than mistaken for additional canonical joins. Descriptive/UUID relationship names need not match local authoring names.

Apply missing sort properties through the supported model UI: `DimDate[MonthName] → MonthNumber`, `DimDate[DayOfWeekName] → DayOfWeekNumber`, and `FactDemand[DayOfWeekNameLocal] → DayOfWeekNumberLocal`. Mark `DimDate` using its UTC `Date` column. Rerun the metadata query after changes.

The measure expression field requires write permission to be populated; the newly created model's owner has that permission. If a function or control is unavailable, retain the actual error instead of substituting a claimed metadata pass. Primary schemas: [MEASURES](https://learn.microsoft.com/en-us/dax/info-view-measures-function-dax), [COLUMNS](https://learn.microsoft.com/en-us/dax/info-view-columns-function-dax), [TABLES](https://learn.microsoft.com/en-us/dax/info-view-tables-function-dax), [RELATIONSHIPS](https://learn.microsoft.com/en-us/dax/info-view-relationships-function-dax).
