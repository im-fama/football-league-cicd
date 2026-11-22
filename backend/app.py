import os
from pathlib import Path

from user_routes import user_bp
from admin_routes import admin_bp
from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
import mysql.connector
from mysql.connector import pooling


def _read_version():
    """Version shown by /api/health.

    The CI/CD pipeline writes a VERSION file next to this file when it builds
    the release (e.g. "1.0.12"). Locally there is no such file, so "dev" is used.
    """
    version_file = Path(__file__).resolve().parent / 'VERSION'
    if version_file.exists():
        return version_file.read_text().strip()
    return os.environ.get('APP_VERSION', 'dev')


APP_VERSION = _read_version()

app = Flask(__name__)
app.config.from_object(Config)
# CORS(app, supports_credentials=True)
CORS(app)

# Database connection pool
db_pool = pooling.MySQLConnectionPool(
    pool_name="football_pool",
    pool_size=5,
    pool_reset_session=True,
    host=app.config['DB_HOST'],
    database=app.config['DB_NAME'],
    user=app.config['DB_USER'],
    password=app.config['DB_PASSWORD']
)


def get_db_connection():
    """Get a connection from the pool"""
    return db_pool.get_connection()


# Import routes

# Register blueprints
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(user_bp, url_prefix='/api')


@app.route('/')
def index():
    return jsonify({
        'message': 'Football League Management System API',
        'version': APP_VERSION,
        'endpoints': {
            'admin': '/api/admin',
            'user': '/api'
        }
    })


@app.route('/api/health')
def health():
    """Used by the pipeline's Verify step and by the frontend's status check."""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            cursor.fetchone()
            cursor.close()
        finally:
            conn.close()
        database = 'ok'
    except mysql.connector.Error:
        database = 'error'

    status_code = 200 if database == 'ok' else 503
    return jsonify({
        'status': 'ok' if database == 'ok' else 'degraded',
        'version': APP_VERSION,
        'database': database,
    }), status_code


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # Local development only. In production the app runs under gunicorn, and
    # debug mode stays off unless FLASK_DEBUG=1 is set (flagged by Bandit B201).
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', host='127.0.0.1', port=5000)
