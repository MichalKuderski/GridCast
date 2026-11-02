"""Verify recruiter links and published artifacts without authenticated clients."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPO = 'MichalKuderski/GridCast'
BASE = 'https://github.com/' + REPO


def get(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'GridCast-public-access-check'})
    # No Authorization/Cookie headers, authenticated opener, or cookie jar.
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.status, response.url, response.headers.get('Content-Type'), response.read()


def main():
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    checks = []
    for label, url in [('repository', BASE),
                       ('case_study', BASE + '/blob/main/reports/CASE_STUDY.md'),
                       ('recruiter_guide', BASE + '/blob/main/docs/RECRUITER_GUIDE.md')]:
        status, final_url, kind, data = get(url)
        checks.append({'label': label, 'url': url, 'final_url': final_url,
                       'http_status': status, 'bytes': len(data), 'content_type': kind,
                       'project_text_present': b'GridCast' in data,
                       'login_redirect': '/login' in final_url})
    files = ['README.md', 'reports/CASE_STUDY.md', 'docs/RECRUITER_GUIDE.md',
             'docs/PORTFOLIO_AND_CAREER.md', 'docs/PUBLIC_RELEASE.md',
             'docs/PUBLICATION_CHECKLIST.md', 'notebooks/GridCast_Analysis.ipynb',
             *['outputs/verification/screenshots/' + name for name in
               ['06_service_test_page.jpg', '09_service_diagnostics_page.jpg',
                '10_service_history_page.jpg', '11_service_future_page.jpg']],
             'data/powerbi/FactForecast.csv']
    for name in files:
        url = f'https://raw.githubusercontent.com/{REPO}/{commit}/{name}'
        status, final_url, kind, data = get(url)
        digest = hashlib.sha256(data).hexdigest()
        checks.append({'label': 'raw_artifact', 'path': name, 'url': url,
                       'http_status': status, 'bytes': len(data), 'sha256': digest,
                       'matches_local': digest == hashlib.sha256((ROOT / name).read_bytes()).hexdigest()})
    status, _, _, data = get(f'https://api.github.com/repos/{REPO}/git/ref/heads/main')
    head = json.loads(data)['object']['sha']
    checks.append({'label': 'anonymous_main_reference', 'http_status': status,
                   'observed_commit': head, 'matches_expected_commit': head == commit})
    passed = all(row['http_status'] == 200 and not row.get('login_redirect', False)
                 and row.get('matches_local', True) and row.get('project_text_present', True)
                 and row.get('matches_expected_commit', True) for row in checks)
    receipt = {'status': 'passed_anonymous_public_access' if passed else 'failed',
               'checked_at_utc': datetime.now(timezone.utc).isoformat(),
               'source_commit': commit, 'repository': BASE,
               'case_study': BASE + '/blob/main/reports/CASE_STUDY.md',
               'recruiter_guide': BASE + '/blob/main/docs/RECRUITER_GUIDE.md',
               'method': 'Python urllib HTTPS GET, explicit public User-Agent; no Cookie or Authorization headers, no cookie jar or authenticated GitHub client. Artifact hashes use the immutable published commit; anonymous public main-ref must match it at check time.',
               'public_sharing_scope': 'GitHub repository, rendered case study, screenshots and downloads; interactive Power BI report remains private',
               'checks': checks,
               'limitations': ['One network vantage and recorded time, not a permanent availability guarantee.',
                               'A later evidence-only commit can add this receipt without changing the verified artifact bytes.',
                               'No Windows Desktop compatibility or public interactive Power BI access is established.']}
    destination = ROOT / 'outputs/publication/anonymous_access.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': receipt['status'], 'checks': len(checks),
                      'source_commit': commit, 'receipt': str(destination.relative_to(ROOT))}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
