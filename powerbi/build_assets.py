"""Generate the reviewable Power BI source project. No Power BI execution is implied.

Run from any directory: python powerbi/build_assets.py
The generated report must still be opened, refreshed, and visually checked in Desktop.
"""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/"
RUN_SUMMARY = HERE.parent / "outputs/run_summary.json"
if not RUN_SUMMARY.exists():
    raise FileNotFoundError("Run the forecasting pipeline before generating Power BI assets: outputs/run_summary.json is required.")
RUN = json.loads(RUN_SUMMARY.read_text())
HIGH_DEMAND_THRESHOLD = float(RUN["training_p90_MW"])


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


M = {
    "DataFolder": '"C:\\GridCast\\data\\powerbi" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
    "ReadCsv": '''(filename as text) as table =>
let
    Source = Csv.Document(File.Contents(DataFolder & "/" & filename),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Nulls = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers))
in
    Nulls''',
    "FactDemand": '''let
    Source = ReadCsv("FactDemand.csv"),
    Typed = Table.TransformColumnTypes(Source,
        {{"Date", type date}, {"HourUTC", Int64.Type}, {"DateLocal", type date}, {"HourLocal", Int64.Type}, {"ActualMW", type number}}, "en-US"),
    UTC = Table.TransformColumns(Typed, {{"DateTimeUTC", each DateTimeZone.RemoveZone(DateTimeZone.SwitchZone(DateTimeZone.FromText(_), 0)), type datetime}}),
    Selected = Table.SelectColumns(UTC, {"DateTimeUTC", "Date", "HourUTC", "DateLocal", "HourLocal", "ActualMW"}),
    WeekdayNumber = Table.AddColumn(Selected, "DayOfWeekNumberLocal", each Date.DayOfWeek([DateLocal], Day.Monday) + 1, Int64.Type),
    WeekdayName = Table.AddColumn(WeekdayNumber, "DayOfWeekNameLocal", each Date.DayOfWeekName([DateLocal], "en-US"), type text)
in
    WeekdayName''',
    "FactForecast": '''let
    Source = ReadCsv("FactForecast.csv"),
    Typed = Table.TransformColumnTypes(Source,
        {{"Date", type date}, {"HourUTC", Int64.Type}, {"Model", type text}, {"Split", type text},
         {"HorizonHours", Int64.Type}, {"ActualMW", type number}, {"ForecastMW", type number},
         {"Lower80MW", type number}, {"Upper80MW", type number}}, "en-US"),
    UTC = Table.TransformColumns(Typed, {
        {"DateTimeUTC", each DateTimeZone.RemoveZone(DateTimeZone.SwitchZone(DateTimeZone.FromText(_), 0)), type datetime},
        {"ForecastOriginUTC", each DateTimeZone.RemoveZone(DateTimeZone.SwitchZone(DateTimeZone.FromText(_), 0)), type datetime}}),
    Selected = Table.SelectColumns(UTC, {"DateTimeUTC", "Date", "HourUTC", "Model", "Split", "ForecastOriginUTC", "HorizonHours", "ActualMW", "ForecastMW", "Lower80MW", "Upper80MW"})
in
    Selected''',
    "DimDate": '''let
    Source = ReadCsv("DimDate.csv"),
    Typed = Table.TransformColumnTypes(Source, {
        {"Date", type date}, {"Year", Int64.Type}, {"MonthNumber", Int64.Type},
        {"MonthName", type text}, {"YearMonth", type text},
        {"DayOfWeekNumber", Int64.Type}, {"DayOfWeekName", type text}, {"IsWeekend", type logical}}, "en-US")
in
    Typed''',
    "DimModel": '''let
    Source = ReadCsv("DimModel.csv"),
    Typed = Table.TransformColumnTypes(Source, {{"Model", type text}}, "en-US"),
    Selected = Table.SelectColumns(Typed, {"Model"})
in
    Selected''',
}

