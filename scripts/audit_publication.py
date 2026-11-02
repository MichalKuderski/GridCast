"""Audit local publication evidence without network access or publishing anything.

This checks numerical receipts, artifact links, notebook outputs, data provenance,
and public-facing status disclosures. It audits saved Service evidence but does
not rerun Power BI, certify Windows Desktop, hosted CI, public link access, or
that a historical fresh-environment run occurred.
Run from any directory: python scripts/audit_publication.py
"""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit
import ast
import csv
import hashlib
import json
import math
import re
import sys
import importlib.util
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'outputs/verification/publication_audit.json'


def read_json(path):
    return json.loads((ROOT / path).read_text())


def read_csv(path):
    with (ROOT / path).open(newline='') as stream:
        return list(csv.DictReader(stream))


def sha256(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    checks, findings = [], []

    def record(name, passed, evidence, severity='P2', remedy=None):
        checks.append({'check': name, 'status': 'passed' if passed else 'failed', 'evidence': evidence})
        if not passed:
            findings.append({'severity': severity, 'check': name, 'evidence': evidence,
                             'remedy': remedy or 'Resolve the discrepancy and rerun this audit.'})

    summary = read_json('outputs/run_summary.json')
    quality = read_json('outputs/data_quality.json')
    manifest = read_json('data/raw/eia_pjm_manifest.json')
    source_audit = read_json('data/raw/eia_pjm_initial_audit.json')
    source_csv = 'data/raw/eia_pjm_hourly_2019_2025.csv'
    digest = sha256(source_csv)
    record('canonical_source_hashes', digest == manifest['extracted_snapshot']['sha256'] == source_audit['csv_sha256'],
           {'canonical_csv': source_csv, 'sha256': digest})
    workbook_path = manifest['file']
    workbook = ROOT / workbook_path
    if workbook.exists():
        record('local_original_workbook_hash', sha256(workbook_path) == manifest['sha256'],
               {'file': workbook_path, 'bytes': workbook.stat().st_size, 'sha256': sha256(workbook_path)})
    else:
        checks.append({'check': 'local_original_workbook_hash', 'status': 'not_applicable',
                       'evidence': 'Large workbook is intentionally excluded; canonical CSV remains available.'})

    # Mock both failure paths: no network and no mutation of the real snapshot.
    sys.path.insert(0, str(ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location('gridcast_fetch_publication_audit', ROOT / 'scripts/fetch_eia_pjm.py')
    fetch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fetch)

    class AlteredUpstreamResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'PK altered upstream vintage'

    guard_results = {}
    with tempfile.TemporaryDirectory(prefix='gridcast-source-guard-') as temporary:
        fake_root = Path(temporary)
        fake_raw = fake_root / 'data/raw'
        fake_raw.mkdir(parents=True)
        fake_manifest = fake_raw / 'eia_pjm_manifest.json'
        fake_manifest.write_text(json.dumps({'sha256': '0' * 64}))
        before_manifest = fake_manifest.read_bytes()
        fake_csv = fake_raw / 'eia_pjm_hourly_2019_2025.csv'
        fake_csv.write_text('PINNED_CANONICAL_EXTRACT')
        fetch.ROOT = fake_root
        with patch.object(sys, 'argv', ['fetch_eia_pjm.py']), patch.object(fetch.urllib.request, 'urlopen', return_value=AlteredUpstreamResponse()), patch.object(fetch, 'extract') as extract_mock:
            refused = False
            try:
                fetch.main()
            except ValueError as error:
                refused = 'vintage changed' in str(error)
            guard_results['changed_upstream_refused_before_mutation'] = refused and not extract_mock.called and fake_manifest.read_bytes() == before_manifest and fake_csv.read_text() == 'PINNED_CANONICAL_EXTRACT' and not (fake_raw / 'eia_pjm_full_history.xlsx').exists()
        (fake_raw / 'eia_pjm_full_history.xlsx').write_bytes(b'PK corrupt local workbook')
        with patch.object(sys, 'argv', ['fetch_eia_pjm.py']), patch.object(fetch, 'extract') as extract_mock:
            refused = False
            try:
                fetch.main()
            except ValueError as error:
                refused = 'checksum differs' in str(error)
            guard_results['corrupt_local_workbook_refused_before_extraction'] = refused and not extract_mock.called
    record('source_restoration_failure_guards', all(guard_results.values()),
           {'mocked_checks': guard_results, 'network_requests': 0,
            'limitation': 'Failure paths use temporary files and mocked bytes; no current upstream download was requested.'})

    raw = read_csv(source_csv)
    history = read_csv('data/processed/demand_hourly.csv')
    forecasts = read_csv('data/powerbi/FactForecast.csv')
    model = summary['selected_model']
    test = [r for r in forecasts if r['Model'] == model and r['Split'] == 'test' and r['ActualMW']]
    baseline = [r for r in forecasts if r['Model'] == 'DailyNaive' and r['Split'] == 'test' and r['ActualMW']]
    actual = [float(r['ActualMW']) for r in test]
    error = [float(r['ForecastMW']) - a for r, a in zip(test, actual)]
    mae = sum(abs(e) for e in error) / len(error)
    rmse = math.sqrt(sum(e*e for e in error) / len(error))
    wape = 100 * sum(abs(e) for e in error) / sum(actual)
    bias = sum(error) / len(error)
    coverage = sum(float(r['Lower80MW']) <= a <= float(r['Upper80MW']) for r, a in zip(test, actual)) / len(test)
    base_mae = sum(abs(float(r['ForecastMW']) - float(r['ActualMW'])) for r in baseline) / len(baseline)
    gain = 100 * (1 - mae / base_mae)
    computed = {'N': len(test), 'MAE_MW': mae, 'RMSE_MW': rmse, 'WAPE_pct': wape, 'Bias_MW': bias,
                'coverage': coverage, 'daily_naive_MAE_MW': base_mae, 'MAE_improvement_pct': gain}
    matched = len(test) == summary['test_metrics']['N']
    for key, value in [('MAE_MW', mae), ('RMSE_MW', rmse), ('WAPE_pct', wape), ('Bias_MW', bias)]:
        matched = matched and math.isclose(value, summary['test_metrics'][key], abs_tol=2e-6)
    matched = matched and math.isclose(coverage, summary['test_interval_coverage'], abs_tol=1e-12)
    record('headline_metrics_recomputed_from_export', matched, computed)
    record('baseline_pairs_are_identical', [r['DateTimeUTC'] for r in baseline] == [r['DateTimeUTC'] for r in test],
           {'champion_valid_pairs': len(test), 'daily_naive_valid_pairs': len(baseline)})
    record('quality_population_and_exclusions', len(raw) == len(history) == quality['hourly_rows'] and
           sum(not r['ActualMW'] for r in history) == quality['excluded_actual_values'],
           {'source_rows': len(raw), 'history_rows': len(history),
            'null_cleaned_actuals': sum(not r['ActualMW'] for r in history),
            'reported_exclusions': quality['excluded_actual_values']})
    high = [e for e, a in zip(error, actual) if a >= summary['training_p90_MW']]
    record('high_demand_failure_metrics', len(high) == summary['test_high_demand_metrics']['N'] and
           math.isclose(sum(high)/len(high), summary['test_high_demand_metrics']['Bias_MW'], abs_tol=2e-6),
           {'threshold_MW': summary['training_p90_MW'], 'N': len(high), 'bias_MW': sum(high)/len(high)})
    scores = read_csv('outputs/model_metrics.csv')
    ridge = next(r for r in scores if r['Model'] == 'Ridge' and r['Split'] == 'test')
    record('rmse_tradeoff_retained', float(ridge['RMSE_MW']) < rmse,
           {'ridge_RMSE_MW': float(ridge['RMSE_MW']), 'selected_RMSE_MW': rmse})

    receipt = read_json('outputs/reproduction_check.json')
    receipt_matches = []
    for path, entry in receipt['checks'].items():
        actual_hash = sha256(path)
        receipt_matches.append({'path': path, 'sha256': actual_hash, 'matches_saved_receipt': actual_hash == entry['sha256']})
    record('saved_same_environment_reproduction_hashes', all(x['matches_saved_receipt'] for x in receipt_matches), receipt_matches)
    clean = read_json('outputs/clean_reproduction_check.json')
    record('fresh_environment_receipt_scope_is_local', clean['status'] == 'passed' and
           'same host/platform' in clean.get('environment', '') and 'hosted CI' in clean.get('scope', ''),
           {'scope': clean.get('scope'), 'environment': clean.get('environment'),
            'limitation': 'Historical receipt read; this audit does not rerun or independently attest the original installation.'})

    nb_path = 'notebooks/GridCast_Analysis.ipynb'
    notebook = read_json(nb_path)
    code = [c for c in notebook['cells'] if c['cell_type'] == 'code']
    errors = [o for c in code for o in c.get('outputs', []) if o.get('output_type') == 'error']
    embedded = sum('image/png' in o.get('data', {}) for c in code for o in c.get('outputs', []))
    figures = sorted((ROOT / 'reports/figures').glob('*.png'))
    record('notebook_saved_execution_and_figures', bool(code) and not errors and
           all(c.get('execution_count') is not None for c in code) and embedded == len(figures) == 7,
           {'cells': len(notebook['cells']), 'code_cells': len(code), 'error_outputs': len(errors),
            'embedded_pngs': embedded, 'saved_pngs': [str(p.relative_to(ROOT)) for p in figures],
            'limitation': 'Saved execution and image presence checked; no new native/browser visual inspection.'})

    markdown = [ROOT / 'README.md', *(ROOT / 'docs').glob('*.md'), *(ROOT / 'reports').glob('*.md'),
                *(ROOT / 'outputs').glob('*.md'), ROOT / 'powerbi/README.md',
                ROOT / 'powerbi/NATIVE_ACCEPTANCE.md', ROOT / 'powerbi/SERVICE_VALIDATION.md']
    # Destinations in this repository have no literal spaces or nested parentheses.
    link_pattern = re.compile(r'!?\[([^\]]*)\]\(([^\s)]+)(?:\s+"[^"]*")?\)')
    broken, local_links, external_links = [], [], []
    for path in markdown:
        if not path.exists():
            broken.append({'document': str(path.relative_to(ROOT)), 'target': '(document missing)'})
            continue
        for label, target in link_pattern.findall(path.read_text()):
            parts = urlsplit(target)
            if parts.scheme or target.startswith('#'):
                external_links.append({'document': str(path.relative_to(ROOT)), 'target': target})
                continue
            dest = (path.parent / unquote(parts.path)).resolve()
            item = {'document': str(path.relative_to(ROOT)), 'target': target}
            local_links.append(item)
            if not dest.exists():
                broken.append(item)
    record('relative_artifact_links_resolve', not broken,
           {'checked_local_links': len(local_links), 'broken': broken,
            'external_links_checked': False, 'external_link_count': len(external_links)})

    private_paths, suspicious_secrets = [], []
    allowed_suffixes = {'.md', '.py', '.json', '.ipynb', '.html', '.yml', '.yaml', '.txt', '.toml', '.pq', '.dax', '.bim', '.csv'}
    excluded = {'.git', '.venv', '.cache', '__pycache__'}
    scanned = 0
    path_pattern = re.compile(r'/(?:Users|home)/[^\s"\x27<>]+|/private/(?:var|tmp)/[^\s"\x27<>]+|file://[^\s"\x27<>]+')
    secret_pattern = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16}')
    for path in ROOT.rglob('*'):
        if not path.is_file() or excluded.intersection(path.relative_to(ROOT).parts) or path.suffix not in allowed_suffixes:
            continue
        if path.resolve() in {Path(__file__).resolve(), DEST.resolve()}:
            continue  # The auditor itself contains detection patterns, not disclosed data.
        try:
            content = path.read_text()
        except UnicodeDecodeError:
            continue
        scanned += 1
        for match in path_pattern.finditer(content):
            private_paths.append({'file': str(path.relative_to(ROOT)), 'line': content.count('\n', 0, match.start()) + 1,
                                  'kind': 'absolute_machine_path'})
        for match in secret_pattern.finditer(content):
            suspicious_secrets.append({'file': str(path.relative_to(ROOT)), 'line': content.count('\n', 0, match.start()) + 1,
                                       'kind': 'credential_signature'})
    record('public_material_private_path_scan', not private_paths and not suspicious_secrets,
           {'scanned_text_files': scanned, 'absolute_path_hits': private_paths, 'credential_signature_hits': suspicious_secrets,
            'limitation': 'Heuristic signature/path scan; not a complete secret or personal-data certification.'})

    readme = (ROOT / 'README.md').read_text()
    case = (ROOT / 'reports/CASE_STUDY.md').read_text()
    career = (ROOT / 'docs/PORTFOLIO_AND_CAREER.md').read_text()
    card = (ROOT / 'docs/MODEL_CARD.md').read_text()
    checklist = (ROOT / 'docs/PUBLICATION_CHECKLIST.md').read_text()
    expected_tokens = {'README.md': ['4.38%', '4,219', '8,735', '13.2%', '78.6%', 'Ridge', 'historical'],
                       'reports/CASE_STUDY.md': ['4.38%', '4,219', '8,735', '13.2%', '78.6%', 'Ridge', '6,593'],
                       'docs/PORTFOLIO_AND_CAREER.md': ['4.38%', '8,735', '13.2%', '78.6%']}
    missing_tokens = []
    for path, tokens in expected_tokens.items():
        text = (ROOT/path).read_text()
        for token in tokens:
            if token.lower() not in text.lower() and not (token == '13.2%' and '13.23%' in text):
                missing_tokens.append({'file': path, 'expected_frozen_run_token': token})
    record('rounded_headline_claims_match_frozen_run', not missing_tokens,
           {'checks': expected_tokens, 'missing_or_changed': missing_tokens,
            'limitation': 'Frozen-run headline tokens, not a general natural-language truth checker.'})
    record('historical_and_native_limitations_disclosed', all('historical' in text.lower() for text in [readme, case, career, card]) and
           all('windows' in text.lower() and 'desktop' in text.lower() and
               any(word in text.lower() for word in ['untested', 'unverified', 'pending', 'remain open', 'not tested'])
               for text in [readme, case, career, card]),
           {'documents': ['README.md', 'reports/CASE_STUDY.md', 'docs/PORTFOLIO_AND_CAREER.md', 'docs/MODEL_CARD.md']})
    sections = re.split(r'^## ', checklist, flags=re.M)
    native_section = next((s for s in sections if s.startswith('Native Power BI acceptance')), '')
    native_checks = re.findall(r'^- \[([xX ])\] (.+)$', native_section, flags=re.M)
    record('unperformed_native_checks_are_open', bool(native_checks) and not any(state.lower() == 'x' for state, _ in native_checks),
           {'native_items': len(native_checks), 'checked_native_items': sum(state.lower() == 'x' for state, _ in native_checks)})
    public_path = ROOT / 'outputs/publication/anonymous_access.json'
    if public_path.exists():
        public = json.loads(public_path.read_text())
        public_checks = public.get('checks', [])
        matching_artifacts = all(sha256(row['path']) == row['sha256']
                                 for row in public_checks if 'path' in row)
        record('public_link_access_evidence',
               public.get('status') == 'passed_anonymous_public_access' and
               len(public_checks) >= 12 and matching_artifacts and
               all(row['http_status'] == 200 and not row.get('login_redirect', False) and
                   row.get('matches_local', True) for row in public_checks),
               {'receipt': str(public_path.relative_to(ROOT)),
                'method': public.get('method'), 'checks': len(public_checks),
                'current_artifact_hashes_match': matching_artifacts,
                'limitation': 'Retained anonymous network observations, not a new request or permanent availability guarantee.'})
    else:
        record('public_link_validation_not_claimed', bool(re.search(r'^- \[ \] The repository and portfolio links work', checklist, re.M)),
               {'public_links': 'No published repository/portfolio link is available to validate in this local audit.'})

    # These are retained observations and comparison receipts, not a new engine run.
    service = read_json('outputs/verification/service_session_status.json')
    native = read_json('powerbi/validation/native_export_reconciliation.json')
    metadata = read_json('outputs/verification/service_exports/metadata_reconciliation.json')
    integrity = read_json('outputs/verification/service_exports/import_integrity_reconciliation.json')
    visual = read_json('outputs/verification/service_visual_acceptance.json')
    future = read_json('outputs/verification/service_exports/future_visual_display_reconciliation.json')
    access = read_json('outputs/verification/privacy_access_check.json')
    bound_hashes = []

    def inspect_bound_hashes(value):
        if isinstance(value, dict):
            for path_key, hash_key in [('path', 'sha256'), ('csv_path', 'csv_sha256'),
                                       ('raw_tsv_path', 'raw_tsv_sha256')]:
                if path_key in value and hash_key in value:
                    bound_hashes.append({'path': value[path_key],
                                         'sha256_matches': sha256(value[path_key]) == value[hash_key]})
            for child in value.values():
                inspect_bound_hashes(child)
        elif isinstance(value, list):
            for child in value:
                inspect_bound_hashes(child)

    for saved_receipt in [native, metadata, integrity, future]:
        inspect_bound_hashes(saved_receipt)
    record('service_receipt_file_hash_bindings', bool(bound_hashes) and
           all(item['sha256_matches'] for item in bound_hashes),
           {'file_bindings': bound_hashes,
            'limitation': 'Binds the retained files and source/provenance snapshots to their receipts; does not create new native execution evidence.'})
    record('saved_service_runtime_receipts',
           service['refresh_verified'] and service['persistent_measures_verified'] and
           service['dax_metric_parity_verified'] and
           native['status'] == 'supplied_native_export_values_match_expected' and
           metadata['status'] == 'actual_service_metadata_matches_canonical_with_documented_service_differences' and
           integrity['status'] == 'actual_service_import_integrity_matches_expected',
           {'manual_refresh': service['manual_refresh'], 'model_count': native['models'],
            'context_count': native['contexts'], 'metadata_receipt_status': metadata['status'],
            'import_integrity_status': integrity['status'],
            'limitation': 'Saved genuine Service evidence; this audit does not execute M, DAX or the visual engine.'})
    screenshot_checks = []
    for page in visual['pages']:
        screenshot_checks.append({'page': page['page'], 'path': page['screenshot'],
                                  'sha256_matches': sha256(page['screenshot']) == page['sha256']})
    record('saved_service_visual_receipts',
           visual['status'] == 'passed_service_visual_acceptance' and len(visual['pages']) == 4 and
           sum(p['visual_count'] for p in visual['pages']) == visual['total_visuals'] == 35 and
           all(p['sha256_matches'] for p in screenshot_checks) and
           service['report_render_verified'] and service['report_screenshots_verified'],
           {'screenshots': screenshot_checks, 'visual_count': visual['total_visuals'],
            'filter_cases': len(visual['observed_filter_checks']),
            'limitation': 'Screenshot hashes verify retained reviewed files, not new live rendering or full accessibility certification.'})
    future_hashes = all(sha256(p['path']) == p['sha256'] for p in future['raw_captures'])
    future_hashes = future_hashes and sha256(future['normalized_display']['path']) == future['normalized_display']['sha256']
    record('saved_future_display_receipt',
           future['status'] == 'passed_rounded_rendered_ui_parity' and future['unique_rows_checked'] == 24 and
           future['numeric_display_cells_checked'] == 72 and future['maximum_integer_display_difference'] == 0 and
           future['all_24_hourly_timestamps_present'] and future['rendered_bound_ordering_passed'] and future_hashes,
           {'rows': future['unique_rows_checked'], 'numeric_display_cells': future['numeric_display_cells_checked'],
            'raw_and_normalized_hashes_match': future_hashes, 'evidence_class': future['evidence_class']})
    record('saved_service_access_scope',
           access['report']['direct_access_results'] == access['semantic_model']['direct_access_results'] == 1 and
           access['report']['direct_access_roles'] == access['semantic_model']['direct_access_roles'] ==
           ['owner: Workspace Admin, All permissions granted'] and
           access['report']['links_message'].startswith("This report doesn't have any links yet") and
           access['semantic_model']['links_message'].startswith('No related reports have been shared yet') and
           not access['permission_mutations_performed'] and not access['public_sharing_performed'] and
           not access['unexpected_license_notice']['access_after_trial_expiry_verified'],
           {'report_direct_access_results': access['report']['direct_access_results'],
            'model_direct_access_results': access['semantic_model']['direct_access_results'],
            'sharing_links': 'No report/model links in inspected UI; organization policies still apply.',
            'trial_scope': access['unexpected_license_notice'],
            'limitation': 'Saved UI observations; not an independent tenant security or license audit.'})

    lock = (ROOT / 'requirements-lock.txt').read_text()
    workflow = (ROOT / '.github/workflows/validate.yml').read_text()
    hosted_path = ROOT / 'outputs/publication/hosted_ci.json'
    hosted = json.loads(hosted_path.read_text()) if hosted_path.exists() else {}
    hosted_inputs = hosted.get('validated_input_hashes', [])
    hosted_verified = bool(hosted_inputs) and all(sha256(row['path']) == row['sha256'] for row in hosted_inputs) and any(
        row.get('head_sha') == hosted.get('validated_source_commit') and
        row.get('status') == 'completed' and row.get('conclusion') == 'success'
        for row in hosted.get('runs', []))
    lock_lines = [line.strip() for line in lock.splitlines() if line.strip() and not line.startswith('#')]
    pins = [bool(re.fullmatch(r'[A-Za-z0-9_.-]+==[^;\s]+(?:\s*;.*)?', line)) for line in lock_lines]
    record('declared_ci_uses_pinned_environment', all(pins) and 'python-version:' in workflow and "'3.12'" in workflow and
           'pip install -r requirements-lock.txt' in workflow and 'unittest discover' in workflow,
           {'packages': len(lock_lines), 'runner': 'ubuntu-latest',
            'hosted_execution_verified': hosted_verified,
            'validated_source_commit': hosted.get('validated_source_commit'),
            'hosted_receipt': str(hosted_path.relative_to(ROOT)) if hosted_path.exists() else None,
            'scope': 'Retained successful GitHub CI status bound to recorded unchanged workflow, dependency, code, test and canonical-source inputs; not Windows or live Power BI execution.'})
    platform_pins = [line for line in lock_lines if line.split('==')[0].lower() in {'appnope', 'pexpect', 'ptyprocess'} and ';' not in line]
    checks.append({'check': 'cross_platform_lock_scope', 'status': 'informational',
                   'evidence': {'unconditional_platform_associated_pins': platform_pins,
                                'finding': 'appnope 1.0.0 is a pure universal wheel and uses a dummy implementation outside macOS; no Linux install failure established.',
                                'windows_ipython_colorama_is_explicitly_pinned': any(line.lower().startswith('colorama==') for line in lock_lines),
                                'windows_lock_note': 'Installed IPython metadata requires colorama on win32. If absent from the lock, pip resolves it transitively without an explicit pin; this is a portability reproducibility gap, not an observed installation failure.',
                                'recommendation': 'Use appropriate environment markers for platform-associated extras and pin active dependencies for each claimed platform. Native Windows Power BI remains outside this Python audit.'}})
    for relative in ['scripts/fetch_eia_pjm.py', 'scripts/extract_eia_pjm.py', 'scripts/run_pipeline.py', 'scripts/build_analysis.py', 'scripts/write_release_docs.py']:
        ast.parse((ROOT/relative).read_text(), filename=relative)
    checks.append({'check': 'publication_scripts_parse', 'status': 'passed', 'evidence': 'Acquisition, extraction, pipeline, notebook, and narrative builders parse as Python.'})

    result = {
        'audited_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'failed' if findings else 'passed_with_external_gates_open',
        'scope': 'Read-only local evidence audit; only this script and its JSON receipt are authored by this audit.',
        'checks': checks,
        'findings': findings,
        'remaining_unperformed_gates': [
            'Separate Windows Power BI Desktop/PBIP compatibility acceptance; completed Service checks do not establish it.',
            'Windows Python/native Desktop validation remains unclaimed; saved hosted Linux CI evidence is reported separately when available.',
            'Public-link access can change after the recorded anonymous checks; interactive Power BI publication remains outside this GitHub release.',
            'Power BI Service access after the unexpected automatic trial expires; no continued access claim.',
        ],
        'summary': computed,
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'checks': len(checks), 'findings': findings,
                      'receipt': str(DEST.relative_to(ROOT))}, indent=2))
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
