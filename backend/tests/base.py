"""Shared set-up for the unit tests.

The real app opens a MySQL connection pool as soon as it is imported. Unit tests
must run anywhere (including GitHub Actions, which has no database), so the pool
is replaced with a mock before the app is imported, and every test gets a fake
connection and cursor whose return values it controls.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Replace the connection pool before app.py runs, so no database is needed.
_pool_patcher = patch('mysql.connector.pooling.MySQLConnectionPool')
_pool_patcher.start()

import app as app_module  # noqa: E402  (must come after the patch above)


class AppTestCase(unittest.TestCase):
    """Gives each test a Flask test client and a mocked database cursor."""

    def setUp(self):
        self.client = app_module.app.test_client()

        self.cursor = MagicMock(name='cursor')
        self.conn = MagicMock(name='connection')
        self.conn.cursor.return_value = self.cursor

        # Routes call app.get_db_connection(); hand them the fake connection.
        db_patcher = patch.object(app_module, 'get_db_connection', return_value=self.conn)
        self.get_db_connection = db_patcher.start()
        self.addCleanup(db_patcher.stop)
