let
    Source = ReadCsv("DimModel.csv"),
    Typed = Table.TransformColumnTypes(Source, {{"Model", type text}}, "en-US"),
    Selected = Table.SelectColumns(Typed, {"Model"})
in
    Selected