PAIR = 'FILTER(FactForecast, FactForecast[Split] = "test" && NOT ISBLANK(FactForecast[ActualMW]) && NOT ISBLANK(FactForecast[ForecastMW]))'
INTERVAL = 'FILTER(FactForecast, FactForecast[Split] = "test" && NOT ISBLANK(FactForecast[ActualMW]) && NOT ISBLANK(FactForecast[ForecastMW]) && NOT ISBLANK(FactForecast[Lower80MW]) && NOT ISBLANK(FactForecast[Upper80MW]))'
HIGH = f'FILTER({PAIR}, FactForecast[ActualMW] >= [Training High Demand Threshold MW])'
HIGH_INTERVAL = f'FILTER({INTERVAL}, FactForecast[ActualMW] >= [Training High Demand Threshold MW])'


def guarded(expr):
    return 'IF(HASONEVALUE(DimModel[Model]), ' + expr + ')'


MEASURES = [
    ("Demand MWh", "SUM(FactDemand[ActualMW])", "#,0", "History", "Sum of hourly mean MW multiplied by each one-hour interval."),
    ("Mean Demand MW", "AVERAGE(FactDemand[ActualMW])", "#,0", "History", "Mean hourly PJM balancing authority demand over the selected UTC dates."),
    ("Peak Demand MW", "MAX(FactDemand[ActualMW])", "#,0", "History", "Maximum observed hourly mean demand; not an instantaneous peak."),
    ("Observed Hours", "COALESCE(COUNT(FactDemand[ActualMW]), 0)", "#,0", "History", "Number of nonblank one-hour observations; zero when no observations exist. Missing demand is not counted as zero."),
    ("Expected Hours", "COALESCE(COUNTROWS(FactDemand), 0)", "#,0", "History", "Number of expected one-hour slots on the complete UTC grid; zero for an empty date selection."),
    ("Missing Hours", "[Expected Hours] - [Observed Hours]", "#,0", "History", "Expected hourly slots without a valid observed actual."),
    ("Observation Completeness", "DIVIDE([Observed Hours], [Expected Hours])", "0.00%", "History", "Observed valid hours divided by expected hourly slots."),
    ("Model Selection", 'IF(HASONEVALUE(DimModel[Model]), SELECTEDVALUE(DimModel[Model]), "Select one model to view forecast KPIs")', None, "Controls", "Model safeguard for cards and lines; comparison tables supply row context."),
    ("Test Hours", guarded(f"COALESCE(COUNTROWS({PAIR}), 0)"), "#,0", "Test", "Scored 2025 hourly pairs for exactly one model; zero for an empty scored subset."),
    ("Test Actual MWh", guarded(f"SUMX({PAIR}, FactForecast[ActualMW])"), "#,0", "Test", "Actual one-hour energy on scored test pairs; excludes future rows."),
    ("Test Forecast MWh", guarded(f"SUMX({PAIR}, FactForecast[ForecastMW])"), "#,0", "Test", "Forecast one-hour energy on the same scored test pairs."),
    ("Test Actual MW", guarded(f"AVERAGEX({PAIR}, FactForecast[ActualMW])"), "#,0", "Test", "Mean actual hourly demand MW, at the current axis grain, on scored test pairs."),
    ("Test Forecast MW", guarded(f"AVERAGEX({PAIR}, FactForecast[ForecastMW])"), "#,0", "Test", "Mean forecast MW, at the current axis grain, on scored test pairs."),
    ("Test MAE MW", guarded(f"AVERAGEX({PAIR}, ABS(FactForecast[ForecastMW] - FactForecast[ActualMW]))"), "#,0.0", "Test", "Mean absolute hourly error; lower is better."),
    ("Test RMSE MW", guarded(f"SQRT(AVERAGEX({PAIR}, POWER(FactForecast[ForecastMW] - FactForecast[ActualMW], 2)))"), "#,0.0", "Test", "Root mean squared hourly error, emphasizing large errors."),
    ("Test WAPE", guarded(f"DIVIDE(SUMX({PAIR}, ABS(FactForecast[ForecastMW] - FactForecast[ActualMW])), SUMX({PAIR}, ABS(FactForecast[ActualMW])))"), "0.00%", "Test", "Ratio of aggregate absolute error to aggregate absolute actual demand. Never average daily WAPE."),
    ("Test Bias MW", guarded(f"AVERAGEX({PAIR}, FactForecast[ForecastMW] - FactForecast[ActualMW])"), "+#,0.0;-#,0.0;0.0", "Test", "Forecast minus actual; positive means overforecasting."),
    ("Test Interval Hours", guarded(f"COALESCE(COUNTROWS({INTERVAL}), 0)"), "#,0", "Intervals", "Number of scored test observations with both interval bounds; zero when none exist."),
    ("Test Coverage 80", guarded(f"DIVIDE(COALESCE(COUNTROWS(FILTER({INTERVAL}, FactForecast[ActualMW] >= FactForecast[Lower80MW] && FactForecast[ActualMW] <= FactForecast[Upper80MW])), 0), COUNTROWS({INTERVAL}))"), "0.0%", "Intervals", "Observed empirical coverage of nominal 80% hourly prediction intervals. Zero when no actual is covered, blank when no interval pairs exist."),
    ("Test Mean Interval Width MW", guarded(f"AVERAGEX({INTERVAL}, FactForecast[Upper80MW] - FactForecast[Lower80MW])"), "#,0", "Intervals", "Mean width on test rows with interval bounds."),
    ("Training High Demand Threshold MW", str(HIGH_DEMAND_THRESHOLD), "#,0.0", "Diagnostics", "Fixed 90th percentile of valid initial training demand (2019–2022, after 336-hour warmup). Generated from outputs/run_summary.json; never derived from test demand."),
    ("Test High Demand Hours", guarded(f"COALESCE(COUNTROWS({HIGH}), 0)"), "#,0", "Diagnostics", "Scored test hours whose observed demand is at least the fixed training p90; zero for an empty subset. Retrospective diagnostic, not an advance alert."),
    ("Test High Demand MAE MW", guarded(f"AVERAGEX({HIGH}, ABS(FactForecast[ForecastMW] - FactForecast[ActualMW]))"), "#,0.0", "Diagnostics", "Mean absolute error during test hours above the fixed initial-training p90 actual-demand threshold."),
    ("Test High Demand Bias MW", guarded(f"AVERAGEX({HIGH}, FactForecast[ForecastMW] - FactForecast[ActualMW])"), "+#,0.0;-#,0.0;0.0", "Diagnostics", "Forecast minus actual bias during high observed demand test hours. Negative indicates underforecasting."),
    ("Test High Demand Coverage 80", guarded(f"DIVIDE(COALESCE(COUNTROWS(FILTER({HIGH_INTERVAL}, FactForecast[ActualMW] >= FactForecast[Lower80MW] && FactForecast[ActualMW] <= FactForecast[Upper80MW])), 0), COUNTROWS({HIGH_INTERVAL}))"), "0.0%", "Diagnostics", "Empirical coverage of nominal80% pointwise intervals during high observed-demand test hours. Requires valid actual, forecast and both bounds; blank when no valid high-demand intervals exist."),
    ("Future Forecast MW", guarded('CALCULATE(AVERAGE(FactForecast[ForecastMW]), KEEPFILTERS(FactForecast[Split] = "future"))'), "#,0", "Future", "Historical next-day forecast from the end of the frozen 2025 source; not today's live forecast."),
    ("Future Lower 80 MW", guarded('CALCULATE(AVERAGE(FactForecast[Lower80MW]), KEEPFILTERS(FactForecast[Split] = "future"))'), "#,0", "Future", "Pointwise lower 80% bound; displayed at hourly grain only."),
    ("Future Upper 80 MW", guarded('CALCULATE(AVERAGE(FactForecast[Upper80MW]), KEEPFILTERS(FactForecast[Split] = "future"))'), "#,0", "Future", "Pointwise upper 80% bound; displayed at hourly grain only."),
]


