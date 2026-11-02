# Independent robustness review · 31 October 2026

The frozen source, selected specification, saved champion, original forecasts, and original metric files were retained. This review adds diagnostic evidence after the 2025 results were examined; it is not a fresh holdout evaluation or a replacement experiment.

## Findings by practical severity

| Severity | Finding | Evidence and implication |
| --- | --- | --- |
| Material limitation | Uncertainty is weak during high demand | The nominal 80% pointwise bands cover **47.95% of 1,487 high-demand test hours**, using the initial-training p90 threshold of 111,972.4 MW. Aggregate coverage of 78.58% does not establish reliable coverage in stressed hours. Report this beside the −6,592.89 MW high-demand bias. |
| Material deployment gap | Immediate previous-hour availability differs from the public EIA release schedule | An explicit one-hour-after-end release stress with fixed model weights raises aggregate MAE from 4,219.45 to **4,232.57 MW**. The affected position is horizon 24: MAE rises from 4,522.07 to **4,837.00 MW**. This is a carry-forward input stress, not archived publication data or operational validation. |
| Moderate coverage limitation | Test truth is missing in a concentrated block | All **25** excluded 2025 actuals occur consecutively from 2 November 04:00 UTC to 3 November 04:00 UTC, coinciding with the Eastern fall daylight-saving date. These are missing originals, not confirmed demand values. Accuracy is established for 8,735 observed valid hours, not all 8,760 intervals. |
| Small observed sensitivity | Manual training exclusions do not drive the headline result in this diagnostic | Retaining all four manually adjudicated 2020 spikes and refitting the same selected specification through 2023 gives **4,226.23 MW MAE**, a **6.78 MW / 0.16%** increase on the unchanged 8,735 valid test actuals. This supports a limited sensitivity statement; it does not confirm that the spikes were measurement errors. |
| Passed within scope | Saved artifact and source lineage reconcile | The saved champion reproduces exported test predictions within **0.0000005 MW**, consistent with CSV rounding. Canonical source CSV, extraction audit, and source manifest hashes agree. The present original workbook's independently recomputed SHA256 matches its pinned manifest. The audit records source, model, and relevant code hashes. |

January's observed pointwise coverage is 62.63%, the lowest month. All 24 pointwise intervals cover the entire daily path on 42.98% of 363 complete UTC test days. The latter is descriptive: pointwise 80% intervals do not target simultaneous 80% daily-path coverage.

## Source-estimate stress

EIA provides imputed estimates for 24 of the 25 missing 2025 originals; one interval remains without a provider estimate. Combining these 24 estimates with the valid originals yields 4,213.70 MW MAE on 8,759 pairs. **This is estimated truth**, so the result is a labeled denominator/quality sensitivity rather than observed accuracy and must not replace the published 8,735-hour result.

The revised source and its quality flags remain retrospective. This review does not recover the vintages, flag discovery times, variable publication latency, or data revisions that a real-time forecaster would have experienced.

## Tests and reproduction

Run from the repository root with the pinned environment:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/audit_robustness.py
```

All **22 tests passed** in this review. Five new tests inject wrong regions, incorrect interval ends, duplicate timestamps, and altered future source values/quality flags; they also test a reporting-delay cutoff across the fall daylight-saving date. Existing tests independently reconcile all candidate/split metric rows, horizon calibration ranks, target/feature separation, facts, dimensions, and forecast-time feature availability.

The executable audit writes `outputs/verification/robustness.json`. It refits only a diagnostic copy of the already selected specification for the manual-exclusion sensitivity. It neither reselects a model nor overwrites the saved champion, frozen experiment, prediction exports, or release metrics. The latency stress carries forward the latest available historical input for the unavailable recent hour, keeps target-day actuals unknown, and does not recalibrate interval bounds. Different latency/imputation policies require their own evaluation.

## Supported publication wording

The evidence supports a reproducible cleaned historical forecasting benchmark with measured improvement under its stated MAE objective. It does not support calling the model robust to high-demand uncertainty, operationally validated, or tested on every 2025 hour. Describe the model-selection rule as fixed in code before scoring; there is no claim of external preregistration. Retain the lower-RMSE Ridge tradeoff and all native Power BI acceptance gaps in the release materials.
