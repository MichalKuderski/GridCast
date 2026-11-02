let
    Source = ReadCsv("FactDemand.csv"),
    Typed = Table.TransformColumnTypes(Source,
        {{"Date", type date}, {"HourUTC", Int64.Type}, {"DateLocal", type date}, {"HourLocal", Int64.Type}, {"ActualMW", type number}}, "en-US"),
    UTC = Table.TransformColumns(Typed, {{"DateTimeUTC", each DateTimeZone.RemoveZone(DateTimeZone.SwitchZone(DateTimeZone.FromText(_), 0)), type datetime}}),
    Selected = Table.SelectColumns(UTC, {"DateTimeUTC", "Date", "HourUTC", "DateLocal", "HourLocal", "ActualMW"}),
    WeekdayNumber = Table.AddColumn(Selected, "DayOfWeekNumberLocal", each Date.DayOfWeek([DateLocal], Day.Monday) + 1, Int64.Type),
    WeekdayName = Table.AddColumn(WeekdayNumber, "DayOfWeekNameLocal", each Date.DayOfWeekName([DateLocal], "en-US"), type text)
in
    WeekdayName
