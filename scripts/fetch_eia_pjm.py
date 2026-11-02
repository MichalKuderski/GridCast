"""Download first-party EIA PJM history and extract the frozen 2019–2025 scope.

Run `python scripts/fetch_eia_pjm.py` from any working directory. Existing raw
workbook is reused; pass --refresh to replace it with the provider's latest vintage.
Only Python's standard library is required. Never commit the >100MB workbook.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import urllib.request
from extract_eia_pjm import main as extract

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://www.eia.gov/electricity/gridmonitor/knownissues/xls/PJM.xlsx'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Download a newer provider vintage; results can change.')
    args = parser.parse_args()
    raw = ROOT / 'data/raw'
    raw.mkdir(parents=True, exist_ok=True)
    dest = raw / 'eia_pjm_full_history.xlsx'
    manifest_path = raw / 'eia_pjm_manifest.json'
    pinned = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if not dest.exists() or args.refresh:
        req = urllib.request.Request(URL, headers={'User-Agent': 'GridCast portfolio research'})
        with urllib.request.urlopen(req, timeout=180) as response:
            content = response.read()
        if not content.startswith(b'PK'):
            raise ValueError('EIA download was not an XLSX archive')
        downloaded_hash = hashlib.sha256(content).hexdigest()
        if not args.refresh and pinned.get('sha256') and downloaded_hash != pinned['sha256']:
            raise ValueError('Upstream EIA vintage changed. The included canonical CSV restores the frozen experiment. Use --refresh deliberately for a new source vintage; retain the old manifest/results in version control.')
        temporary = dest.with_suffix('.download')
        temporary.write_bytes(content)
        temporary.replace(dest)
        manifest = {'url': URL, 'file': str(dest.relative_to(ROOT)), 'bytes': len(content),
                    'sha256': downloaded_hash,
                    'retrieved_at_utc': datetime.now(timezone.utc).isoformat()}
        manifest_path.write_text(json.dumps(manifest, indent=2))
    else:
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        if manifest.get('sha256') and manifest['sha256'] != digest:
            raise ValueError('Existing source workbook checksum differs from its manifest')
        manifest.update({'url': URL, 'file': str(dest.relative_to(ROOT)), 'bytes': dest.stat().st_size, 'sha256': digest})
    extract()
    csv_path = raw / 'eia_pjm_hourly_2019_2025.csv'
    manifest['extracted_snapshot'] = {'file': str(csv_path.relative_to(ROOT)),
        'sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        'start_utc': '2019-01-01T00:00:00Z', 'end_utc_exclusive': '2026-01-01T00:00:00Z',
        'source_sheet': 'Published Hourly Data', 'target_column': 'Demand',
        'timestamp_conversion': 'source UTC hour ending minus one hour',
        'script': 'scripts/extract_eia_pjm.py'}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print('Wrote', csv_path.relative_to(ROOT))


if __name__ == '__main__':
    main()
