# GridCast in two minutes

GridCast forecasts hourly PJM regional electricity demand in daily 24-hour batches and explains the results through Power BI.

| Evidence | Result |
|---|---|
| Data | Official EIA-930; 61,368 UTC hourly slots, 2019–2025 |
| Evaluation | Select on 2023, calibrate on 2024, final test on 2025 |
| Test accuracy | 4.38% WAPE; 4,219 MW MAE on 8,735 valid test hours |
| Baseline improvement | 13.2% lower MAE than yesterday’s same-hour forecast |
| Power BI | Four pages, 35 visuals, 28 persistent DAX measures; Service refresh, metric parity and filters verified |
| Main limitation | Nominal 80% intervals covered 78.6% overall but 47.95% during high-demand hours; Ridge had lower RMSE |

Start with the [case study](../reports/CASE_STUDY.md), then inspect the [actual dashboard screenshots](../powerbi/SERVICE_VALIDATION.md#saved-report-and-observed-interactions), [executed notebook](../notebooks/GridCast_Analysis.ipynb), and [forecasting code](../src/gridcast/core.py).

The project demonstrates data auditing, temporal validation, seasonal baselines, feature engineering, calibrated uncertainty, dimensional modeling, DAX and business communication. This is a retrospective historical benchmark, not a live operational deployment. No outages prevented, savings, price prediction or grid-reliability improvement was measured. Windows Desktop/PBIP compatibility is untested; the separately reconstructed Power BI Service report is the validated implementation.
