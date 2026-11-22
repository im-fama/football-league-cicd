"""Tests for the public (user) API routes."""
import mysql.connector

from tests.base import AppTestCase


class TestTeams(AppTestCase):

    def test_get_teams_returns_teams_and_count(self):
        self.cursor.fetchall.return_value = [
            {'team_id': 1, 'team_name': 'Arsenal'},
            {'team_id': 2, 'team_name': 'Barcelona'},
        ]

        response = self.client.get('/api/teams')

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body['count'], 2)
        self.assertEqual(body['teams'][0]['team_name'], 'Arsenal')

    def test_get_teams_filters_by_league(self):
        self.cursor.fetchall.return_value = []

        response = self.client.get('/api/teams?league_id=3')

        self.assertEqual(response.status_code, 200)
        query, params = self.cursor.execute.call_args.args
        self.assertIn('WHERE league_id = %s', query)
        self.assertEqual(params, [3])

    def test_get_teams_returns_500_on_database_error(self):
        self.cursor.execute.side_effect = mysql.connector.Error('table missing')

        response = self.client.get('/api/teams')

        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.get_json())

    def test_connection_is_always_returned_to_pool(self):
        self.cursor.fetchall.return_value = []

        self.client.get('/api/teams')

        self.cursor.close.assert_called_once()
        self.conn.close.assert_called_once()


class TestStandings(AppTestCase):

    def test_standings_require_league_id(self):
        response = self.client.get('/api/standings')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {'error': 'league_id is required'})