TABLES = {
    "FactDemand": [("DateTimeUTC", "dateTime"), ("Date", "dateTime"), ("HourUTC", "int64"), ("DateLocal", "dateTime"), ("HourLocal", "int64"), ("DayOfWeekNumberLocal", "int64"), ("DayOfWeekNameLocal", "string"), ("ActualMW", "double")],
    "FactForecast": [("DateTimeUTC", "dateTime"), ("Date", "dateTime"), ("HourUTC", "int64"), ("Model", "string"), ("Split", "string"), ("ForecastOriginUTC", "dateTime"), ("HorizonHours", "int64"), ("ActualMW", "double"), ("ForecastMW", "double"), ("Lower80MW", "double"), ("Upper80MW", "double")],
    "DimDate": [("Date", "dateTime"), ("Year", "int64"), ("MonthNumber", "int64"), ("MonthName", "string"), ("YearMonth", "string"), ("DayOfWeekNumber", "int64"), ("DayOfWeekName", "string"), ("IsWeekend", "boolean")],
    "DimModel": [("Model", "string")],
}


def column(name, dtype):
    result = {"name": name, "dataType": dtype, "sourceColumn": name, "summarizeBy": "none"}
    if dtype == "dateTime":
        result["formatString"] = "yyyy-mm-dd" if name in ["Date", "DateLocal"] else "yyyy-mm-dd HH:mm"
    if name == "MonthName":
        result["sortByColumn"] = "MonthNumber"
    if name == "DayOfWeekName":
        result["sortByColumn"] = "DayOfWeekNumber"
    if name == "DayOfWeekNameLocal":
        result["sortByColumn"] = "DayOfWeekNumberLocal"
    return result


