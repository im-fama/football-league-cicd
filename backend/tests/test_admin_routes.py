"""Tests for the admin API routes and the admin check."""
from tests.base import AppTestCase


class TestAdminAccess(AppTestCase):

    def test_request_without_user_header_is_rejected(self):
        response = self.client.get('/api/admin/users')

        self.assertEqual(response.status_code, 401)
        self.get_db_connection.assert_not_called()

    def test_non_admin_user_is_forbidden(self):
        self.cursor.fetchone.return_value = {'is_admin': 0}

        response = self.client.get('/api/admin/users', headers={'X-User-Id': '7'})

        self.assertEqual(response.status_code, 403)

    def test_admin_user_can_list_users(self):
        self.cursor.fetchone.return_value = {'is_admin': 1}
        self.cursor.fetchall.return_value = [
            {'user_id': 1, 'username': 'admin', 'email': 'admin@example.com', 'is_admin': 1},
        ]

        response = self.client.get('/api/admin/users', headers={'X-User-Id': '1'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['users'][0]['username'], 'admin')


class TestMatchScore(AppTestCase):

    def setUp(self):
        super().setUp()
        self.cursor.fetchone.return_value = {'is_admin': 1}
        self.admin = {'X-User-Id': '1'}

    def test_score_update_calls_stored_procedure(self):
        response = self.client.put(
            '/api/admin/matches/42/score',
            json={'full_time_home': 2, 'full_time_away': 1},
            headers=self.admin,
        )

        self.assertEqual(response.status_code, 200)
        self.cursor.callproc.assert_called_once_with('sp_update_match_score', (42, 2, 1, 0, 0))
        self.conn.commit.assert_called_once()

    def test_score_update_rejects_missing_fields(self):
        response = self.client.put(
            '/api/admin/matches/42/score',
            json={'full_time_home': 2},
            headers=self.admin,
        )

        self.assertEqual(response.status_code, 400)
        self.cursor.callproc.assert_not_called()
