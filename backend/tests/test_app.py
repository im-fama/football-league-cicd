"""Tests for the app itself: the root endpoint, the health check and error handling."""
import mysql.connector

from tests.base import AppTestCase, app_module


class TestApp(AppTestCase):

    def test_root_returns_api_information(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body['message'], 'Football League Management System API')
        self.assertEqual(body['version'], app_module.APP_VERSION)

    def test_health_is_ok_when_database_answers(self):
        response = self.client.get('/api/health')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            'status': 'ok',
            'version': app_module.APP_VERSION,
            'database': 'ok',
        })
        self.cursor.execute.assert_called_once_with('SELECT 1')

    def test_health_reports_database_failure(self):
        self.get_db_connection.side_effect = mysql.connector.Error('database is down')

        response = self.client.get('/api/health')

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['database'], 'error')

    def test_unknown_endpoint_returns_json_404(self):
        response = self.client.get('/api/does-not-exist')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {'error': 'Endpoint not found'})
