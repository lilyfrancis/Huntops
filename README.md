# HuntOps

The job search copilot that finds real openings, scores your fit for where you
actually live, and emails the recruiter for you.

This repo is being built in phases against the 7-phase product blueprint
(Foundation → Real supply → Fit intelligence → Email-alert bridge →
Autopilot Outreach → Reach & retention → Premium coaching).

**Phase 1 — Foundation**: auth, roles, job/application CRUD, real Stripe billing. ✅
**Phase 2 — Real supply & fit intelligence**: live job aggregation, résumé
parsing, geo-aware fit scoring. ✅
**Phase 3 — Email-alert bridge**: per-user Gmail OAuth, auto-provisioned
label + filters, AI extraction of jobs from alert emails. ✅
**Phase 4 — Autopilot Outreach**: Apollo recruiter discovery, AI-drafted
pitches, sending via the user's own Gmail. ✅ — the flagship feature.

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

## What's in Phase 2

- **Real job aggregation** from six live sources — Remotive, RemoteOK,
  Arbeitnow, Jobicy, We Work Remotely (RSS), and Adzuna (optional, needs an
  API key) — replacing the fake hardcoded fixture the prior prototype shipped
  with. Each source runs in its own try/except and gets its own
  `IngestionRun` audit row, so a dead or rate-limited source never takes
  down the whole run and is visible to admins instead of silently shrinking
  the feed. Runs daily via an in-process scheduler (07:00 UTC) or on demand
  via `POST /api/admin/jobs/aggregate`.
- **Broadened lane taxonomy**: Job Engine's original inference (tuned to one
  RevOps/GTM persona) dropped anything that didn't match. This version
  covers engineering/product/design/sales/etc. and files an unmatched job
  under `other` instead of discarding it — a general marketplace can't
  throw away most of its own supply.
- **Résumé parsing**: upload a PDF/DOCX/TXT résumé; Claude (Haiku tier)
  extracts structured skills, experience, education, and achievements.
- **Geo-aware fit scoring**: `GET /api/ai/match-jobs` scores a user's résumé
  against open roles and applies a configurable boost (`GEO_MATCH_BOOST`,
  default 15) when a job is remote with no detected restriction, or
  explicitly open to the user's `home_market`. Job Engine hardcoded this as
  a single "is this Nigeria-eligible" check for one person; here it's a
  per-user field so it works for any home market.
- **Per-user, not per-job, fit**: fit scores live in their own `job_matches`
  table keyed on `(user_id, job_id)` — re-scoring never touches the job
  itself, so the same listing can carry a different fit score for every
  candidate who views it.
- **Schema-validated AI responses**: every Claude reply is parsed into a
  Pydantic model (`ParsedResume`, `JobFitScore`) before it's trusted. The
  prior prototype did a bare `json.loads()` with no validation, so a
  malformed reply corrupted data instead of failing loudly.

## What's in Phase 3

- **Per-user Gmail OAuth**, not one shared mailbox. Job Engine's own spec was
  explicit that it only ever handled one hand-configured inbox with manually
  created Gmail filters — this is the multi-tenant version, sized honestly
  as the trickiest piece in the whole blueprint's rebuild plan.
- **Zero manual setup**: connecting an account programmatically creates the
  "HuntOps" Gmail label and routing filters for known job-alert senders
  (LinkedIn, Indeed, Glassdoor, Jobberman, MyJobMag, TheLadders) via the
  Gmail API — the user never touches Gmail's settings UI.
- **Encrypted tokens at rest**: refresh/access tokens are Fernet-encrypted
  before hitting the database, decrypted only in memory when a sync runs.
- **Same extraction + normalization pipeline as Phase 2**: emails are parsed
  by Claude into structured postings, then flow through the exact same
  `normalize_common` / lane-inference / geo-heuristic functions aggregation
  uses — the email bridge is just another source feeding one table.
- **LinkedIn's missing-URL problem, solved the way Job Engine solved it**:
  when an alert email has no direct job link, a provider-aware search-URL
  fallback is generated (and deduped on) instead of dropping the job.
- **Scoped audit logging**: `EmailSyncRun` records fetched/extracted/inserted
  counts and errors per sync, without exposing which user's inbox produced
  which job to anyone but that user.

## What's in Phase 4

- **Apollo recruiter discovery**, ported from Job Engine with both of its
  documented gotchas preserved: search results obfuscate the last name
  (e.g. "Li\*\*\*a"), so enrichment keys on the person's `id`, never the
  masked name; and the work email lands in `person.email`, not the usually-
  empty `personal_emails` array.
- **Per-job, not per-user, recruiter caching**: `RecruiterContact` is keyed
  on `job_id` alone. The second, third, and Nth user who reaches out to the
  same job reuses the cached contact instead of spending another Apollo
  reveal credit — the same instinct behind Phase 2's job dedup, applied to
  a paid third-party lookup this time.
- **Per-user AI drafting**, not a hardcoded persona: Job Engine's prompt had
  one candidate's résumé and voice baked in as constants. Here the draft is
  built from whichever user's résumé and optional `positioning_statement`
  requested it — same prompt structure, works for anyone.
