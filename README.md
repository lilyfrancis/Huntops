# HuntOps

The job search copilot that finds real openings, scores your fit for where you
actually live, and emails the recruiter for you.

This repo is being built in phases against the 7-phase product blueprint
(Foundation → Real supply → Fit intelligence → Email-alert bridge →
Autopilot Outreach → Reach & retention → Premium coaching). **Phase 1 —
Foundation** is complete: auth, roles, job/application CRUD, and real
Stripe billing on Postgres.

## What's in Phase 1

- **Auth**: register/login/refresh with short-lived JWT access tokens (30 min)
  + longer-lived refresh tokens (30 days), bcrypt password hashing, per-IP
  rate limiting on login/register.
- **Roles**: `job_seeker`, `employer`, `admin` — enforced server-side on every
  route. Admin accounts cannot be self-registered.
- **Jobs**: employer-posted listings go through `pending → active/rejected`
  admin moderation. Public feed shows only `active` jobs, featured first.
- **Applications**: one application per candidate/job pair, employer-side
  status pipeline, applicant list scoped to the owning employer only.
- **Credits & billing**: every user has a cached `ai_credits` balance backed
  by an immutable ledger. Stripe Checkout creates real subscriptions (Free /
  Pro / Elite); a webhook — not a self-serve endpoint — is the only thing
  that can change a user's tier. This deliberately replaces the prior
  prototype's `/users/upgrade` endpoint, which let anyone grant themselves
  premium credits for free.
- **Ops basics**: `/health` for liveness, `/api/health/detailed` (admin-only)
  for DB + Stripe config checks, startup validation that fails fast on unsafe
  config in production.

## Deliberately not in Phase 1

Résumé parsing, AI job matching/screening, the real job-aggregation and
email-alert pipelines, and every "wow" feature (autopilot outreach, warm
intros, ghost-job detection, etc.) — those are Phases 2 onward. Phase 1 is
the foundation everything else attaches to: a correct data model, real auth,
and real billing.

## Project layout

```
backend/
  app/
    core/       settings, JWT/password security, rate limiter
    db/         SQLAlchemy engine/session
    models/     User, Job, Application, CreditLedgerEntry
    schemas/    Pydantic request/response models
    routers/    auth, users, jobs, applications, billing, admin, health
    services/   credits ledger, Stripe billing
  alembic/      migrations (0001_initial creates the full schema)
  tests/        pytest suite (sqlite in-memory, no external services needed)
docker-compose.yml   Postgres + API for local dev
```

## Running locally

**Option A — Docker (recommended):**

```bash
cp backend/.env.example backend/.env
# edit backend/.env: set JWT_SECRET, Stripe test keys if you want billing to work
docker compose up --build
```

API is at `http://localhost:8000`. Run migrations once the DB is up:

```bash
docker compose exec api alembic upgrade head
```

**Option B — Local Python:**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # point DATABASE_URL at a Postgres you have running
alembic upgrade head
uvicorn app.main:app --reload
```

## Tests

No external services required — the suite runs against an in-memory SQLite
DB with Stripe calls mocked:

```bash
cd backend
pytest -v
```

## Stripe setup

1. Create two recurring Prices in the Stripe Dashboard (test mode) for Pro
   and Elite — copy their `price_...` IDs into `STRIPE_PRICE_PRO` /
   `STRIPE_PRICE_ELITE`.
2. Add a webhook endpoint pointing at `/api/billing/webhook` listening for
   `checkout.session.completed`, `customer.subscription.updated`, and
   `customer.subscription.deleted`; copy the signing secret into
   `STRIPE_WEBHOOK_SECRET`.
3. `POST /api/billing/checkout-session {"tier": "pro"}` (authenticated)
   returns a Checkout URL; `GET /api/billing/portal` returns a self-serve
   billing portal URL for plan changes/cancellation.

## What's next (Phase 2)

Real job aggregation (6 live sources ported from the Job Engine spec),
résumé parsing, and geo-aware fit scoring — see the blueprint for the full
7-phase roadmap through Autopilot Outreach and beyond.