def model():
    tables = []
    for name, cols in TABLES.items():
        table = {"name": name, "columns": [column(*c) for c in cols], "partitions": [{"name": name, "mode": "import", "source": {"type": "m", "expression": M[name].splitlines()}}]}
        if name == "DimDate":
            table["dataCategory"] = "Time"
            table["columns"][0]["isKey"] = True
        if name == "DimModel":
            table["columns"][0]["isKey"] = True
            table["measures"] = [{"name": n, "expression": e, "displayFolder": f, "description": d, **({"formatString": fmt} if fmt else {})} for n, e, fmt, f, d in MEASURES]
        tables.append(table)
    relationships = []
    for fact in ["FactDemand", "FactForecast"]:
        relationships.append({"name": f"{fact}_Date", "fromTable": fact, "fromColumn": "Date", "toTable": "DimDate", "toColumn": "Date", "fromCardinality": "many", "toCardinality": "one", "isActive": True, "crossFilteringBehavior": "oneDirection"})
    relationships.append({"name": "FactForecast_Model", "fromTable": "FactForecast", "fromColumn": "Model", "toTable": "DimModel", "toColumn": "Model", "fromCardinality": "many", "toCardinality": "one", "isActive": True, "crossFilteringBehavior": "oneDirection"})
    return {"name": "GridCast", "compatibilityLevel": 1567, "model": {"culture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3", "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True}, "annotations": [{"name": "PBI_QueryOrder", "value": json.dumps(list(M))}, {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"}], "expressions": [{"name": n, "kind": "m", "expression": M[n].splitlines()} for n in ["DataFolder", "ReadCsv"]], "tables": tables, "relationships": relationships}}


