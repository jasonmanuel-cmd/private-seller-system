import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ConfigTests(unittest.TestCase):
    def test_database_path_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'persistent.sqlite')
            env = dict(os.environ, DB_PATH=path)
            result = subprocess.run([sys.executable, '-c', 'from config import DB_PATH; print(DB_PATH)'], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.strip(), path)

    def test_intelligence_configuration_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, REPORT_DIR=tmp, RUN_INTERVAL_MINUTES='90',
                       OPPORTUNITY_THRESHOLD='82', WATCHLIST_THRESHOLD='58',
                       STALE_DATA_DAYS='45')
            code = ('from config import REPORT_DIR,RUN_INTERVAL_MINUTES,OPPORTUNITY_THRESHOLD,'
                    'WATCHLIST_THRESHOLD,STALE_DATA_DAYS; '
                    'print(REPORT_DIR,RUN_INTERVAL_MINUTES,OPPORTUNITY_THRESHOLD,'
                    'WATCHLIST_THRESHOLD,STALE_DATA_DAYS,sep="|")')
            result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.strip(), f'{tmp}|90|82|58|45')

    def test_invalid_numeric_configuration_fails_clearly(self):
        env = dict(os.environ, RUN_INTERVAL_MINUTES='zero')
        result = subprocess.run([sys.executable, '-c', 'import config'], cwd=ROOT, env=env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('RUN_INTERVAL_MINUTES must be an integer', result.stderr)

if __name__ == '__main__':
    unittest.main()
