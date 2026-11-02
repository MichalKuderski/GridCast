"""Read-only full round-trip verification of the Power BI import workbook."""
from pathlib import Path
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import zipfile
import xml.etree.ElementTree as ET
from itertools import zip_longest
import openpyxl

ROOT = Path(__file__).resolve().parents[2]
FILE = Path(__file__).with_name('GridCastValidation.xlsx')
DEFINITIONS = {
    'FactDemand': {'rows': 61368, 'numeric': ['ActualMW', 'OriginalDemandMWh', 'FeatureInputMW', 'HourUTC', 'HourLocal'], 'boolean': ['IsActualValid']},
    'FactForecast': {'rows': 131544, 'numeric': ['HourUTC', 'HorizonHours', 'ActualMW', 'ForecastMW', 'Lower80MW', 'Upper80MW'], 'boolean': []},
    'DimDate': {'rows': 2558, 'numeric': ['Year', 'MonthNumber', 'DayOfWeekNumber'], 'boolean': ['IsWeekend']},
    'DimModel': {'rows': 5, 'numeric': [], 'boolean': []},
}
ERRORS = []
def check(condition, message):
    if not condition and len(ERRORS) < 20:
        ERRORS.append(message)

workbook = openpyxl.load_workbook(FILE, read_only=True, data_only=False)
check(workbook.sheetnames == list(DEFINITIONS), 'Unexpected sheets or sheet order')
receipts = []
for name, definition in DEFINITIONS.items():
    sheet = workbook[name]
    # Write-only OOXML validly omits optional worksheet dimensions. Derive the
    # actual saved extents before iteration so omitted trailing blank cells are
    # materialized and every source column is compared, including blank bounds.
    sheet.calculate_dimension(force=True)
    with (ROOT / 'data/powerbi' / (name + '.csv')).open(newline='') as stream:
        source = csv.reader(stream)
        headers = next(source)
        rows = sheet.iter_rows()
        excel_headers = [cell.value for cell in next(rows)]
        check(excel_headers == headers, f'{name}: header mismatch')
        check(sheet.max_row == definition['rows'] + 1, f'{name}: Excel row count mismatch')
        check(sheet.max_column == len(headers), f'{name}: extra columns')
        count = 0
        compared_cells = 0
        null_count = 0
        zero_count = 0
        boolean_count = 0
        maximum_error = 0.0
        for row_number, (expected_row, actual_row) in enumerate(zip_longest(source, rows), start=2):
            count += 1
            if expected_row is None or actual_row is None:
                check(False, f'{name}: missing/extra row {row_number}')
                continue
            for column_number, (header, expected, cell) in enumerate(zip(headers, expected_row, actual_row), start=1):
                compared_cells += 1
                actual = cell.value
                location = f'{name}!R{row_number}C{column_number}'
                check(cell.data_type != 'f', f'{location}: formula appeared in data-only workbook')
                if expected == '':
                    null_count += 1
                    check(actual is None, f'{location}: source blank became nonblank')
                elif header in definition['numeric']:
                    check(type(actual) in (int, float), f'{location}: numeric source lost its type')
                    if type(actual) in (int, float):
                        delta = abs(float(expected) - actual)
                        maximum_error = max(maximum_error, delta)
                        check(math.isfinite(actual) and delta <= 1e-7, f'{location}: numeric value changed beyond 1e-7')
                        zero_count += actual == 0
                elif header in definition['boolean']:
                    boolean_count += 1
                    check(type(actual) is bool and actual == (expected == 'True'), f'{location}: boolean source lost type/value')
                else:
                    check(type(actual) is str and actual == expected, f'{location}: text identifier/category changed')
        check(count == definition['rows'], f'{name}: full row comparison count mismatch')
        receipts.append({'sheet': name, 'data_rows': count, 'columns': len(headers), 'cells_compared': compared_cells,
                         'source_blanks_checked': null_count, 'numeric_zeros_checked': zero_count,
                         'typed_booleans_checked': boolean_count, 'maximum_absolute_numeric_error': maximum_error,
                         'source_sha256': hashlib.sha256((ROOT / 'data/powerbi' / (name + '.csv')).read_bytes()).hexdigest()})
        print(f'Fully compared {name}: {count} rows; {compared_cells} cells', flush=True)
workbook.close()
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
tables = []
with zipfile.ZipFile(FILE) as archive:
    table_files = [name for name in archive.namelist() if name.startswith('xl/tables/') and name.endswith('.xml')]
    check(len(table_files) == 4, 'Workbook does not contain exactly four native Excel Table parts')
    for filename in table_files:
        table = ET.fromstring(archive.read(filename))
        name = table.attrib['name']
        check(name in DEFINITIONS, f'Unexpected Excel table {name}')
        headers = [node.attrib['name'] for node in table.findall('m:tableColumns/m:tableColumn', NS)]
        with (ROOT / 'data/powerbi' / (name + '.csv')).open(newline='') as stream:
            expected = next(csv.reader(stream))
        check(headers == expected, f'{name}: native table headers differ')
        check(table.attrib.get('totalsRowShown', '0') in ['0', 'false'], f'{name}: totals row appears')
        check(table.attrib['ref'] == f'A1:{openpyxl.utils.get_column_letter(len(headers))}{DEFINITIONS[name]["rows"] + 1}', f'{name}: native table range differs')
        tables.append({'name': name, 'ref': table.attrib['ref'], 'columns': headers})
    check(not any('comments' in name.lower() for name in archive.namelist()), 'Unexpected comments in import workbook')

receipt = {'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'failed' if ERRORS else 'passed',
           'method': 'Independent read-only openpyxl full cell/type comparison plus saved OOXML native-table inspection',
           'numeric_absolute_tolerance': 1e-7, 'text_comparison': 'exact including ISO timestamp/date strings',
           'blank_policy': 'CSV empty -> Excel None, never zero or empty string', 'sheets': receipts, 'tables': tables,
           'errors': ERRORS, 'workbook_sha256': hashlib.sha256(FILE.read_bytes()).hexdigest(),
           'scope': 'Data transport workbook only. No Power BI import or native Excel recalculation claim.'}
Path(__file__).with_name('workbook_roundtrip.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'status': receipt['status'], 'tables': len(tables), 'cells_compared': sum(r['cells_compared'] for r in receipts), 'errors': ERRORS}), flush=True)
if ERRORS:
    raise SystemExit(1)
