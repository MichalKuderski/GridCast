"""Extract a reproducible PJM demand snapshot from the official EIA BA workbook.

Uses the original reported Demand column, never silently substitutes adjusted data.
The workbook's UTC time is interval END; model timestamp uses interval START.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
EPOCH = datetime(1899, 12, 30, tzinfo=timezone.utc)


def excel_datetime(value):
    return EPOCH + timedelta(seconds=round(float(value) * 86400))


def rows(z, name, strings):
    for _, row in ET.iterparse(z.open(name), events=('end',)):
        if row.tag != '{' + NS['m'] + '}row':
            continue
        values = {}
        for c in row:
            v = c.find('m:v', NS)
            value = '' if v is None else v.text
            if c.attrib.get('t') == 's' and value is not None:
                value = strings[int(value)]
            col = ''.join(x for x in c.attrib.get('r', '') if x.isalpha())
            values[col] = value
        yield values
        row.clear()


def main():
    src = ROOT / 'data/raw/eia_pjm_full_history.xlsx'
    output = ROOT / 'data/raw/eia_pjm_hourly_2019_2025.csv'
    start = datetime(2019, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = []
    timestamps = []
    note_rows = []
    fields = ['BalancingAuthority', 'DateTimeUTC', 'IntervalEndUTC',
              'OriginalDemandMWh', 'DemandForecastMWh', 'ImputedDemandMWh',
              'AdjustedDemandMWh', 'SourceLocalDate', 'SourceHour',
              'SourceLocalTime', 'SourceTimeZone']
    with zipfile.ZipFile(src) as z:
        strings = [''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        stream = rows(z, 'xl/worksheets/sheet1.xml', strings)
        header = next(stream)
        expected = {'A': 'BA', 'B': 'UTC time', 'H': 'Demand forecast', 'I': 'Demand',
                    'L': 'Imputed demand', 'O': 'Adjusted demand'}
        assert all(header[k] == v for k, v in expected.items()), header
        for row in stream:
            if row.get('A') != 'PJM' or not row.get('B'):
                continue
            end = excel_datetime(row['B'])
            begin = end - timedelta(hours=1)
            if not start <= begin < stop:
                continue
            record = {
                'BalancingAuthority': row['A'],
                'DateTimeUTC': begin.isoformat().replace('+00:00', 'Z'),
                'IntervalEndUTC': end.isoformat().replace('+00:00', 'Z'),
                'OriginalDemandMWh': row.get('I', ''),
                'DemandForecastMWh': row.get('H', ''),
                'ImputedDemandMWh': row.get('L', ''),
                'AdjustedDemandMWh': row.get('O', ''),
                'SourceLocalDate': excel_datetime(row['C']).date().isoformat(),
                'SourceHour': row.get('D', ''),
                'SourceLocalTime': excel_datetime(row['E']).replace(tzinfo=None).isoformat(),
                'SourceTimeZone': row.get('F', ''),
            }
            records.append(record)
            timestamps.append(begin)
        for row in rows(z, 'xl/worksheets/sheet7.xml', strings):
            if row.get('A') and row.get('B'):
                note_rows.append({'column': row['A'], 'description': row['B'].strip()})
    expected_hours = int((stop - start).total_seconds() / 3600)
    assert len(records) == expected_hours, f'Expected {expected_hours} rows, got {len(records)}'
    assert len(set(timestamps)) == expected_hours, 'Duplicate source UTC timestamps'
    assert min(timestamps) == start and max(timestamps) == stop - timedelta(hours=1)
    assert all(b - a == timedelta(hours=1) for a, b in zip(sorted(timestamps), sorted(timestamps)[1:])), 'Non-hourly source gap'
    with output.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    (ROOT / 'data/raw/eia_pjm_workbook_notes.json').write_text(json.dumps(note_rows, indent=2))
    valid = [float(r['OriginalDemandMWh']) for r in records if r['OriginalDemandMWh']]
    timestamps.sort()
    audit = {
        'source_sheet': 'Published Hourly Data',
        'target_source_column': 'Demand',
        'source_utc_time_convention': 'hour ending; subtract one hour for interval start',
        'source_units': 'MWh per one-hour interval; numerically equivalent to average MW',
        'rows': len(records),
        'unique_utc_starts': len(set(timestamps)),
        'first_interval_start_utc': min(timestamps).isoformat(),
        'last_interval_start_utc': max(timestamps).isoformat(),
        'missing_demand': sum(not r['OriginalDemandMWh'] for r in records),
        'nonpositive_demand': sum(v <= 0 for v in valid),
        'imputed_demand_present': sum(bool(r['ImputedDemandMWh']) for r in records),
        'adjusted_differs_from_reported': sum(bool(r['OriginalDemandMWh']) and bool(r['AdjustedDemandMWh']) and float(r['OriginalDemandMWh']) != float(r['AdjustedDemandMWh']) for r in records),
        'min_demand_mwh': min(valid),
        'max_demand_mwh': max(valid),
        'non_hourly_gaps': sum(b-a != timedelta(hours=1) for a,b in zip(timestamps, timestamps[1:])),
        'csv_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'annual_rows': {str(year): sum(t.year == year for t in timestamps) for year in range(2019, 2026)},
    }
    (ROOT / 'data/raw/eia_pjm_initial_audit.json').write_text(json.dumps(audit, indent=2))
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