- **Real send, not a copy-pasted draft**: on a recruiter email + a connected
  Gmail account, the pitch is sent from the user's own inbox via the Gmail
  API (new `gmail.send` scope) using the OAuth plumbing Phase 3 already
  built. No recruiter found, or no Gmail connected? The draft is still
  generated and returned — the user can send it manually.
- **Gated and metered honestly**: Elite-tier only, credit balance checked
  *before* any Apollo or Anthropic call fires, so a user who can't pay never
  costs real money. Cached per `(user, job)` like JobQuick's old boost/
  message features, so re-opening the same job never re-drafts or re-charges.

## Deliberately not built (and why)

**Warm-intro finder** — the blueprint proposed surfacing 2nd-degree
LinkedIn connections before falling back to a cold recruiter email. That
needs LinkedIn's connection graph, which neither Apollo nor any realistic
third-party API exposes to outside applications. Building a fake version of
this would be worse than not having it; it stays out until there's an
honest data source for it.

**Everything else from the blueprint's "new wow features" list** — ghost-job
detector, mock interview simulator, negotiation coach, apply-anywhere
browser extension, funnel/streak dashboard — is real product work, just not
part of the core Job Engine → HuntOps port. Reasonable next phases once the
core loop (find → score → reach out) is validated with real users.

## Project layout

```
backend/
  app/
    core/       settings, JWT/password security, rate limiter
    db/         SQLAlchemy engine/session
    models/     User, Job, Application, CreditLedgerEntry, Resume, JobMatch,
                IngestionRun, GmailConnection, EmailSyncRun,
                RecruiterContact, Outreach
    schemas/    Pydantic request/response models, AI response schemas
    routers/    auth, users, jobs, applications, billing, resumes, matches,
                integrations (Gmail), outreach, admin, health
    services/   credits ledger, Stripe billing, AI client, résumé parsing,
                job-fit matching, job aggregation, Gmail OAuth + message
                parsing + sending, email-alert bridge, Apollo recruiter
                discovery, outreach drafting/orchestration, daily scheduler
  alembic/      migrations (0001 core, 0002 aggregation + matching,
                0003 email bridge, 0004 outreach)
  tests/        pytest suite (sqlite in-memory, external calls mocked — no
                network or API keys needed to run it)
docker-compose.yml   Postgres + API for local dev
```

## Running locally

**Option A — Docker (recommended):**

```bash
cp backend/.env.example backend/.env
# edit backend/.env: JWT_SECRET, Stripe test keys, ANTHROPIC_API_KEY
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
DB with Stripe and Anthropic calls mocked, and aggregation sources exercised
with realistic fixture responses rather than live HTTP calls:

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

## AI setup

Set `ANTHROPIC_API_KEY` to a real key to enable résumé parsing
(`POST /api/resumes/upload`) and fit scoring (`GET /api/ai/match-jobs`).
Without it, those two endpoints return a `502` with a clear error instead of
crashing — everything else in the API works fine without an AI key.

## Aggregation setup

Five of the six sources need no configuration. Adzuna additionally needs
`ADZUNA_APP_ID` / `ADZUNA_APP_KEY` (free at https://developer.adzuna.com/) —
leave them blank and that source is skipped, logged as `status: success,
fetched: 0` rather than an error. Set `ENABLE_SCHEDULED_AGGREGATION=false`
to disable the daily 07:00 UTC run and only trigger ingestion manually via
`POST /api/admin/jobs/aggregate`.

## Gmail setup

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials),
   create an OAuth 2.0 Client ID (Web application), enable the Gmail API for
   the project, and add `GOOGLE_OAUTH_REDIRECT_URI`'s value to the client's
   authorized redirect URIs.
2. Set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` and a real
   `TOKEN_ENCRYPTION_KEY` (see `.env.example` for how to generate one).
3. A job seeker calls `GET /api/integrations/gmail/connect`, visits the
   returned URL, and consents. Google redirects back to
   `/api/integrations/gmail/callback`, which creates the Gmail label/filters
   and stores encrypted tokens — no manual Gmail configuration needed.
4. `POST /api/integrations/gmail/sync` triggers an immediate sync;
   otherwise it runs daily at 07:10 UTC via the scheduler.

## Apollo + Outreach setup

1. Get a **master** API key from [Apollo.io](https://developer.apollo.io/) —
   a non-master key gets a 403 on people search — and set `APOLLO_API_KEY`.
2. A job seeker needs an Elite subscription, an uploaded résumé, and
   (optionally, to enable actual sending rather than draft-only output) a
   connected Gmail account from the Phase 3 setup above.
3. `POST /api/outreach {"job_id": "..."}` runs the whole flow: find/reuse a
   recruiter contact for the job's company, draft a personalized pitch, and
   send it if a recruiter email and connected Gmail are both available.
   Costs `OUTREACH_CREDIT_COST` (default 30) credits on first request for a
   given job; repeat requests for the same job return the cached result for
   free. `GET /api/outreach/mine` lists everything a user has sent or drafted.

## What's next (Phase 5)

Reach & retention: the daily digest/push notification, and the account-side
work needed before any of this goes in front of real users — rate limiting
beyond auth, observability, and a frontend to actually drive the flows this
API now supports end to end.
