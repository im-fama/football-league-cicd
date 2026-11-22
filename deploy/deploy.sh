#!/usr/bin/env bash
# Deploys the latest successful build from S3 to this server.
#
# GitHub Actions runs this over SSH after uploading a build:
#     sudo /opt/football/deploy.sh
#
# 1. Read builds/latest.txt in the S3 bucket to find the newest build
#    (the pipeline only writes it after tests, security checks and the build pass).
# 2. Download that zip from S3 and unpack it into /opt/football/releases/<version>.
# 3. Install the backend's Python packages and point /opt/football/current at it.
# 4. Copy the React build to /var/www/football (served by Nginx).
# 5. Restart the Flask API and wait until /api/health reports the new version.
set -euo pipefail

# shellcheck source=/dev/null
. /etc/football/deploy.env          # S3_BUCKET, AWS_REGION
export AWS_DEFAULT_REGION="$AWS_REGION"
APP_DIR=/opt/football
WEB_DIR=/var/www/football

KEY="$(aws s3 cp "s3://$S3_BUCKET/builds/latest.txt" - | tr -d '[:space:]')"
FILE="$(basename "$KEY")"            # e.g. build-v1.0.12.zip
VERSION="${FILE#build-v}"
VERSION="${VERSION%.zip}"            # e.g. 1.0.12
echo "Latest successful build in S3: s3://$S3_BUCKET/$KEY (version $VERSION)"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
aws s3 cp --no-progress "s3://$S3_BUCKET/$KEY" "$TMP/$FILE"

RELEASE="$APP_DIR/releases/$VERSION"
rm -rf "$RELEASE"
mkdir -p "$RELEASE"
unzip -q "$TMP/$FILE" -d "$RELEASE"
echo "Unpacked to $RELEASE"

"$APP_DIR/venv/bin/pip" install --quiet -r "$RELEASE/backend/requirements.txt"

ln -sfn "$RELEASE" "$APP_DIR/current"
find "$WEB_DIR" -mindepth 1 -delete
cp -r "$RELEASE/frontend/." "$WEB_DIR/"
echo "Frontend copied to $WEB_DIR"

systemctl restart football-api
echo "Restarted football-api; waiting for /api/health to report version $VERSION ..."
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:5000/api/health 2>/dev/null \
      | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('version')=='$VERSION' and d.get('database')=='ok' else 1)"; then
    echo "Deployed version $VERSION - API and database are healthy."
    install -m 755 "$RELEASE/deploy/deploy.sh" "$APP_DIR/deploy.sh"   # keep this script up to date
    ls -1dt "$APP_DIR"/releases/* | tail -n +4 | xargs -r rm -rf          # keep the 3 newest releases
    exit 0
  fi
  sleep 2
done

echo "ERROR: version $VERSION did not become healthy. Recent API logs:" >&2
journalctl -u football-api -n 40 --no-pager >&2 || true
exit 1
