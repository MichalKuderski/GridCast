"""Package a self-contained, frozen Power BI snapshot for real-engine validation.

The packaged model embeds compressed CSVs in Power Query; it has no Mac/Windows
file-path or gateway dependency. This verifies the payload bytes in Python, not
Power Query execution. The canonical file-backed project is left untouched.
"""
from pathlib import Path
import base64
import gzip
import hashlib
import json
import re
import shutil
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)')
BLOCKED = {'.cache', '.git', '.venv', '.aws', '.codex', '.agents', '__pycache__', '.pbi'}


def copy_public(source, bundle):
    """Copy a public repository-relative dependency without reading private caches."""
    source = source.resolve()
    relative = source.relative_to(ROOT)
    if BLOCKED.intersection(relative.parts) or source.suffix == '.pbix':
        raise ValueError(f'Not a public validation dependency: {relative}')
    if not source.is_file():
        raise FileNotFoundError(relative)
    if source.suffix in {'.md', '.json', '.csv', '.tsv', '.txt', '.tmdl', '.pq', '.dax', '.bim'}:
        text = source.read_text(encoding='utf-8-sig')
        forbidden = [r'https?://[^\s"<>]*\.sharepoint\.com/personal/',
                     r'/(?:Users|home)/[^\s"<>]+',
                     r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                     r'gh[pousr]_[A-Za-z0-9]{30,}', r'AKIA[A-Z0-9]{16}',
                     r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}']
        if any(re.search(pattern, text) for pattern in forbidden):
            raise ValueError(f'Potential private content in public dependency: {relative}')
    target = bundle / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def close_markdown_dependencies(bundle):
    """Include local linked artifacts recursively, then verify extracted link targets."""
    visited, links = set(), []
    while True:
        pending = [p for p in bundle.rglob('*.md') if p not in visited]
        if not pending:
            break
        for document in pending:
            visited.add(document)
            for target in LINK.findall(document.read_text()):
                parts = urlsplit(target)
                if parts.scheme or target.startswith('#') or not parts.path:
                    continue
                destination = (document.parent / unquote(parts.path)).resolve()
                relative = destination.relative_to(bundle)
                if not destination.exists():
                    copy_public(ROOT / relative, bundle)
                links.append({'document': str(document.relative_to(bundle)), 'target': target})
    assert all((bundle / row['document']).parent.joinpath(unquote(urlsplit(row['target']).path)).resolve().exists() for row in links)
    return {'status': 'all_local_markdown_links_resolve', 'documents': len(visited),
            'local_links': len(links), 'broken_links': [], 'external_links_verified': False}


