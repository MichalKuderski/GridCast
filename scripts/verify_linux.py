"""Isolated Linux verification entry point; run inside the documented container.

Mount repository at /source read-only and outputs/verification at /receipt.
All fitting and notebook work happens in the container's disposable /tmp copy.
This never executes Power BI, Power Query, or DAX.
"""
from pathlib import Path
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys


def main():
    source, receipt, work = Path('/source'), Path('/receipt'), Path('/tmp/gridcast-linux')
    receipt.mkdir(parents=True, exist_ok=True)
    result = {'platform': platform.platform(), 'python': platform.python_version(),
              'machine': platform.machine(), 'native_powerbi_verified': False,
              'status': 'running', 'checks': {}}
    destination = receipt / 'linux_reproduction.json'
    try:
        with (receipt / 'linux_install.log').open('w') as log:
            subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(source / 'requirements-lock.txt')], stdout=log, stderr=subprocess.STDOUT, check=True)
        work.mkdir(exist_ok=True)
        for name in ['src', 'scripts', 'tests']:
            shutil.copytree(source / name, work / name, ignore=shutil.ignore_patterns('__pycache__'), dirs_exist_ok=True)
        (work / 'data/raw').mkdir(parents=True, exist_ok=True)
        for name in ['eia_pjm_hourly_2019_2025.csv', 'eia_pjm_initial_audit.json', 'eia_pjm_manifest.json']:
            shutil.copy2(source / 'data/raw' / name, work / 'data/raw' / name)
        commands = {
            'pipeline': [sys.executable, 'scripts/run_pipeline.py'],
            'unit_tests': [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
            'notebook': [sys.executable, 'scripts/build_analysis.py'],
        }
        environment = {**os.environ, 'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2', 'MPLBACKEND': 'Agg'}
        for name, command in commands.items():
            with (receipt / f'linux_{name}.log').open('w') as log:
                ran = subprocess.run(command, cwd=work, env=environment, stdout=log, stderr=subprocess.STDOUT)
            result['checks'][name] = {'exit_code': ran.returncode}
            if ran.returncode:
                raise RuntimeError(f'{name} failed; see linux_{name}.log')
        import pandas as pd
        import numpy as np
        actual = pd.read_csv(work / 'outputs/model_metrics.csv').set_index(['Model', 'Split']).sort_index()
        expected = pd.read_csv(source / 'outputs/model_metrics.csv').set_index(['Model', 'Split']).sort_index()
        difference = (actual - expected).abs()
        max_error = float(difference.to_numpy().max())
        if max_error > 1e-4:
            raise AssertionError(f'Cross-platform metrics differ by {max_error}, tolerance 1e-4')
        result['checks']['metric_parity'] = {'max_absolute_difference': max_error, 'absolute_tolerance': 1e-4, 'candidate_split_rows': len(actual)}
        a = pd.read_csv(work / 'data/powerbi/FactForecast.csv')
        b = pd.read_csv(source / 'data/powerbi/FactForecast.csv')
        keys = ['DateTimeUTC', 'Model', 'Split']
        if not a[keys].equals(b[keys]):
            raise AssertionError('Forecast keys differ')
        columns = ['ActualMW', 'ForecastMW', 'Lower80MW', 'Upper80MW']
        np.testing.assert_allclose(a[columns], b[columns], rtol=0, atol=1e-4, equal_nan=True)
        result['checks']['forecast_parity'] = {'rows': len(a), 'columns': columns, 'absolute_tolerance': 1e-4}
        import nbformat
        notebook = nbformat.read(work / 'notebooks/GridCast_Analysis.ipynb', as_version=4)
        nbformat.validate(notebook)
        outputs = [o for c in notebook.cells if c.cell_type == 'code' for o in c.outputs]
        if any(o.output_type == 'error' for o in outputs):
            raise AssertionError('Executed notebook contains errors')
        result['checks']['notebook_outputs'] = {'cells': len(notebook.cells), 'embedded_figures': sum('image/png' in o.get('data', {}) for o in outputs)}
        if result['checks']['notebook_outputs']['embedded_figures'] != 7:
            raise AssertionError('Notebook execution lost the required seven embedded chart outputs')
        result['source_csv_sha256'] = hashlib.sha256((work / 'data/raw/eia_pjm_hourly_2019_2025.csv').read_bytes()).hexdigest()
        result['status'] = 'passed'
    except Exception as error:
        result['status'] = 'failed'
        result['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        destination.write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
