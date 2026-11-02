# Data sources and provenance

## Scope decision

The first release covers **PJM regional grid demand**, hourly observations, a daily 24-hour forecasting task, and a Power BI implementation. AEP, COMED, and other individual zones are not substituted for the full region.

## Selected first-party data

The input is the **U.S. Energy Information Administration (EIA), Form EIA-930 Hourly Electric Grid Monitor**, balancing-authority code **PJM**. This is PJM regional balancing-authority demand as reported to EIA, not a single utility zone and not total US consumption. EIA offers the complete history as a downloadable BA workbook without an API key.

- Official dataset documentation: <https://www.eia.gov/electricity/930-content/about.html>
- Public dashboard: <https://www.eia.gov/electricity/gridmonitor/dashboard/electric_overview/US48/US48>
- Direct original workbook: <https://www.eia.gov/electricity/gridmonitor/knownissues/xls/PJM.xlsx>
- EIA reuse policy: <https://www.eia.gov/about/copyrights_reuse.php>
- PJM's own data directory, useful for distinguishing preliminary, estimated, and metered products: <https://www.pjm.com/markets-and-operations/data-dictionary.aspx/>

EIA demand is based on metered net generation less net interchange within a balancing authority's system. It represents a physical operating measure; its definition and vintage can differ from PJM's market-settled or planning load products. Do not assert exact equivalence to PJM Historical Metered Load without reconciliation. The project should be described as **PJM demand forecasting using official EIA-930 data**.

The old PJM historical-load `.aspx` page currently returns not found. PJM's [System Information page](https://www.pjm.com/markets-and-operations/etools/oasis/system-information) now directs historical load users to Data Miner. The available EIA BA workbook provides a credible reproducible acquisition route for this release.

## Files and reproducibility

The downloaded workbook is unchanged at `data/raw/eia_pjm_full_history.xlsx` (114,347,009 bytes in this snapshot). Its retrieval timestamp and SHA-256 are recorded in `data/raw/eia_pjm_manifest.json`. This large source file must be excluded from Git because it exceeds GitHub's regular 100 MB file limit. Keep the extracted snapshot and the fetch recipe.

Run:

```sh
python scripts/fetch_eia_pjm.py
```

The standard-library script reuses the downloaded workbook, verifies its manifest checksum, extracts the documented source columns, and adds a checksum for the output CSV. `--refresh` downloads a newer source vintage intentionally; because historical records can be revised, results may then change. The script does not require an EIA API key. It uses `scripts/extract_eia_pjm.py` as a helper. Keep both files.

The selected CSV, `data/raw/eia_pjm_hourly_2019_2025.csv`, contains 61,368 continuous, unique hourly intervals from 2019-01-01 00:00 UTC through 2025-12-31 23:00 UTC. Calendar years 2020 and 2024 have 8,784 hours; all other selected years have 8,760. No partial 2026 observations are included. This period restriction uses **UTC interval starts**, which must be stated beside annual summaries.

The input workbook's `Notes` sheet was also extracted to `data/raw/eia_pjm_workbook_notes.json`, and a raw structural audit is saved as `data/raw/eia_pjm_initial_audit.json`.

## Column mapping and units

| Canonical CSV field | Source workbook column | Meaning |
|---|---|---|
| `BalancingAuthority` | BA | Always PJM in this extract |
| `DateTimeUTC` | UTC time minus one hour | UTC interval start, canonical join key |
| `IntervalEndUTC` | UTC time | Original hour-ending instant |
| `OriginalDemandMWh` | Demand | Original reported hourly demand |
| `DemandForecastMWh` | Demand forecast | Published BA day-ahead demand forecast; retained for provenance only |
| `ImputedDemandMWh` | Imputed demand | EIA replacement value, when supplied |
| `AdjustedDemandMWh` | Adjusted demand | EIA reported demand with its replacements applied |
| `SourceLocalDate`, `SourceHour`, `SourceLocalTime`, `SourceTimeZone` | Local date, Hour, Local time, Time zone | Original local reporting fields, retained for inspection |