def field(table, name, measure=False):
    return {"Measure" if measure else "Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def projection(table, name, measure=False):
    return {"field": field(table, name, measure), "queryRef": table + "." + name, "nativeQueryRef": name}


def literal(value):
    if isinstance(value, bool):
        value = "true" if value else "false"
    else:
        value = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": value}}}


def visual(name, kind, title, x, y, w, h, roles=None, objects=None):
    v = {"$schema": SCHEMA + "item/report/definition/visualContainer/2.4.0/schema.json", "name": name, "position": {"x": x, "y": y, "width": w, "height": h, "z": y + x, "tabOrder": y * 10000 + x}, "visual": {"visualType": kind, "visualContainerObjects": {"title": [{"properties": {"show": literal(True), "text": literal(title)}}], "general": [{"properties": {"altText": literal("Nominal 80% interval coverage" if name == "CoverageCard" else title)}}]}}}
    if roles:
        v["visual"]["query"] = {"queryState": {k: {"projections": values} for k, values in roles.items()}}
        # Visual defaults can sort by measure rather than chronology. Pin the
        # category/time order in the actual PBIR query, not just the runbook.
        category = roles.get("Category")
        if category:
            v["visual"]["query"]["sortDefinition"] = {"sort": [{"field": category[0]["field"], "direction": "Ascending"}], "isDefaultSort": False}
        elif kind == "tableEx" and roles.get("Values"):
            first = roles["Values"][0]["field"]
            if "Column" in first:
                v["visual"]["query"]["sortDefinition"] = {"sort": [{"field": first, "direction": "Ascending"}], "isDefaultSort": False}
    if objects:
        v["visual"]["objects"] = objects
    return v


def text(name, title, body, x, y, w, h, size=12):
    return visual(name, "textbox", title, x, y, w, h, objects={"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": body, "textStyle": {"fontFamily": "Segoe UI", "fontSize": f"{size}pt"}}]}]}}]})


