# Football League Management System — CI/CD on AWS

![CI/CD Pipeline](../../actions/workflows/ci-cd.yml/badge.svg)

A 3-tier web application (React → Flask REST API → MySQL) for browsing and managing the top five European football leagues, deployed automatically to AWS with GitHub Actions.

**DevOps Assignment 2 — Fatima Irfan (ERP 29294)**

## CI/CD pipeline

Every push to `main` runs [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml):

| Stage | What happens |
| --- | --- |
| 1. Unit tests | `pytest` runs the backend tests in `backend/tests`. Any failure stops the pipeline. |
| 2. Security scan | Gitleaks (secret scanning), Bandit (static code analysis), pip-audit and npm audit (dependency vulnerabilities). |
| 3. Build | Builds the React frontend and packages it with the Flask backend as `build-v1.0.<run>.zip`. |
| 4. Upload to S3 | Uploads the zip to `s3://<bucket>/builds/` and marks it as the latest build. |
| 5. Deploy | Connects to the EC2 server, which downloads the latest build from S3 and installs it. |
| 6. Verify | Calls the live `/api/health` endpoint and checks it reports the new version. |

```
Code change → git push → Unit tests + Security scan → Build → S3 → EC2 → Live app
```

## Production setup (AWS)

- **EC2** (Ubuntu 24.04): Nginx serves the React build and forwards `/api` to Flask (gunicorn); MySQL holds the data.
- **S3**: stores every build zip; `builds/latest.txt` points at the newest successful build.
- **IAM**: GitHub Actions can only upload to the bucket; the EC2 server can only read from it.

One-time server setup: `sudo bash deploy/setup_server.sh <bucket> <region>` (see `deploy/`).

## Run locally

See [SETUP.md](SETUP.md). Run the backend tests with:

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest -v
```
