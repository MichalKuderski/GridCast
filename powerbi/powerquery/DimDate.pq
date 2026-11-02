let
    Source = ReadCsv("DimDate.csv"),
    Typed = Table.TransformColumnTypes(Source, {
        {"Date", type date}, {"Year", Int64.Type}, {"MonthNumber", Int64.Type},
        {"MonthName", type text}, {"YearMonth", type text},
        {"DayOfWeekNumber", Int64.Type}, {"DayOfWeekName", type text}, {"IsWeekend", type logical}}, "en-US")
in
    Typed