def build_report():
    root = HERE / "GridCast.Report"
    write_json(root / "definition.pbir", {"$schema": SCHEMA + "item/report/definitionProperties/2.0.0/schema.json", "version": "4.0", "datasetReference": {"byPath": {"path": "../GridCast.SemanticModel"}}})
    write_json(root / "definition/version.json", {"$schema": SCHEMA + "item/report/definition/versionMetadata/1.0.0/schema.json", "version": "4.0.0"})
    write_json(root / "definition/report.json", {"$schema": SCHEMA + "item/report/definition/report/3.1.0/schema.json", "themeCollection": {}, "annotations": [{"name": "GridCast.Validation", "value": "Authored source. Native refresh/render and measure reconciliation remain required."}]})
    write_json(root / "definition/pages/pages.json", {"$schema": SCHEMA + "item/report/definition/pagesMetadata/1.0.0/schema.json", "pageOrder": ["DemandHistory", "TestScorecard", "Diagnostics", "HistoricalNextDay"], "activePageName": "DemandHistory"})
    P = projection
    measure = lambda n: P("DimModel", n, True)
    model_slicer = lambda n: visual(n, "slicer", "Select one model", 30, 95, 300, 75, {"Values": [P("DimModel", "Model")]}, {"selection": [{"properties": {"singleSelect": literal(True)}}]})
    pages = {
        "DemandHistory": ("01 | Demand history", [
            text("HistoryTitle", "GridCast | PJM electricity demand", "EIA-930 PJM balancing authority demand. UTC dates; local pattern charts use America/New_York.", 30, 15, 1220, 70, 14),
            visual("DateSlicer", "slicer", "UTC date range", 30, 95, 520, 70, {"Values": [P("DimDate", "Date")]}),
            visual("CompletenessCard", "card", "Observation completeness", 625, 95, 285, 75, {"Values": [measure("Observation Completeness")]}),
            visual("MissingCard", "card", "Missing actual hours", 945, 95, 285, 75, {"Values": [measure("Missing Hours")]}),
            visual("EnergyCard", "card", "Observed energy proxy | MWh", 30, 180, 380, 105, {"Values": [measure("Demand MWh")]}),
            visual("MeanCard", "card", "Mean demand | MW", 440, 180, 380, 105, {"Values": [measure("Mean Demand MW")]}),
            visual("PeakCard", "card", "Maximum hourly mean | MW", 850, 180, 380, 105, {"Values": [measure("Peak Demand MW")]}),
            visual("DemandTrend", "lineChart", "Daily mean PJM demand | MW", 30, 305, 1200, 285, {"Category": [P("DimDate", "Date")], "Y": [measure("Mean Demand MW")]}),
            visual("WeekdayDemand", "clusteredColumnChart", "Mean demand by local weekday | MW", 30, 610, 570, 245, {"Category": [P("FactDemand", "DayOfWeekNameLocal")], "Y": [measure("Mean Demand MW")]}),
            visual("HourlyDemand", "lineChart", "Mean demand by local hour | MW", 630, 610, 600, 245, {"Category": [P("FactDemand", "HourLocal")], "Y": [measure("Mean Demand MW")]}),
        ]),
        "TestScorecard": ("02 | Untouched 2025 test", [
            text("TestTitle", "GridCast | Forecast validation", "All accuracy measures below use the untouched 2025 test set. Select one model for cards and the trend; compare models in the table.", 30, 15, 1220, 70, 13),
            model_slicer("TestModelSlicer"),
            visual("TestDateSlicer", "slicer", "UTC date range (intersected with 2025)", 360, 95, 530, 75, {"Values": [P("DimDate", "Date")]}),
            visual("MAECard", "card", "Hourly MAE | MW", 30, 185, 280, 100, {"Values": [measure("Test MAE MW")]}),
            visual("WAPECard", "card", "Test WAPE", 340, 185, 280, 100, {"Values": [measure("Test WAPE")]}),
            visual("BiasCard", "card", "Bias | forecast − actual MW", 650, 185, 280, 100, {"Values": [measure("Test Bias MW")]}),
            visual("CoverageCard", "card", "80% interval coverage", 960, 185, 270, 100, {"Values": [measure("Test Coverage 80")]}),
            visual("ForecastTrend", "lineChart", "Daily mean actual and forecast | MW (2025 only)", 30, 305, 1200, 280, {"Category": [P("DimDate", "Date")], "Y": [measure("Test Actual MW"), measure("Test Forecast MW")]}),
            visual("ModelComparison", "tableEx", "Model comparison | same scored test pairs", 30, 610, 1200, 245, {"Values": [P("DimModel", "Model"), measure("Test Hours"), measure("Test MAE MW"), measure("Test RMSE MW"), measure("Test WAPE"), measure("Test Bias MW"), measure("Test Coverage 80")]}),
        ]),
        "Diagnostics": ("03 | Error and peak-risk diagnostics", [
            text("DiagnosticsTitle", "GridCast | Error and high-demand risk", "Test diagnostics expose seasonal weaknesses and underforecasting during high observed demand. Select a model; date filters remain UTC.", 30, 15, 1220, 70, 13),
            model_slicer("DiagnosticModelSlicer"),
            visual("DiagnosticDateSlicer", "slicer", "UTC date range (intersected with 2025)", 360, 95, 530, 75, {"Values": [P("DimDate", "Date")]}),
            visual("TrainingThresholdCard", "card", "Fixed training p90 threshold | MW", 30, 185, 280, 100, {"Values": [measure("Training High Demand Threshold MW")]}),
            visual("HighHoursCard", "card", "High observed-demand test hours", 340, 185, 280, 100, {"Values": [measure("Test High Demand Hours")]}),
            visual("HighMAECard", "card", "High-demand MAE | MW", 650, 185, 280, 100, {"Values": [measure("Test High Demand MAE MW")]}),
            visual("HighBiasCard", "card", "High-demand bias | MW", 960, 185, 270, 100, {"Values": [measure("Test High Demand Bias MW")]}),
            visual("MonthlyMAE", "clusteredColumnChart", "Hourly MAE by UTC month | MW", 30, 305, 1200, 235, {"Category": [P("DimDate", "YearMonth")], "Y": [measure("Test MAE MW")]}),
            visual("HourBias", "clusteredColumnChart", "Mean forecast − actual bias by UTC hour | MW", 30, 565, 1200, 235, {"Category": [P("FactForecast", "HourUTC")], "Y": [measure("Test Bias MW")]}),
            visual("HighCoverageCard", "card", "High-demand 80% coverage", 30, 820, 300, 65, {"Values": [measure("Test High Demand Coverage 80")]}),
            text("HighRiskNote", "Diagnostic definition", "High-demand subset: actual test demand ≥ the fixed 90th percentile of initial 2019–2022 training demand after feature warmup. This uses observed test demand for retrospective diagnosis, not an advance alert rule.", 360, 820, 870, 65, 11),
        ]),
        "HistoricalNextDay": ("04 | Historical next day", [
            text("FutureTitle", "GridCast | Historical next-day forecast", "A 24-hour forecast after the frozen historical source cutoff. This is a historical demonstration, not a live forecast for today.", 30, 15, 1220, 80, 13),
            model_slicer("FutureModelSlicer"),
            text("IntervalNote", "Interpret the uncertainty", "Only the selected champion has prediction intervals. Bounds are pointwise hourly 80% intervals; they do not give an 80% simultaneous guarantee for the entire day.", 365, 100, 865, 80),
            visual("FutureTrend", "lineChart", "Hourly forecast and pointwise 80% bounds | MW, UTC", 30, 205, 1200, 330, {"Category": [P("FactForecast", "DateTimeUTC")], "Y": [measure("Future Forecast MW"), measure("Future Lower 80 MW"), measure("Future Upper 80 MW")]}),
            visual("FutureTable", "tableEx", "Forecast review | UTC hour", 30, 560, 1200, 285, {"Values": [P("FactForecast", "DateTimeUTC"), measure("Future Forecast MW"), measure("Future Lower 80 MW"), measure("Future Upper 80 MW")]}),
        ]),
    }
    for name, (title, visuals) in pages.items():
        folder = root / "definition/pages" / name
        page = {"$schema": SCHEMA + "item/report/definition/page/2.0.0/schema.json", "name": name, "displayName": title, "displayOption": "FitToPage", "height": 900, "width": 1280}
        if name == "TestScorecard":
            page["visualInteractions"] = [{"source": "TestModelSlicer", "target": "ModelComparison", "type": "NoFilter"}]
        write_json(folder / "page.json", page)
        for v in visuals:
            write_json(folder / "visuals" / v["name"] / "visual.json", v)


