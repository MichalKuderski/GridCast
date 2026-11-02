/** Wrap exactly the four approved Power BI CSVs in typed Excel Tables. */
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'outputs/service-validation');
// The documented artifact-tool probe cannot preserve ISO identifiers as text,
// even with @ formatting. Use the validated transport fallback by default.
const fallback = true;
const runtime = process.env.CODEX_WORKSPACE_DEPENDENCIES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies');
const taskDependencies = path.join(os.tmpdir(), 'gridcast-service-workbook-dependencies');
await fs.mkdir(taskDependencies, {recursive: true});
try { await fs.symlink(path.join(runtime, 'node/node_modules'), path.join(taskDependencies, 'node_modules'), 'dir'); }
catch (error) { if (error.code !== 'EEXIST') throw error; }
const requireBundled = createRequire(path.join(taskDependencies, 'resolve.cjs'));
const {Workbook, SpreadsheetFile} = await import(pathToFileURL(requireBundled.resolve('@oai/artifact-tool')).href);
await fs.mkdir(out, {recursive: true});

const definitions = [
  {name: 'FactDemand', expectedRows: 61368, numeric: ['ActualMW', 'OriginalDemandMWh', 'FeatureInputMW', 'HourUTC', 'HourLocal'], boolean: ['IsActualValid']},
  {name: 'FactForecast', expectedRows: 131544, numeric: ['HourUTC', 'HorizonHours', 'ActualMW', 'ForecastMW', 'Lower80MW', 'Upper80MW'], boolean: []},
  {name: 'DimDate', expectedRows: 2558, numeric: ['Year', 'MonthNumber', 'DayOfWeekNumber'], boolean: ['IsWeekend']},
  {name: 'DimModel', expectedRows: 5, numeric: [], boolean: []},
];

if (fallback) {
  // Only invoke after the required artifact-tool full-scale attempt has been
  // bounded, recorded, and terminated. This is an import intermediate, not an
  // analytical workbook; the fallback writes identical typed source records.
  const python = String.raw`
from pathlib import Path
import csv, json
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.table import Table, TableColumn, TableStyleInfo
from openpyxl.utils import get_column_letter
root=Path(__import__('sys').argv[1]); definitions=json.loads(__import__('sys').argv[2])
output=root/'outputs/service-validation/GridCastValidation.xlsx'
book=Workbook(write_only=True)
for definition in definitions:
 name=definition['name'];sheet=book.create_sheet(name)
 sheet.sheet_view.showGridLines=False;sheet.freeze_panes='A2'
 with (root/'data/powerbi'/f'{name}.csv').open(newline='') as stream:
  reader=csv.reader(stream);headers=next(reader)
  for c,header in enumerate(headers,1):
   sheet.column_dimensions[get_column_letter(c)].width=max(len(header)+2,26 if header.endswith('UTC') and header not in definition['numeric'] else 16)
  styled=[]
  for header in headers:
   cell=WriteOnlyCell(sheet,value=header);cell.font=Font(name='Arial',size=10,bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='21364B');cell.alignment=Alignment(horizontal='center',vertical='center');styled.append(cell)
  sheet.append(styled);count=0
  for row in reader:
   assert len(row)==len(headers)
   values=[]
   for header,value in zip(headers,row):
    if value=='':values.append(None)
    elif header in definition['numeric']:values.append(float(value))
    elif header in definition['boolean']:
     assert value in ['True','False'];values.append(value=='True')
    else:values.append(value)
   sheet.append(values);count+=1
  assert count==definition['expectedRows'],(name,count)
 table=Table(displayName=name,ref=f'A1:{get_column_letter(len(headers))}{count+1}')
 table.tableColumns=[TableColumn(id=c,name=header) for c,header in enumerate(headers,1)]
 table.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showFirstColumn=False,showLastColumn=False,showRowStripes=True,showColumnStripes=False)
 sheet.add_table(table)
 print(f'Fallback wrote {name}: {count} rows',flush=True)
book.save(output)
print('Fallback saved workbook',flush=True)
`;
  console.log('Using documented type-preservation fallback: bundled openpyxl write_only');
  execFileSync(path.join(runtime, 'python/bin/python3'), ['-c', python, root, JSON.stringify(definitions)], {stdio: 'inherit'});
}