The workbook's notes define hourly demand in **MWh for the interval**. Since each interval is exactly one hour, its numerical value is also the interval's **average MW**. This project can model/report average MW, but daily energy is the sum of interval MWh and must be labeled MWh. Do not call a time sum of hourly power an instantaneous MW value.

The workbook uses **hour ending** timestamps. Thus source UTC time 2025-01-01 01:00 describes the interval starting at 00:00; the extractor subtracts one hour. Excel serial timestamps are converted using the workbook's 1899-12-30 epoch and rounded to seconds before conversion. Local reporting/calendar features should be derived from the UTC interval start in `America/New_York`. UTC prevents duplicate keys during the autumn repeated local hour. EIA documents 23/25-hour local days at daylight saving transitions.

## Quality findings and adjudication

Structural completeness is not measurement completeness. In this exact frozen extract:

- 167 original demand observations are blank.
- 7 additional original values differ from EIA's adjusted demand; each has an explicit EIA imputation. Three values on 2021-10-19 are hundreds of millions or billions of MWh and plainly unusable.
- EIA supplies 171 imputed values total. Three blank original observations have no imputation: 2023-11-06 04:00 UTC, 2024-11-04 04:00 UTC, and 2025-11-03 04:00 UTC.
- Four further 2020 training-period spikes remain unchanged even in EIA's adjusted column. Their values and immediate neighbors are preserved in `docs/anomaly_review.csv`.

Exclude the missing originals and EIA-flagged values from scored ground truth. The four manually reviewed 2020 observations can also be excluded from target fitting, with the judgment labeled **analyst inference, not an operator-confirmed correction**. The list is fixed to these training observations; it is not a universal ceiling that would erase future peaks. Original raw values remain available for inspection.

The manual review is supported by the sharp isolated upward reversals and independent scale context: [PJM's May 2026 outlook](https://www.pjm.com/-/media/DotCom/about-pjm/newsroom/2026-releases/20260507-summer-outlook-202-pjm-prepared-to-meet-growing-summer-demand-with-adequate-resources.pdf) reports the pre-2026 summer record as 165,563 MW and the June 2025 peaks near 161 GW. The four suspect 2020 values are 176,085–224,345. The source definitions differ, so the PJM record is a corroborating plausibility check, not an exact correction formula. Real 2025 peak observations near 160,560 average MW are retained.

Together these rules flag 178 target observations across 2019–2025 (174 source-missing/flagged plus four reviewed training spikes). Feature history may require past-only replacement, but a replacement must never become scored actual demand. Keep flags, observed values, and modeling inputs distinct.

## Information available at a forecast origin

EIA's public documentation says demand is typically released about one hour after an operating hour ends. A forecast that assumes immediate access to the last completed hour needs an operational feed beyond that public release schedule. Configure the issue time and lag availability explicitly; this project is a retrospective historical-vintage study, not a proof of real-time deployment.

The published EIA demand forecast is retained only for provenance. It must not be used as a feature or secondary benchmark unless its issue time and revision history are aligned to the project's origin. Realized future weather, future generation, future interchange, and future demand are also unavailable at the origin. A demand-and-calendar first release avoids pretending those covariates are known.

## Reuse and publication

EIA's reuse page permits use/distribution of its public-domain government information and asks for acknowledgment including a date. Use an attribution such as **Source: U.S. Energy Information Administration, Form EIA-930 PJM workbook, retrieved 2026-10-27**. Link the source documentation and retain the checksum manifest. Do not reuse EIA or PJM logos or imply either organization endorses this independent project. The repository's code licence is separate from the source data terms.

## Follow-up audit · 31 October 2026

All 25 missing 2025 actuals form a contiguous gap from 2025-11-02 04:00 UTC through 2025-11-03 04:00 UTC, around the Eastern autumn clock change. The 8,735-hour observed test result does not validate the missing transition. Provider estimates for 24 of those hours were examined only as an explicitly labeled sensitivity; they remain excluded from scored ground truth. Source files and their retrieval vintage are unchanged.