def main():
    for n, expression in M.items():
        folder = HERE / "powerquery"
        folder.mkdir(exist_ok=True)
        (folder / f"{n}.pq").write_text(expression + "\n", encoding="utf-8")
    dax = "// Create these as measures on DimModel, or use the authored model.bim.\n// Formats and descriptions are embedded in model.bim.\n\n"
    dax += "\n\n".join(f"// {d}\n{n} =\n{e}" for n, e, _, _, d in MEASURES) + "\n"
    (HERE / "measures.dax").write_text(dax, encoding="utf-8")
    write_json(HERE / "GridCast.SemanticModel/definition.pbism", {"$schema": SCHEMA + "item/semanticModel/definitionProperties/1.0.0/schema.json", "version": "4.0", "settings": {"qnaEnabled": False}})
    write_json(HERE / "GridCast.SemanticModel/model.bim", model())
    write_json(HERE / "GridCast.pbip", {"$schema": SCHEMA + "pbip/pbipProperties/1.0.0/schema.json", "version": "1.0", "artifacts": [{"report": {"path": "GridCast.Report"}}], "settings": {"enableAutoRecovery": True}})
    write_json(HERE / "GridCastTheme.json", {"name": "GridCast", "dataColors": ["#137E81", "#E79436", "#5675AC", "#915F9D", "#6B8D3E", "#B3514F"], "background": "#F5F7FA", "foreground": "#173246", "tableAccent": "#137E81", "textClasses": {"label": {"fontFace": "Segoe UI", "fontSize": 11, "color": "#173246"}, "title": {"fontFace": "Segoe UI Semibold", "fontSize": 15, "color": "#173246"}, "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 30, "color": "#173246"}}})
    build_report()
    print("Generated PBIP semantic/report source, Power Query, DAX and theme. Native execution remains unverified.")


if __name__ == "__main__":
    main()