def main():
    files = ['FactDemand.csv', 'FactForecast.csv', 'DimDate.csv', 'DimModel.csv']
    payloads, hashes = {}, {}
    for name in files:
        data = (ROOT / 'data/powerbi' / name).read_bytes()
        payloads[name] = base64.b64encode(gzip.compress(data, mtime=0)).decode('ascii')
        assert gzip.decompress(base64.b64decode(payloads[name])) == data
        hashes[name] = hashlib.sha256(data).hexdigest()
    # Small chunks avoid very long M literal tokens while preserving exact bytes.
    entries = []
    for name, value in payloads.items():
        chunks = ','.join(json.dumps(value[i:i+24000]) for i in range(0, len(value), 24000))
        entries.append(f'#"{name}" = Text.Combine({{{chunks}}})')
    embedded = '[\n' + ',\n'.join(entries) + '\n]'
    reader = '''(filename as text) as table =>
let
    Encoded = Record.Field(EmbeddedCSVs, filename),
    Bytes = Binary.Decompress(Binary.FromText(Encoded, BinaryEncoding.Base64), Compression.GZip),
    Source = Csv.Document(Bytes, [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Nulls = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers))
in
    Nulls'''
    manifest = {'snapshot_kind': 'canonical source plus separate embedded, immutable Desktop validation copy',
                'source_csv_sha256': hashes, 'power_query_executed': False, 'dax_executed': False,
                'native_rendering_verified': False, 'publicly_published': False,
                'execution_flags_scope': 'THIS embedded Desktop artifact only; the reconstructed Service implementation has separately retained actual evidence.',
                'embedded_desktop_entrypoint': 'powerbi/GridCast-Embedded.pbip',
                'canonical_file_backed_entrypoint': 'powerbi/GridCast.pbip'}
    with tempfile.TemporaryDirectory(prefix='gridcast-pbi-package-') as temp:
        temp_root = Path(temp).resolve()
        bundle = temp_root / 'GridCast'
        shutil.copytree(ROOT / 'powerbi', bundle / 'powerbi', ignore=shutil.ignore_patterns('__pycache__', '.pbi'))
        # Keep the canonical BIM at its original relative path: actual Service
        # evidence receipts bind its exact SHA. The embedded artifact has its
        # own explicit report/model/project names rather than replacing it.
        embedded_model = bundle / 'powerbi/GridCast-Embedded.SemanticModel'
        embedded_report = bundle / 'powerbi/GridCast-Embedded.Report'
        shutil.copytree(bundle / 'powerbi/GridCast.SemanticModel', embedded_model)
        shutil.copytree(bundle / 'powerbi/GridCast.Report', embedded_report)
        model_path = embedded_model / 'model.bim'
        model = json.loads(model_path.read_text())
        model['model']['expressions'] = [{'name':'EmbeddedCSVs', 'kind':'m', 'expression':embedded.splitlines()},
                                         {'name':'ReadCsv', 'kind':'m', 'expression':reader.splitlines()}]
        for annotation in model['model'].get('annotations', []):
            if annotation['name'] == 'PBI_QueryOrder':
                annotation['value'] = json.dumps(['EmbeddedCSVs', 'ReadCsv', *['FactDemand', 'FactForecast', 'DimDate', 'DimModel']])
        model_path.write_text(json.dumps(model, indent=2))
        embedded_queries = bundle / 'powerbi/embedded-powerquery'
        embedded_queries.mkdir()
        (embedded_queries / 'ReadCsv.pq').write_text(reader + '\n')
        (embedded_queries / 'EmbeddedCSVs.pq').write_text(embedded + '\n')
        project = json.loads((bundle / 'powerbi/GridCast.pbip').read_text())
        project['artifacts'] = [{'report': {'path': 'GridCast-Embedded.Report'}}]
        (bundle / 'powerbi/GridCast-Embedded.pbip').write_text(json.dumps(project, indent=2) + '\n')
        definition = json.loads((embedded_report / 'definition.pbir').read_text())
        definition['datasetReference'] = {'byPath': {'path': '../GridCast-Embedded.SemanticModel'}}
        (embedded_report / 'definition.pbir').write_text(json.dumps(definition, indent=2) + '\n')
        for name in ['SOURCES.md', 'MODEL_CARD.md', 'DATA_DICTIONARY.md']:
            dest = bundle / 'docs' / name
            dest.parent.mkdir(exist_ok=True)
            shutil.copy2(ROOT / 'docs' / name, dest)
        (bundle / 'data/powerbi').mkdir(parents=True)
        for name in files:
            shutil.copy2(ROOT / 'data/powerbi' / name, bundle / 'data/powerbi' / name)
        (bundle / 'outputs').mkdir()
        for name in ['run_summary.json', 'model_metrics.csv', 'data_quality.json']:
            shutil.copy2(ROOT / 'outputs' / name, bundle / 'outputs' / name)
        # Only public evidence is selected; raw full-table TMDL with personal
        # cloud partitions lives exclusively in the ignored .cache directory.
        seeds = [ROOT / 'LICENSE', ROOT / 'docs/PUBLICATION_CHECKLIST.md',
                 ROOT / 'outputs/VALIDATION.md',
                 *[p for p in (ROOT / 'outputs/verification/service_exports').iterdir() if p.is_file()],
                 *[ROOT / 'outputs/verification' / n for n in [
                     'service_session_status.json', 'service_visual_acceptance.json',
                     'privacy_access_check.json', 'service_upload_manifest.json', 'publication_audit.json']],
                 *[ROOT / 'outputs/verification/screenshots' / n for n in [
                     '03_service_relationships.jpg', '04_service_refresh_completed.jpg',
                     '06_service_test_page.jpg', '07_service_baseline_filter.jpg',
                     '08_service_june_filter.jpg', '09_service_diagnostics_page.jpg',
                     '10_service_history_page.jpg', '11_service_future_page.jpg']],
                 *[p for p in (ROOT / 'outputs/service-validation').iterdir()
                   if p.is_file() and p.suffix in {'.json', '.md', '.tmdl', '.xlsx'}]]
        for source in seeds:
            copy_public(source, bundle)
        # Generator is intentionally omitted: the package is a read-only snapshot.
        (bundle / 'powerbi/build_assets.py').unlink(missing_ok=True)
        text = '''# GridCast real-engine validation snapshot

This archive preserves the canonical file-backed source and a SEPARATE embedded
Desktop copy. The embedded model contains the four frozen CSVs as compressed
Power Query literals. It needs no DataFolder or gateway; refreshing reimports the
SAME frozen snapshot, fetches no new EIA observations and retrains no model.

Windows Desktop: open powerbi/GridCast-Embedded.pbip and refresh. THIS embedded
PBIP has NOT been opened/refreshed/rendered in Windows; its execution flags remain
false. The four report pages and DAX definitions are prepared source, not proof.
Follow powerbi/NATIVE_ACCEPTANCE.md, execute standalone read-only queries01–05 in
powerbi/queries, export actual native query results, compare with the expected
fixtures, inspect slicers/plots, and retain genuine report screenshots.

A separately reconstructed Power BI SERVICE implementation has passed actual
refresh, persistent DAX/metadata parity and observed report rendering/filter
checks. Read powerbi/SERVICE_VALIDATION.md and its included public evidence,
screenshots and receipts under outputs/verification/. That evidence establishes
Service behavior, NOT Windows PBIP compatibility. Service-only layout/line-style
refinements do not imply byte-identical PBIR source. No PBIX download or public
sharing is claimed, and continued Service access after the automatic trial notice
is unverified. No private account paths or full cloud-source TMDL are included.

powerbi/GridCast.pbip and its canonical model/M files are also retained unchanged
at their original paths so evidence source hashes remain verifiable. This version
requires setting DataFolder; its instructions are in powerbi/README.md. The
embedded artifact uses GridCast-Embedded.Report and GridCast-Embedded.SemanticModel;
embedded helper queries are in powerbi/embedded-powerquery/. Do not regenerate or
change the frozen snapshot while using its evidence receipts. Original EIA source
restoration/full Python project reproduction belongs to the repository, not this
Desktop-validation/evidence archive.
'''
        (bundle / 'START_HERE.md').write_text(text)
        manifest['markdown_dependency_closure'] = close_markdown_dependencies(bundle)
        canonical_bim = bundle / 'powerbi/GridCast.SemanticModel/model.bim'
        manifest['canonical_model_sha256'] = hashlib.sha256(canonical_bim.read_bytes()).hexdigest()
        assert canonical_bim.read_bytes() == (ROOT / 'powerbi/GridCast.SemanticModel/model.bim').read_bytes()
        # Read-only public measure projection only; no source partition escaped.
        public_tmdl = bundle / 'outputs/verification/service_exports/metadata_measures_native.tmdl'
        assert not re.search(r'^\s*partition\b|https?://|Web\.Contents|File\.Contents', public_tmdl.read_text(), re.M)
        manifest['public_service_evidence_included'] = True
        manifest['private_cache_included'] = False
        manifest['public_file_sha256'] = {str(p.relative_to(bundle)): hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in sorted(bundle.rglob('*')) if p.is_file()}
        (bundle / 'snapshot_manifest.json').write_text(json.dumps(manifest, indent=2))
        dist = ROOT / 'dist'
        dist.mkdir(exist_ok=True)
        output = dist / 'GridCast-PowerBI-Validation.zip'
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(bundle.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(temp_root))
        with zipfile.ZipFile(output) as archive:
            assert archive.testzip() is None
            restored = json.loads(archive.read('GridCast/powerbi/GridCast-Embedded.SemanticModel/model.bim'))
            assert 'File.Contents' not in json.dumps(restored)
            current_visual = (ROOT / 'powerbi/GridCast.Report/definition/pages/TestScorecard/visuals/CoverageCard/visual.json').read_bytes()
            assert archive.read('GridCast/powerbi/GridCast.Report/definition/pages/TestScorecard/visuals/CoverageCard/visual.json') == current_visual
            assert archive.read('GridCast/powerbi/GridCast-Embedded.Report/definition/pages/TestScorecard/visuals/CoverageCard/visual.json') == current_visual
        manifest['archive_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
        manifest['archive_bytes'] = output.stat().st_size
        manifest['payload_round_trip_verified'] = True
        (ROOT / 'outputs/verification/portable_snapshot.json').write_text(json.dumps(manifest, indent=2))
        print(json.dumps({'archive': str(output.relative_to(ROOT)),
                          'archive_sha256': manifest['archive_sha256'],
                          'archive_bytes': manifest['archive_bytes'],
                          'public_file_count': len(manifest['public_file_sha256']),
                          'markdown_dependency_closure': manifest['markdown_dependency_closure'],
                          'embedded_desktop_entrypoint': manifest['embedded_desktop_entrypoint'],
                          'payload_round_trip_verified': True,
                          'embedded_desktop_runtime_verified': False,
                          'public_service_evidence_included': True}, indent=2))


if __name__ == '__main__':
    main()
