# Deploying HuntOps to a Hostinger VPS

## Read this first: Cloud Hosting will not run this app

Hostinger sells two things people call "cloud". They are not interchangeable here.

| | Hostinger **Cloud Hosting** (Cloud Startup / Professional / Enterprise) | Hostinger **VPS** (KVM 1–8) |
|---|---|---|
| Python / FastAPI | **No** — Python is VPS-only | Yes |
| PostgreSQL | **No** — MySQL only | Yes |
| Root / SSH | No | Yes |
| Docker | No | Yes |

HuntOps is a Python (FastAPI) application on PostgreSQL with a background
scheduler. **Hostinger Cloud Hosting cannot run it** — that is a hard platform
limit, not a configuration problem. Cloud Hosting is a managed PHP/MySQL
product; it supports Node.js on some plans, but not Python, and not Postgres.

Deploy to a **Hostinger VPS**. KVM 2 (2 vCPU / 8 GB) is the sensible starting
point: this stack runs six containers, one of which is Postgres. KVM 1
(1 vCPU / 4 GB) will work for a low-traffic launch but leaves little headroom
for the AI-calling endpoints.

Porting to Cloud Hosting is not a small change — it would mean rewriting the
backend in PHP and migrating Postgres to MySQL. Take the VPS.

## What you need before you start

- A Hostinger VPS with Ubuntu 22.04 or 24.04
- A domain with an **A record already pointing at the VPS IP** (Caddy requests
  the TLS certificate on first boot; if DNS doesn't resolve yet, that fails)
- API keys as needed: Anthropic (required for all AI features), Stripe,
  Google OAuth (Gmail bridge), Apollo (outreach), SMTP (digest email)

## 1. Prepare the server

SSH in as root, then:

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh          # Docker + Compose plugin
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
```

Postgres is deliberately **not** published to the host in the production
compose file, so it is unreachable from the internet — do not open 5432.

## 2. Get the code and configure

```bash
git clone https://github.com/lilyfrancis/huntops.git /opt/huntops
cd /opt/huntops

cp .env.prod.example .env              # compose-level: domain + DB credentials
cp backend/.env.example backend/.env   # application settings
```

Generate real secrets — do not hand-invent them:

```bash
openssl rand -base64 32                                             # POSTGRES_PASSWORD
openssl rand -hex 32                                                # JWT_SECRET
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # TOKEN_ENCRYPTION_KEY
```

Edit `.env`:

```
DOMAIN=huntops.yourdomain.com
TLS_EMAIL=you@yourdomain.com
POSTGRES_USER=huntops
POSTGRES_PASSWORD=<generated>
POSTGRES_DB=huntops
```

Edit `backend/.env` — these **must** change from the defaults:

| Key | Value |
|---|---|
| `ENVIRONMENT` | `production` (startup validation refuses weak secrets here) |
| `JWT_SECRET` | the generated hex string |
| `TOKEN_ENCRYPTION_KEY` | the generated Fernet key — **losing this orphans every stored Gmail token** |
| `CORS_ORIGINS` | `https://huntops.yourdomain.com` (never `*` in production) |
| `FRONTEND_URL` | `https://huntops.yourdomain.com` — the Gmail OAuth callback redirects here |
| `GOOGLE_OAUTH_REDIRECT_URI` | `https://huntops.yourdomain.com/api/integrations/gmail/callback`, and register this exact URI in Google Cloud Console |
| `ANTHROPIC_API_KEY` | required — every AI feature fails without it |
| `STRIPE_*` | live keys + the webhook secret |

`DATABASE_URL` is set by compose from your Postgres credentials — leave it
alone in `backend/.env`.

## 3. Launch

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

On first boot: the DB starts, the `migrate` container runs `alembic upgrade
head` and exits, then the API, scheduler, frontend, and Caddy come up. Caddy
obtains the certificate automatically. Give it a minute, then visit
`https://huntops.yourdomain.com`.

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
```

## 4. Create the first admin

Admin accounts cannot be self-registered (deliberately). Register normally
through the UI, then promote:

```bash
docker compose -f docker-compose.prod.yml exec api python -c "
from app.db.base import SessionLocal
from app.models.user import User
from app.models.enums import UserRole
s = SessionLocal()
u = s.query(User).filter(User.email == 'you@yourdomain.com').first()
u.role = UserRole.admin
s.commit()
print('promoted', u.email)
"
```

## 5. Stripe webhook

Point a Stripe webhook at `https://huntops.yourdomain.com/api/billing/webhook`
and put its signing secret in `STRIPE_WEBHOOK_SECRET`. The webhook is the
**only** thing that can change a user's tier — without it, paid subscriptions
never activate.

## Updating

```bash
cd /opt/huntops && git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations run automatically before the new API starts.

## Backups

The database is the only irreplaceable state. Set up a nightly dump:

```bash
# /etc/cron.daily/huntops-backup  (chmod +x)
#!/bin/bash
cd /opt/huntops
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U huntops huntops | gzip > /root/backups/huntops-$(date +%F).sql.gz
find /root/backups -name 'huntops-*.sql.gz' -mtime +14 -delete
```

Copy those off the VPS — a backup that only exists on the machine it protects
is not a backup.

## Migrations are verified against real PostgreSQL

The full chain (0001–0009) has been run against a real PostgreSQL 16, and the
resulting schema diffed against the SQLAlchemy models — they match exactly. The
app was then booted against that database and exercised through registration,
login, and authenticated reads with no errors.

This found two genuine bugs that SQLite testing could never have caught, both
now fixed: migrations 0001/0002/0004 created their enum types twice and failed
outright on a fresh Postgres, and three tables carried a unique constraint
duplicating a unique index.

## Notes on how this is wired

- **One origin.** Caddy serves the frontend and proxies `/api` to the backend
  on the same hostname, so there is no cross-site request and no CORS surface.
- **The scheduler runs in exactly one container.** The API runs three gunicorn
  workers with `RUN_SCHEDULER=false`; a separate single-worker `scheduler`
  service owns the cron jobs. If the API had the scheduler on, every worker
  would run every job — three aggregation runs and three digests per user, per
  day. **Do not `scale` the scheduler service.**
- **Migrations gate the API.** The API waits for the migration container to
  finish successfully, so a release never serves traffic against a schema it
  doesn't match.

## Known gaps before you trust this with real users

- **No CI**, and no committed end-to-end test suite — browser verification so
  far has been ad-hoc.
- **Stripe, Anthropic, Apollo, and Gmail have only ever run against mocks.**
  Exercise each once in staging with real keys before launch.
