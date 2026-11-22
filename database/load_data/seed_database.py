"""Load the CSV dataset into MySQL (used once when setting up the server).

This replaces the manual steps in load_data.py (which needed code to be
uncommented by hand). It only uses the Python standard library plus
mysql-connector-python, and reads the connection settings from environment
variables, the same ones the Flask app uses:

    DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

Run it after schema.sql and BEFORE procedures_triggers.sql, so the standings
triggers don't fire while historic scores are being inserted.
"""
import ast
import csv
import json
import os
from pathlib import Path

import mysql.connector

DATA_DIR = Path(__file__).resolve().parent


def text(value):
    """Empty CSV cells become NULL; everything else is trimmed text."""
    value = (value or '').strip()
    return value or None


def number(value):
    """Numbers may be written as '1898.0' in the CSV; store them as integers."""
    value = text(value)
    return None if value is None else int(float(value))


def form_json(value):
    """Standings form is stored like "['D', 'W']"; MySQL wants JSON: ["D", "W"]."""
    value = text(value)
    return None if value is None else json.dumps(ast.literal_eval(value))


# table name -> (columns, how to convert each column)
TABLES = [
    ('countries', ['country_id', 'name', 'flag_url'], [number, text, text]),
    ('leagues', ['league_id', 'name', 'country', 'country_id', 'icon_url', 'cl_spot', 'uel_spot', 'relegation_spot'],
     [number, text, text, number, text, number, number, number]),
    ('stadiums', ['stadium_id', 'name', 'location', 'capacity'], [number, text, text, number]),
    ('coaches', ['coach_id', 'name', 'team_id', 'nationality'], [number, text, number, text]),
    ('referees', ['referee_id', 'name', 'nationality'], [number, text, text]),
    ('seasons', ['season_id', 'league_id', 'year'], [number, number, text]),  # year is text, e.g. '2023-2024'
    ('teams', ['team_id', 'name', 'founded_year', 'stadium_id', 'league_id', 'coach_id', 'cresturl'],
     [number, text, number, number, number, number, text]),
    ('players', ['player_id', 'team_id', 'name', 'position', 'date_of_birth', 'nationality'],
     [number, number, text, text, text, text]),
    ('matches', ['match_id', 'season_id', 'league_id', 'matchday', 'home_team_id', 'away_team_id', 'winner', 'utc_date'],
     [number, number, number, number, number, number, text, text]),
    ('scores', ['score_id', 'match_id', 'full_time_home', 'full_time_away', 'half_time_home', 'half_time_away'],
     [number] * 6),
    ('standings', ['standing_id', 'season_id', 'league_id', 'position', 'team_id', 'played_games', 'won', 'draw',
                   'lost', 'points', 'goals_for', 'goals_against', 'goal_difference', 'form'],
     [number] * 13 + [form_json]),
    ('scorers', ['scorer_id', 'player_id', 'season_id', 'league_id', 'goals', 'assists', 'penalties'], [number] * 7),
    ('match_referees', ['match_id', 'referee_id'], [number, number]),
]

# The frontend sends "X-User-Id: 1" for admin pages (there is no login screen
# yet), so user 1 must exist and be an admin. The password is a placeholder
# because the app has no login; it is never used.
USERS = [
    (1, 'admin', '!no-login', 'admin@football-league.local', 1),
    (2, 'fan', '!no-login', 'fan@football-league.local', 0),
]


def load_table(cursor, table, columns, converters):
    with open(DATA_DIR / f'{table}.csv', newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    values = []
    for row in rows:
        if table == 'coaches' and text(row['name']) is None:
            continue  # same rule as the original loader: skip coaches without a name
        values.append(tuple(convert(row[col]) for col, convert in zip(columns, converters)))

    column_sql = ', '.join(f'`{c}`' for c in columns)
    placeholders = ', '.join(['%s'] * len(columns))
    cursor.execute(f'DELETE FROM `{table}`')  # nosec B608 - table names come from the fixed list above
    cursor.executemany(f'INSERT INTO `{table}` ({column_sql}) VALUES ({placeholders})', values)  # nosec B608
    print(f'  {table:<15} {len(values):>5} rows')


def main():
    conn = mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'dbsproject'),
        user=os.environ.get('DB_USER', 'root'),
        password=os.environ.get('DB_PASSWORD', ''),
    )
    cursor = conn.cursor()
    cursor.execute('SET FOREIGN_KEY_CHECKS = 0')
    try:
        print('Loading CSV data:')
        for table, columns, converters in TABLES:
            load_table(cursor, table, columns, converters)

        cursor.execute('DELETE FROM users')
        cursor.executemany(
            'INSERT INTO users (user_id, username, password, email, is_admin) VALUES (%s, %s, %s, %s, %s)',
            USERS)
        print(f'  {"users":<15} {len(USERS):>5} rows (user 1 = admin)')
        conn.commit()
    finally:
        cursor.execute('SET FOREIGN_KEY_CHECKS = 1')
        cursor.close()
        conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
