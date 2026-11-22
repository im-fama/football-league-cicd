#!/usr/bin/env bash
# One-time setup of the production server (Ubuntu 24.04 on AWS EC2).
#
# Run it ONCE on the EC2 instance, from a clone of this repository:
#     sudo bash deploy/setup_server.sh <s3-bucket-name> <aws-region>
#   e.g.
#     sudo bash deploy/setup_server.sh football-league-builds-29294 ap-south-1
#
# It installs MySQL, Nginx, Python and the AWS CLI, creates the database and
# loads the football dataset, and prepares the folders, the Flask (gunicorn)
# service and the deploy script that GitHub Actions runs on every push.
# It is safe to run again: existing passwords and data are kept
# (set RELOAD_DB=1 to wipe and reload the database).
set -euo pipefail

BUCKET="${1:?Usage: sudo bash deploy/setup_server.sh <s3-bucket-name> <aws-region>}"
REGION="${2:?Usage: sudo bash deploy/setup_server.sh <s3-bucket-name> <aws-region>}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR=/opt/football
WEB_DIR=/var/www/football
CONF_DIR=/etc/football

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo bash deploy/setup_server.sh $*" >&2
  exit 1
fi

step() { echo; echo "=== $* ==="; }

step "1/8 Adding 1 GB swap (the small instance has only 1 GB of memory)"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
free -h | head -2

step "2/8 Installing Nginx, MySQL, Python and the AWS CLI"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y nginx mysql-server python3-venv python3-pip unzip curl openssl
if ! command -v aws >/dev/null 2>&1; then
  snap install aws-cli --classic
fi
aws --version

step "3/8 Creating the database and its user"
mkdir -p "$CONF_DIR"
chmod 750 "$CONF_DIR"
if [ ! -f "$CONF_DIR/football.env" ]; then
  cat > "$CONF_DIR/football.env" <<EOF
DB_HOST=127.0.0.1
DB_NAME=dbsproject
DB_USER=football
DB_PASSWORD=$(openssl rand -hex 16)
SECRET_KEY=$(openssl rand -hex 32)
EOF
  chmod 640 "$CONF_DIR/football.env"
fi
set -a; . "$CONF_DIR/football.env"; set +a
systemctl enable --now mysql
mysql <<SQL
CREATE DATABASE IF NOT EXISTS dbsproject CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS 'football'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
CREATE USER IF NOT EXISTS 'football'@'127.0.0.1' IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER 'football'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER 'football'@'127.0.0.1' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON dbsproject.* TO 'football'@'localhost';
GRANT ALL PRIVILEGES ON dbsproject.* TO 'football'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL

step "4/8 Creating the Python environment"
mkdir -p "$APP_DIR/releases"
[ -d "$APP_DIR/venv" ] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$REPO_DIR/backend/requirements.txt"

step "5/8 Loading the football database (first run only)"
TABLES=$(mysql -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='dbsproject'")
if [ "$TABLES" -eq 0 ] || [ "${RELOAD_DB:-0}" = "1" ]; then
  # Order matters: tables, then data, then views, then procedures/triggers
  # (so the standings triggers don't fire while historic scores are loaded).
  mysql dbsproject < "$REPO_DIR/database/schema.sql"
  "$APP_DIR/venv/bin/python" "$REPO_DIR/database/load_data/seed_database.py"
  mysql dbsproject < "$REPO_DIR/database/views.sql"
  mysql dbsproject < "$REPO_DIR/database/procedures_triggers.sql"
else
  echo "Database already has $TABLES tables - keeping it (use RELOAD_DB=1 to reload)."
fi
mysql -N -e "SELECT CONCAT('teams: ', COUNT(*)) FROM dbsproject.teams; SELECT CONCAT('matches: ', COUNT(*)) FROM dbsproject.matches;"

step "6/8 Installing the deploy script"
cat > "$CONF_DIR/deploy.env" <<EOF
S3_BUCKET=$BUCKET
AWS_REGION=$REGION
EOF
install -m 755 "$REPO_DIR/deploy/deploy.sh" "$APP_DIR/deploy.sh"

step "7/8 Installing the Flask API service (gunicorn)"
install -m 644 "$REPO_DIR/deploy/football-api.service" /etc/systemd/system/football-api.service
systemctl daemon-reload
systemctl enable football-api   # started by the first deployment

step "8/8 Configuring Nginx"
mkdir -p "$WEB_DIR"
if [ ! -f "$WEB_DIR/index.html" ]; then
  echo '<h1>Server ready - waiting for the first deployment from GitHub Actions</h1>' > "$WEB_DIR/index.html"
fi
install -m 644 "$REPO_DIR/deploy/nginx-football.conf" /etc/nginx/sites-available/football
ln -sf /etc/nginx/sites-available/football /etc/nginx/sites-enabled/football
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

step "Checking that this server can read the S3 bucket (IAM role)"
if aws s3 ls "s3://$BUCKET" --region "$REGION" >/dev/null; then
  echo "OK - the server can read s3://$BUCKET"
else
  echo "WARNING - cannot read s3://$BUCKET. Attach the IAM role to this instance (guide step 4) and run this script again."
fi

echo
echo "Setup complete. Push a commit to GitHub to run the pipeline and deploy the app."
