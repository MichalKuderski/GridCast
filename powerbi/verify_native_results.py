"""Compare real, full-precision native DAX CSV exports to independent oracles.

No synthetic native results are supplied. All four actual exports are required.
A pass verifies the supplied values, not their provenance or visual rendering.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent

def receipt_path(path):
    """Retain useful evidence locations without publishing personal host paths."""
    try:
        return path.resolve().relative_to(HERE.parent).as_posix()
    except ValueError:
        return path.name

def read(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    return [{re.sub(r'^.*\[([^]]+)\]$',r'\1',k):v for k,v in row.items()} for row in rows]

def value(x):
    if x is None or x.strip().lower() in ('','null','(blank)'):
        return None
    if x.lower() in ('true','false'):
        return x.lower()=='true'
    try:
        return float(x.rstrip('%'))/(100 if x.endswith('%') else 1)
    except ValueError:
        return x

def equal(actual, expected, field):
    a,e=value(actual),value(expected)
    if isinstance(e,(float,int)) and not isinstance(e,bool):
        tolerance=1e-8 if field in ('Test WAPE','Test Coverage 80','Test High Demand Coverage 80','Observation Completeness') else 1e-4
        return isinstance(a,(float,int)) and not isinstance(a,bool) and math.isfinite(a) and math.isclose(a,e,rel_tol=1e-8,abs_tol=tolerance)
    return a==e

def compare(actual, expected, key):
    assert len(actual)==len(expected), f'Row count differs: actual{len(actual)}, expected{len(expected)}'
    a={r[key]:r for r in actual};e={r[key]:r for r in expected}
    assert len(a)==len(actual) and len(e)==len(expected), 'Duplicate comparison keys'
    assert set(a)==set(e), f'Keys differ: actual{set(a)}, expected{set(e)}'
    failures=[]
    for k,erow in e.items():
        for field,ev in erow.items():
            if field not in a[k] or not equal(a[k][field],ev,field):
                failures.append({'key':k,'field':field,'expected':ev,'actual':a[k].get(field)})
    assert not failures, json.dumps(failures,indent=2)

def main():
    parser=argparse.ArgumentParser()
    for label in ['contexts','models','history','primitives']:
        parser.add_argument('--'+label,required=True,type=Path,help='Real full-precision CSV export from the corresponding DAX query')
    args=parser.parse_args()
    expected_contexts=read(HERE/'validation/expected_context_metrics.csv')
    expected_models=read(HERE/'validation/expected_test_metrics.csv')
    compare(read(args.contexts),expected_contexts,'Case')
    compare(read(args.models),expected_models,'Model')
    history=read(args.history)
    assert len(history)==1
    ref=json.loads((HERE/'validation/export_reconciliation.json').read_text())
    mapping={'Demand MWh':'demand_mwh','Mean Demand MW':'mean_demand_mw','Peak Demand MW':'peak_demand_mw','Observed Hours':'observed_hours','Expected Hours':'expected_hours','Missing Hours':'missing_hours','Observation Completeness':'observation_completeness'}
    for field,key in mapping.items():
        assert field in history[0] and equal(history[0][field],str(ref[key]),field), field
    primitive=read(args.primitives)
    assert len(primitive)==1
    expected={'CountEmptyIsBlank':'true','CountEmptyNormalized':'0','ZeroCoverageNumerator':'0','NoIntervalDenominatorIsBlank':'true','ZeroActualDenominatorIsBlank':'true'}
    for field,ev in expected.items():
        assert field in primitive[0] and equal(primitive[0][field],ev,field), field
    receipt={'status':'supplied_native_export_values_match_expected','checked_at_utc':datetime.now(timezone.utc).isoformat(),'contexts':len(expected_contexts),'models':len(expected_models),'actual_exports':{k:{'path':receipt_path(v),'sha256':hashlib.sha256(v.read_bytes()).hexdigest()} for k,v in vars(args).items()},'limitations':['Export provenance must be recorded by the native operator.','This comparison does not itself establish Desktop loading, M refresh, visual rendering, screenshots, accessibility, or publication.']}
    output=HERE/'validation/native_export_reconciliation.json'
    output.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    main()
