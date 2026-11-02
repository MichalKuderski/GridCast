"""Create independent CSV-oracle expectations and read-only DAX queries.

This does NOT execute, parse, or emulate the native DAX engine. It computes
expected values directly from exported rows, including blank/zero contracts.
"""
from pathlib import Path
import csv
import json
import math
from statistics import fmean

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / 'data/powerbi'

def read(name):
    with (DATA / (name + '.csv')).open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def number(x):
    return None if x in ('', None) else float(x)

def mean(xs):
    return fmean(xs) if xs else None

def total(xs):
    return sum(xs) if xs else None

def dax_str(value):
    return '"' + value.replace('"', '""') + '"'

def main():
    forecast = read('FactForecast')
    demand = read('FactDemand')
    model_names = {r['Model'] for r in read('DimModel')}
    run = json.loads((HERE.parent / 'outputs/run_summary.json').read_text())
    champion = run['selected_model']
    threshold = run['training_p90_MW']
    model = json.loads((HERE / 'GridCast.SemanticModel/model.bim').read_text())['model']
    names = [m['name'] for t in model['tables'] for m in t.get('measures', [])]
    actuals = {r['DateTimeUTC']: number(r['ActualMW']) for r in demand}
    scored = [r for r in forecast if r['Split']=='test' and r['Model']==champion]
    missing = next(r['DateTimeUTC'] for r in scored if number(r['ActualMW']) is None)
    uncovered = next(r['DateTimeUTC'] for r in scored if number(r['ActualMW']) is not None and number(r['Lower80MW']) is not None and not number(r['Lower80MW']) <= number(r['ActualMW']) <= number(r['Upper80MW']))
    high_uncovered = next(r['DateTimeUTC'] for r in scored if number(r['ActualMW']) is not None and number(r['ActualMW']) >= threshold and number(r['Lower80MW']) is not None and number(r['Upper80MW']) is not None and not number(r['Lower80MW']) <= number(r['ActualMW']) <= number(r['Upper80MW']))
    cases = [
        {'Case':'no_model_filter'},
        {'Case':'multiple_models', 'models':[champion,'DailyNaive']},
        {'Case':'zero_models', 'models':['__not_a_model__']},
        {'Case':'champion_all', 'models':[champion]},
        {'Case':'baseline_no_intervals', 'models':['DailyNaive']},
        {'Case':'champion_june', 'models':[champion], 'date_from':'2025-06-01','date_to':'2025-06-30'},
        {'Case':'champion_empty_date', 'models':[champion], 'date_from':'2030-01-01','date_to':'2030-01-01'},
        {'Case':'champion_missing_actual_hour', 'models':[champion], 'timestamp':missing},
        {'Case':'champion_zero_coverage_hour', 'models':[champion], 'timestamp':uncovered},
        {'Case':'champion_high_demand_zero_coverage_hour', 'models':[champion], 'timestamp':high_uncovered},
        {'Case':'champion_future_date', 'models':[champion], 'date_from':'2026-01-01','date_to':'2026-01-01'},
        {'Case':'champion_validation_date', 'models':[champion], 'date_from':'2023-01-01','date_to':'2023-01-01'},
    ]
    expected = []
    for case in cases:
        selected = model_names if 'models' not in case else model_names.intersection(case['models'])
        single = len(selected)==1
        in_date = lambda r: 'date_from' not in case or case['date_from'] <= r['Date'] <= case['date_to']
        history = [r for r in demand if in_date(r)]
        observed = [number(r['ActualMW']) for r in history if number(r['ActualMW']) is not None]
        values = {name: None for name in names}
        values.update({'Demand MWh':total(observed), 'Mean Demand MW':mean(observed), 'Peak Demand MW':max(observed) if observed else None, 'Observed Hours':len(observed), 'Expected Hours':len(history), 'Missing Hours':len(history)-len(observed), 'Observation Completeness':len(observed)/len(history) if history else None, 'Training High Demand Threshold MW':threshold, 'Model Selection':next(iter(selected)) if single else 'Select one model to view forecast KPIs'})
        if single:
            rows = [r for r in forecast if r['Model'] in selected and in_date(r) and ('timestamp' not in case or r['DateTimeUTC']==case['timestamp'])]
            pairs = [r for r in rows if r['Split']=='test' and number(r['ActualMW']) is not None and number(r['ForecastMW']) is not None]
            interval = [r for r in pairs if number(r['Lower80MW']) is not None and number(r['Upper80MW']) is not None]
            high = [r for r in pairs if number(r['ActualMW']) >= threshold]
            high_interval = [r for r in interval if number(r['ActualMW']) >= threshold]
            future = [r for r in rows if r['Split']=='future']
            a = [number(r['ActualMW']) for r in pairs]
            p = [number(r['ForecastMW']) for r in pairs]
            errors = [y-x for x,y in zip(a,p)]
            width = [number(r['Upper80MW'])-number(r['Lower80MW']) for r in interval]
            high_errors = [number(r['ForecastMW'])-number(r['ActualMW']) for r in high]
            values.update({'Test Hours':len(pairs), 'Test Actual MWh':total(a), 'Test Forecast MWh':total(p), 'Test Actual MW':mean(a), 'Test Forecast MW':mean(p), 'Test MAE MW':mean([abs(e) for e in errors]), 'Test RMSE MW':math.sqrt(mean([e*e for e in errors])) if errors else None, 'Test WAPE':sum(abs(e) for e in errors)/sum(abs(x) for x in a) if a and sum(abs(x) for x in a) else None, 'Test Bias MW':mean(errors), 'Test Interval Hours':len(interval), 'Test Coverage 80':sum(number(r['Lower80MW']) <= number(r['ActualMW']) <= number(r['Upper80MW']) for r in interval)/len(interval) if interval else None, 'Test Mean Interval Width MW':mean(width), 'Test High Demand Hours':len(high), 'Test High Demand MAE MW':mean([abs(e) for e in high_errors]), 'Test High Demand Bias MW':mean(high_errors), 'Test High Demand Coverage 80':sum(number(r['Lower80MW']) <= number(r['ActualMW']) <= number(r['Upper80MW']) for r in high_interval)/len(high_interval) if high_interval else None, 'Future Forecast MW':mean([number(r['ForecastMW']) for r in future]), 'Future Lower 80 MW':mean([number(r['Lower80MW']) for r in future if number(r['Lower80MW']) is not None]), 'Future Upper 80 MW':mean([number(r['Upper80MW']) for r in future if number(r['Upper80MW']) is not None])})
        expected.append({'Case':case['Case'], **values})
    path = HERE / 'validation/expected_context_metrics.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        writer=csv.DictWriter(f, fieldnames=['Case']+names);writer.writeheader();writer.writerows(expected)
    (HERE / 'validation/context_cases.json').write_text(json.dumps({'status':'expected_only_native_unexecuted','cases':cases,'blank_contract':'CSV empty values represent DAX BLANK, not zero. Counts normalize to 0 only when exactly one model is in context; accuracy measures remain blank for empty pairs. History counts normalize to0.'}, indent=2)+'\n')
    def row_expression(case):
        row='ROW("Case", '+dax_str(case['Case'])+', '+', '.join(dax_str(n)+', ['+n+']' for n in names)+')'
        filters=[]
        if 'models' in case:
            filters.append('TREATAS({'+', '.join(dax_str(n) for n in case['models'])+'}, DimModel[Model])')
        if 'date_from' in case:
            dates=[]
            for n in ['date_from','date_to']:
                y,m,d=map(int,case[n].split('-'));dates.append(f'DATE({y},{m},{d})')
            filters.append('DATESBETWEEN(DimDate[Date], '+', '.join(dates)+')')
        if 'timestamp' in case:
            timestamp=case['timestamp'];date,time=timestamp.rstrip('Z').split('T');y,m,d=map(int,date.split('-'));h,mi,s=map(int,time.split(':'))
            filters.append(f'TREATAS({{DATE({y},{m},{d}) + TIME({h},{mi},{s})}}, FactForecast[DateTimeUTC])')
        return 'CALCULATETABLE('+row+', '+', '.join(filters)+')' if filters else row
    intro='// Read-only DAX. Run against the REFRESHED GridCast model; this file has NOT been executed here.\n// Run outside any report visual: queries define their own contexts. CSV blanks are DAX BLANK.\n'
    (HERE / 'queries/03_context_matrix.dax').write_text(intro+'EVALUATE\nUNION(\n'+',\n'.join('    '+row_expression(c) for c in cases)+'\n)\nORDER BY [Case]\n')
    test_names=[n for n in names if n.startswith('Test ')]+['Training High Demand Threshold MW']
    (HERE / 'queries/02_test_models.dax').write_text(intro+'EVALUATE\nSUMMARIZECOLUMNS(\n    DimModel[Model],\n'+',\n'.join('    '+dax_str(n)+', ['+n+']' for n in test_names)+'\n)\nORDER BY DimModel[Model]\n')
    history_names=[n for n in names if n in ['Demand MWh','Mean Demand MW','Peak Demand MW','Observed Hours','Expected Hours','Missing Hours','Observation Completeness']]
    (HERE / 'queries/01_history_totals.dax').write_text(intro+'EVALUATE\nROW(\n'+',\n'.join('    '+dax_str(n)+', ['+n+']' for n in history_names)+'\n)\n')
    (HERE / 'queries/04_blank_zero_semantics.dax').write_text(intro+'''// Isolates the documented COUNTROWS(empty) behavior without altering the model.
+EVALUATE
+VAR EmptyRows = FILTER({1}, FALSE())
+RETURN ROW(
+    "CountEmptyIsBlank", ISBLANK(COUNTROWS(EmptyRows)),
+    "CountEmptyNormalized", COALESCE(COUNTROWS(EmptyRows), 0),
+    "ZeroCoverageNumerator", DIVIDE(COALESCE(COUNTROWS(EmptyRows), 0), 1),
+    "NoIntervalDenominatorIsBlank", ISBLANK(DIVIDE(0, COUNTROWS(EmptyRows))),
+    "ZeroActualDenominatorIsBlank", ISBLANK(DIVIDE(10, 0))
+)
+'''.replace('\n+','\n'))
    print(f'Prepared {len(cases)} independent context expectations and four read-only DAX query files. Native engine remains UNEXECUTED.')

if __name__=='__main__':
    main()
