let
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
    Selected