function parseCSV(text) {
  const rows = [];
  let row = [], field = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(field); field = ''; }
    else if (ch === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
    else if (ch !== '\r') field += ch;
  }
  if (quoted) throw new Error('Unclosed CSV quote');
  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  return rows;
}
function colName(index) {
  let result = '';
  for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) result = String.fromCharCode(65 + ((n - 1) % 26)) + result;
  return result;
}
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const workbook = Workbook.create();
const evidence = {createdAtUTC: new Date().toISOString(), purpose: 'Same approved CSV data packaged as four Excel Tables for Power BI import', authoring: fallback ? 'Bundled openpyxl write_only fallback: artifact-tool cannot preserve required ISO text identifiers; artifact-tool used for four source-top-row previews, with ISO display formats' : 'Bundled @oai/artifact-tool', sheets: []};
for (const definition of definitions) {
  const csvPath = path.join(root, 'data/powerbi', `${definition.name}.csv`);
  const bytes = await fs.readFile(csvPath);
  const matrix = parseCSV(bytes.toString('utf8'));
  const headers = matrix[0];
  if (matrix.length - 1 !== definition.expectedRows) throw new Error(`${definition.name}: unexpected row count ${matrix.length - 1}`);
  const numeric = new Set(definition.numeric), boolean = new Set(definition.boolean);
  for (let r = 1; r < matrix.length; r++) {
    if (matrix[r].length !== headers.length) throw new Error(`${definition.name}: ragged CSV row ${r + 1}`);
    for (let c = 0; c < headers.length; c++) {
      const value = matrix[r][c];
      if (value === '') matrix[r][c] = null;
      else if (numeric.has(headers[c])) {
        const number = Number(value);
        if (!Number.isFinite(number)) throw new Error(`${definition.name}: invalid numeric ${r + 1},${c + 1}`);
        matrix[r][c] = number;
      } else if (boolean.has(headers[c])) {
        if (!['True', 'False'].includes(value)) throw new Error(`${definition.name}: invalid boolean`);
        matrix[r][c] = value === 'True';
      }
    }
  }
  const sheet = workbook.worksheets.add(definition.name);
  sheet.showGridLines = false;
  const endColumn = colName(headers.length - 1);
  console.log(`Writing ${definition.name}: ${matrix.length - 1} rows x ${headers.length} columns`);
  const viewMatrix = fallback ? matrix.slice(0, 7) : matrix;
  for (let begin = 0; begin < viewMatrix.length; begin += 10000) {
    const chunk = viewMatrix.slice(begin, begin + 10000);
    sheet.getRangeByIndexes(begin, 0, chunk.length, headers.length).values = chunk;
  }
  const table = sheet.tables.add(`A1:${endColumn}${viewMatrix.length}`, true, definition.name);
  table.showTotals = false;
  table.showFilterButton = true;
  sheet.freezePanes.freezeRows(1);
  const top = sheet.getRange(`A1:${endColumn}${Math.min(viewMatrix.length, 12)}`);
  top.format.font = {name: 'Arial', size: 10};
  top.format.verticalAlignment = 'center';
  const header = sheet.getRange(`A1:${endColumn}1`);
  header.format = {fill: '#21364B', font: {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'}, rowHeight: 26, horizontalAlignment: 'center', verticalAlignment: 'center'};
  for (let c = 0; c < headers.length; c++) {
    const range = sheet.getRange(`${colName(c)}1:${colName(c)}${Math.min(viewMatrix.length, 12)}`);
    range.format.columnWidth = Math.max(headers[c].length + 2, headers[c].includes('UTC') && headers[c].includes('Time') ? 26 : 15);
    if (numeric.has(headers[c])) sheet.getRange(`${colName(c)}2:${colName(c)}${Math.min(viewMatrix.length, 12)}`).setNumberFormat(headers[c].includes('MW') || headers[c].includes('MWh') ? '0.000000' : '0');
    // The fallback's saved workbook has exact text keys. Artifact-tool's preview
    // engine auto-coerces timestamp strings; display the same source ISO labels.
    else if (fallback && headers[c].endsWith('UTC')) sheet.getRange(`${colName(c)}2:${colName(c)}${Math.min(viewMatrix.length, 12)}`).setNumberFormat('yyyy-mm-dd"T"hh:mm:ss"Z"');
  }
  evidence.sheets.push({name: definition.name, tableName: table.name, rows: matrix.length - 1, columns: headers, range: `A1:${endColumn}${matrix.length}`, source: `data/powerbi/${definition.name}.csv`, sourceSHA256: sha(bytes), numericColumns: definition.numeric, booleanColumns: definition.boolean, textColumns: headers.filter(h => !numeric.has(h) && !boolean.has(h))});
  console.log(`Populated ${definition.name}`);
}
workbook.recalculate();
for (const definition of definitions) {
  const info = evidence.sheets.find(s => s.name === definition.name);
  const range = `A1:${colName(info.columns.length - 1)}${Math.min(info.rows + 1, 7)}`;
  const inspection = await workbook.inspect({kind: 'region', sheetId: definition.name, range, maxChars: 1800, tableMaxRows: 7, tableMaxCols: info.columns.length});
  await fs.writeFile(path.join(out, `${definition.name}-inspection.ndjson`), inspection.ndjson);
  console.log(`Rendering ${definition.name}`);
  const preview = await workbook.render({sheetName: definition.name, range, scale: 1.5, format: 'png'});
  await fs.writeFile(path.join(out, `${definition.name}-preview.png`), new Uint8Array(await preview.arrayBuffer()));
}
const xlsx = path.join(out, 'GridCastValidation.xlsx');
if (!fallback) {
  console.log('Exporting workbook');
  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(xlsx);
}
const resultBytes = await fs.readFile(xlsx);
evidence.output = {file: 'outputs/service-validation/GridCastValidation.xlsx', bytes: resultBytes.length, sha256: sha(resultBytes)};
evidence.contentPolicy = 'Exactly four tables/sheets. No added formulas, summary rows, notes, comments, citations, or analysis. UTC/date keys remain exact ISO strings; numeric and boolean columns are typed; source nulls are blank.';
await fs.writeFile(path.join(out, 'workbook_build.json'), JSON.stringify(evidence, null, 2) + '\n');
console.log(JSON.stringify(evidence.output));
