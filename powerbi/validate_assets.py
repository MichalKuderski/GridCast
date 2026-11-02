"""Validate authored PBIP/PBIR JSON and model/report references.

python powerbi/validate_assets.py --fetch-schemas
python powerbi/validate_assets.py  # subsequent checks use cached Microsoft schemas

This is not a substitute for Power BI Desktop refresh, DAX execution, or visual QA.
"""
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin, urldefrag
import argparse
import hashlib
import json
import re
import warnings

import jsonschema

HERE = Path(__file__).resolve().parent
CACHE = HERE / "validation" / "schemas"
ALLOWED = "https://developer.microsoft.com/json-schemas/"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-schemas", action="store_true")
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    receipts = {}

    def get_schema(url):
        url, _ = urldefrag(url)
        # Microsoft's embedded schema declares a dot-form $id, but is served
        # at the hyphen-form URL used by its parent schema's $ref.
        url = url.replace("/schema.embedded.json", "/schema-embedded.json")
        if not url.startswith(ALLOWED):
            raise ValueError(f"Unexpected schema host: {url}")
        path = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:20] + ".json")
        if not path.exists():
            if not args.fetch_schemas:
                raise FileNotFoundError(f"Missing schema {url}; run with --fetch-schemas")
            with urlopen(url, timeout=30) as response:
                payload = response.read()
            json.loads(payload)
            path.write_bytes(payload)
        payload = path.read_bytes()
        receipts[url] = {"cache": str(path.relative_to(HERE)), "sha256": hashlib.sha256(payload).hexdigest()}
        return json.loads(payload)

    files = [HERE / "GridCast.pbip", HERE / "GridCast.Report/definition.pbir", HERE / "GridCast.SemanticModel/definition.pbism"]
    files += sorted((HERE / "GridCast.Report/definition").rglob("*.json"))
    results = []
    for path in files:
        document = json.loads(path.read_text())
        schema_url = document["$schema"]
        schema = get_schema(schema_url)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            resolver = jsonschema.RefResolver(base_uri=schema_url, referrer=schema, handlers={"https": get_schema})
        validator = jsonschema.Draft7Validator(schema, resolver=resolver)
        errors = list(validator.iter_errors(document))
        if errors:
            raise AssertionError(f"{path}: " + "\n".join(f"{list(e.path)} {e.message}" for e in errors))
        results.append(str(path.relative_to(HERE)))

    model = json.loads((HERE / "GridCast.SemanticModel/model.bim").read_text())["model"]
    tables = {t["name"]: t for t in model["tables"]}
    assert len(tables) == len(model["tables"]), "Duplicate table names"
    fields = {n: {c["name"] for c in t["columns"]} | {m["name"] for m in t.get("measures", [])} for n, t in tables.items()}
    columns = {n: {c["name"] for c in t["columns"]} for n, t in tables.items()}
    measures = {n: {m["name"] for m in t.get("measures", [])} for n, t in tables.items()}
    all_measures = {m["name"]: m["expression"] for t in tables.values() for m in t.get("measures", [])}
    assert len(all_measures) == sum(len(t.get("measures", [])) for t in tables.values()), "Duplicate measures"
    for name, table in tables.items():
        assert len(columns[name]) == len(table["columns"]), "Duplicate columns"
        for col in table["columns"]:
            if "sortByColumn" in col:
                assert col["sortByColumn"] in columns[name]
    for rel in model["relationships"]:
        assert rel["fromColumn"] in fields[rel["fromTable"]]
        assert rel["toColumn"] in fields[rel["toTable"]]
        assert rel["crossFilteringBehavior"] == "oneDirection"
        assert rel["fromCardinality"] == "many" and rel["toCardinality"] == "one" and rel["isActive"] is True
        assert rel["fromTable"].startswith("Fact") and rel["toTable"].startswith("Dim")
    for table in tables.values():
        for m in table.get("measures", []):
            for t, c in re.findall(r"(FactForecast|FactDemand|DimModel|DimDate)\[([^]]+)\]", m["expression"]):
                assert c in fields[t], (m["name"], t, c)

    def check_fields(obj):
        if isinstance(obj, dict):
            for kind in ["Column", "Measure"]:
                if kind in obj:
                    f = obj[kind]
                    target = measures if kind == "Measure" else columns
                    assert f["Property"] in target[f["Expression"]["SourceRef"]["Entity"]]
            for item in obj.values():
                check_fields(item)
        elif isinstance(obj, list):
            for item in obj:
                check_fields(item)

    for path in (HERE / "GridCast.Report/definition").rglob("visual.json"):
        check_fields(json.loads(path.read_text()))
    # Invariants beyond permissive JSON schema properties; no DAX execution.
    for name, expression in all_measures.items():
        if name.startswith("Test ") or name.startswith("Future "):
            assert expression.startswith("IF(HASONEVALUE(DimModel[Model]), "), name
        if name.startswith("Test "):
            assert 'FactForecast[Split] = "test"' in expression and "NOT ISBLANK(FactForecast[ActualMW])" in expression and "NOT ISBLANK(FactForecast[ForecastMW])" in expression, name
    assert "DIVIDE(COALESCE(COUNTROWS(FILTER(" in all_measures["Test Coverage 80"], "Zero-covered intervals must return0, notBLANK"
    assert "DIVIDE(COALESCE(COUNTROWS(FILTER(" in all_measures["Test High Demand Coverage 80"], "High-demand zero-covered intervals must return0, notBLANK"
    assert "NOT ISBLANK(FactForecast[Lower80MW])" in all_measures["Test High Demand Coverage 80"] and "NOT ISBLANK(FactForecast[Upper80MW])" in all_measures["Test High Demand Coverage 80"]
    for name in ["Test Hours", "Test Interval Hours", "Test High Demand Hours"]:
        assert "COALESCE(COUNTROWS(" in all_measures[name], name
    assert "SUM(FactDemand[ActualMW])" == all_measures["Demand MWh"], "History energy must not sum duplicated forecast actuals"
    for page_path in (HERE / "GridCast.Report/definition/pages").glob("*/page.json"):
        page = json.loads(page_path.read_text())
        visuals = [json.loads(p.read_text()) for p in page_path.parent.rglob("visual.json")]
        visual_names = {v["name"] for v in visuals}
        assert len(visual_names) == len(visuals)
        tab_order = []
        for v in visuals:
            p = v["position"]
            assert p["x"] >= 0 and p["y"] >= 0 and p["x"] + p["width"] <= page["width"] and p["y"] + p["height"] <= page["height"], v["name"]
            tab_order.append((p["y"], p["x"], p["tabOrder"]))
            query = v["visual"].get("query", {})
            if "Category" in query.get("queryState", {}) or v["visual"]["visualType"] == "tableEx":
                assert query["sortDefinition"]["sort"][0]["direction"] == "Ascending", v["name"]
            assert "Y2" not in query.get("queryState", {}), "Forecast lines must share one axis"
            assert "altText" in v["visual"]["visualContainerObjects"]["general"][0]["properties"]
        assert [t[2] for t in sorted(tab_order)] == sorted(t[2] for t in tab_order), "Tab order must follow top-to-bottom/left-to-right layout"
        for interaction in page.get("visualInteractions", []):
            assert interaction["source"] in visual_names and interaction["target"] in visual_names
        if page["name"] == "TestScorecard":
            assert {"source": "TestModelSlicer", "target": "ModelComparison", "type": "NoFilter"} in page["visualInteractions"]
    result = {
        "status": "passed",
        "checks": {"official_json_schema_files": len(results), "pbir_visuals": len(list((HERE / "GridCast.Report/definition").rglob("visual.json"))), "model_tables": len(tables), "measures": sum(len(t.get("measures", [])) for t in tables.values()), "relationship_and_field_references": "passed", "measure_guards_and_missing_actual_filters": "passed", "explicit_category_sorts_and_shared_forecast_axis": "passed", "layout_bounds_alt_text_and_tab_order": "passed", "model_comparison_interaction": "passed"},
        "limitations": ["Power BI Desktop unavailable on this macOS workspace.", "Native model.bim loading, M refresh, DAX execution, and visual rendering have not been executed.", "No claim of a refreshed PBIX or a published Power BI report."],
        "validated_files": results,
        "schemas": receipts,
    }
    (HERE / "validation/schema_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["checks"], indent=2))


if __name__ == "__main__":
    main()
