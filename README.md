# Medicaid Eligibility Import — medicaid-v4

Internal web application for batch Medicaid eligibility checking via eMedNY CORE Web Services.

## Architecture

- **Django 5** + **PostgreSQL** — web framework and primary database  
- **Celery** + **Redis** — background row processing (import continues even if browser closes)  
- **Server-Sent Events** — real-time progress stream to the browser  
- **Tailwind CSS** (CDN) + **HTMX** — lightweight frontend  
- **Gunicorn** + **Nginx** — production deployment  
- **No Docker required**

## Quick Start (Development)

### Prerequisites

- Python 3.12+
- PostgreSQL 14+
- Redis 7+

### 1. PostgreSQL Setup

```bash
psql -U postgres
CREATE DATABASE medicaid_eligibility;
CREATE USER medicaideligibility WITH PASSWORD 'meidicaideligibility';
GRANT ALL PRIVILEGES ON DATABASE medicaid_eligibility TO medicaid;
\q
```

### 2. Redis (macOS)

```bash
brew install redis
brew services start redis
```

### 3. Redis (Ubuntu/Debian)

```bash
sudo apt install redis-server
sudo systemctl enable --now redis-server
```

### 4. Python Environment

```bash
cd medicaid-v4
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

### 5. Environment Variables

```bash
cp .env.example .env
# Edit .env with your credentials
```

Key variables to set:
- `DJANGO_SECRET_KEY` — long random string
- `DB_PASSWORD` — PostgreSQL password
- `EMEDNY_USERNAME`, `EMEDNY_PASSWORD`, `EMEDNY_ETIN`, `EMEDNY_PROVIDER_ID` — eMedNY credentials
- `EMEDNY_MOCK_MODE=True` — use mock client during development/testing

### 6. Run Migrations

```bash
python manage.py migrate
python manage.py createsuperuser  # optional
python manage.py collectstatic --noinput
```

### 7. Start the Application

**Terminal 1 — Django dev server:**
```bash
python manage.py runserver
```

**Terminal 2 — Celery worker:**
```bash
celery -A config worker -l info --concurrency=4
```

Open http://127.0.0.1:8000 — the default page is the Import Eligibility screen.

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use SQLite in-memory and the mock eMedNY client. No live credentials needed.

---

## Production Deployment

### System Setup (Ubuntu 22.04)

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv python3-pip \
  postgresql postgresql-contrib redis-server nginx
```

### Application User and Directory

```bash
sudo useradd -m -s /bin/bash medicaid
sudo mkdir -p /var/www/medicaid /var/log/medicaid
sudo chown medicaid:medicaid /var/www/medicaid /var/log/medicaid
sudo -u medicaid git clone <repo> /var/www/medicaid/app
cd /var/www/medicaid/app
sudo -u medicaid python3.12 -m venv venv
sudo -u medicaid venv/bin/pip install -r requirements.txt
sudo -u medicaid cp .env.example .env
# Edit /var/www/medicaid/app/.env with production values
```

### Gunicorn systemd Service

Create `/etc/systemd/system/medicaid.service`:

```ini
[Unit]
Description=Medicaid Eligibility Gunicorn
After=network.target postgresql.service redis.service

[Service]
User=medicaid
Group=medicaid
WorkingDirectory=/var/www/medicaid/app
EnvironmentFile=/var/www/medicaid/app/.env
ExecStart=/var/www/medicaid/app/venv/bin/gunicorn \
    --workers 4 \
    --bind unix:/run/medicaid.sock \
    --access-logfile /var/log/medicaid/access.log \
    --error-logfile /var/log/medicaid/error.log \
    config.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

### Celery systemd Service

Create `/etc/systemd/system/medicaid-celery.service`:

```ini
[Unit]
Description=Medicaid Eligibility Celery Worker
After=network.target redis.service

[Service]
User=medicaid
Group=medicaid
WorkingDirectory=/var/www/medicaid/app
EnvironmentFile=/var/www/medicaid/app/.env
ExecStart=/var/www/medicaid/app/venv/bin/celery \
    -A config worker \
    --loglevel=info \
    --concurrency=4 \
    --logfile=/var/log/medicaid/celery.log
Restart=always

[Install]
WantedBy=multi-user.target
```

### Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now medicaid medicaid-celery
```

### Nginx Configuration

Create `/etc/nginx/sites-available/medicaid`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    client_max_body_size 15M;

    # SSE — disable buffering for Server-Sent Events
    location /progress/ {
        proxy_pass http://unix:/run/medicaid.sock;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header X-Accel-Buffering no;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }

    location /static/ {
        alias /var/www/medicaid/static/;
        expires 30d;
    }

    location / {
        proxy_pass http://unix:/run/medicaid.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/medicaid /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Database Backups

```bash
# Add to crontab (as postgres user)
0 2 * * * pg_dump medicaid_eligibility | gzip > /var/backups/medicaid_$(date +\%Y\%m\%d).sql.gz
find /var/backups -name 'medicaid_*.sql.gz' -mtime +30 -delete
```

### Log Rotation

Create `/etc/logrotate.d/medicaid`:

```
/var/log/medicaid/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    sharedscripts
    postrotate
        systemctl reload medicaid medicaid-celery
    endscript
}
```

---

## Mock eMedNY Client

Set `EMEDNY_MOCK_MODE=True` in `.env` to use the mock client during development. The mock returns realistic 271 responses based on CIN prefixes:

| CIN prefix | Response |
|---|---|
| `ERR` | Technical failure |
| `NF` | Member not found |
| `REJ` | Business rejection (AAA) |
| `NHTD` | Eligible + NHTD indicator |
| `C60` | Eligible + Code 60 |
| `SURP` | Eligible + Surplus $215.00 |
| `REC` | Eligible + Recertification |
| anything else | Eligible + Recertification |

---

## Application Structure

```
config/         Django settings, Celery, URLs
imports/        CSV upload, ImportBatch, ImportRow, Celery tasks, SSE progress
patients/       Patient, PatientChangeHistory, PatientDataConflict
eligibility/    EligibilityRequest/Response/Snapshot/Indicator/Financial/Benefit
emedny/         X12 270 builder, CORE SOAP client, X12 271 parser, classifier, mock
templates/      Django HTML templates (Tailwind CSS)
static/         CSS, JS
tests/          pytest test suite + anonymised 271 fixtures
```

## Security Notes

- PHI is never logged
- eMedNY credentials are environment-variable only
- Raw X12 responses are HTML-escaped before display
- CSV formula injection protection is applied to all inputs and exports
- CIN is treated as sensitive data throughout
- All Django CSRF, XSS, and clickjacking protections are enabled
