# GridCast — final career materials

## Resume entry

**GridCast | Energy Demand Forecasting & Power BI**  
Python · pandas · scikit-learn · Power BI Service · DAX · Power Query

- Built a reproducible Python pipeline for hourly PJM electricity-demand forecasting using official EIA-930 data; audited 61,368 hourly slots and preserved source provenance and missing-target exclusions.
- Achieved **4.38% WAPE** and **4,219 MW MAE** across **8,735 held-out 2025 hours**, reducing MAE **13.2%** versus a daily seasonal naïve baseline through chronological model selection.
- Developed a **four-page Power BI Service report with 28 DAX measures**; reconciled engine results against Python, verified refresh and model/date filters, and communicated uncertainty and high-demand forecast failures.

For a shorter resume, use the second and third bullets. This is a historical prototype. Windows PBIP/Desktop compatibility remains untested; the Service implementation is verified. No production deployment, savings or public interactive Power BI dashboard is claimed.

## LinkedIn post — final text, not posted

I built GridCast, an end-to-end project forecasting hourly electricity demand for the PJM regional grid using official EIA-930 data.

I audited seven years of hourly observations, documented missing and questionable readings, and evaluated daily and weekly baselines alongside Ridge and histogram gradient boosting models. Model selection, interval calibration and final testing used separate chronological periods.

On 8,735 valid test hours in 2025, the selected model achieved:
• 4.38% WAPE
• 4,219 MW MAE
• 13.2% lower MAE than yesterday’s same-hour baseline

I connected the analysis to a four-page Power BI Service report with 28 DAX measures, verified refresh and metric parity against Python, and tested model/date filters.

The most useful finding was a limitation: nominal 80% intervals covered 78.6% overall, but only 47.95% during high-demand hours. Ridge also had lower RMSE. Those tradeoffs matter when explaining what a model is suitable for.

This is a historical forecasting study and decision-support prototype, not a live operational forecasting system.

Code and case study: [Public links will be inserted after anonymous-access verification.]

#DataAnalytics #DataScience #PowerBI #Python #TimeSeries #Energy

## LinkedIn attachment

Use the actual Power BI [test scorecard](../outputs/verification/screenshots/06_service_test_page.jpg) as the primary image and the [high-demand diagnostics](../outputs/verification/screenshots/09_service_diagnostics_page.jpg) as the second image. Both are genuine Service screenshots. Keep the private app.powerbi.com link out of recruiter-facing materials.

## Interview preparation

Be prepared to explain the UTC/Eastern distinction, target exclusions versus causal feature filling, why random splits were avoided, the daily baseline, MAE versus RMSE tradeoffs, pointwise coverage, and why source revision/latency limits operational claims. Explain your own work and use of tools accurately.
