# HuntOps

The job search copilot that finds real openings, scores your fit for where you
actually live, and emails the recruiter for you.

This repo is being built in phases against the product blueprint
(Foundation → Real supply → Fit intelligence → Email-alert bridge →
Autopilot Outreach → Reach & retention → Frontend → Landing page).

**Phase 1 — Foundation**: auth, roles, job/application CRUD, real Stripe billing. ✅
**Phase 2 — Real supply & fit intelligence**: live job aggregation, résumé
parsing, geo-aware fit scoring. ✅
**Phase 3 — Email-alert bridge**: per-user Gmail OAuth, auto-provisioned
label + filters, AI extraction of jobs from alert emails. ✅
**Phase 4 — Autopilot Outreach**: Apollo recruiter discovery, AI-drafted
pitches, sending via the user's own Gmail. ✅ — the flagship feature.
**Phase 5 — Reach & retention**: daily digest email, consolidated admin
analytics, scheduled-job failure alerting, rate limiting on AI-costing
endpoints. ✅
**Phase 6 — Frontend**: a real React app covering every job-seeker,
employer, and admin flow the API supports. ✅
**Phase 7 — Landing page**: an animated marketing page — hero, scroll
reveals, pricing — in front of the app. ✅
**Phase 8 — Ghost-job detector**: heuristic scoring that flags listings
which probably aren't a real, fillable seat, with the reasons shown. ✅
**Phase 9 — Mock interview simulator**: role-specific questions, per-answer
grading, and a session summary. Pro's own headline feature. ✅
**Phase 10 — Momentum dashboard**: cumulative application funnel, daily
streak, and an 8-week activity grid. Free on every tier. ✅

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

## What's in Phase 5

- **Daily digest email**: the scheduled job re-scores every job seeker with
  a résumé against recent active jobs, persists the matches (through the
  same `persist_matches` function the interactive `/api/ai/match-jobs`
  endpoint uses — one code path, not two that can drift), and emails a
  home-market-first summary. Ported from Job Engine's "Build Digest" step,
  generalized from one shared Telegram chat to per-user email.
- **Consolidated admin analytics** (`GET /api/admin/analytics`): user/job/
  application counts, subscription revenue estimate, and — unlike JobQuick's
  original version — real ingestion success rate and outreach send success
  rate, because this product's supply and outreach are real enough to have
  a success rate worth watching.
- **Scheduled-job failure alerting**: if the aggregation, email-sync, or
  digest job crashes outright, an admin email fires — the generalized,
  email-based equivalent of Job Engine's dedicated Telegram error-alert
  workflow. A single user's AI failure inside the digest loop is logged and
  skipped, not treated as a crash worth paging on.
- **Rate limiting extended past auth**: résumé upload, job matching, and
  outreach creation are now capped per IP (10/hour, 20/hour, 10/hour) on
  top of the credit/tier gates already in place — the credit system stops
  someone from affording abuse, this stops someone from just hammering the
  endpoint.
- **Request logging + expanded health check**: every request logs method,
  path, status, and duration; `/api/health/detailed` now reports whether
  Anthropic/Apollo/Gmail OAuth/SMTP are configured and whether the
  scheduler is actually running, not just database/Stripe.

## What's in Phase 6

- **Full role-based app** built on Vite, React 19, TypeScript, Tailwind v4,
  Radix UI primitives, and TanStack React Query — covering the job seeker
  (feed, matches, résumé upload, applications, Autopilot Outreach, digest
  preview, Gmail connect, profile), employer (post/manage jobs, review
  applicants), and admin (analytics, pending-job moderation, user
  approval, ops health) surfaces end to end.
- **JWT auth with silent refresh**: access + refresh tokens with a
  singleton in-flight refresh promise so concurrent 401s don't each trigger
  their own refresh call, and a global `huntops:unauthorized` event that
  logs the user out cleanly on final failure.
- **Three real backend gaps found and fixed by building a real frontend
  against the real API**, rather than assuming the Phase 1-5 contract was
  UI-ready: `JobOut` wasn't exposing `lane`/`is_remote`/`source_url`/
  `restricted_to` despite the model having them; `ApplicationOut` only
  exposed a bare candidate UUID, unusable for an employer reviewing
  applicants, so `candidate_name`/`candidate_email` are now denormalized
  onto `Application` at apply-time (migration `0005`); and the Gmail OAuth
  callback returned raw JSON instead of redirecting back into the app.
- **Verified with a real end-to-end browser run**, not just a compile
  check: Playwright drives the full business flow — employer registers,
  is blocked from posting pre-approval, admin approves the employer, the
  employer posts a job, admin approves the job, a job seeker sees it in
  the feed and applies, and the employer sees the real applicant name and
  email on the Applicants page — with zero console or page errors.

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
frontend/
  src/
    components/ ui primitives (button, card, dialog, select, ...),
                layout (app shell, protected routes, page header),
                jobs/matches/admin presentational components
    hooks/      use-auth (JWT session context)
    lib/        typed API client (one module per backend domain), TS
                mirrors of every backend schema, token storage, query
                client, cn()/formatting helpers
    pages/      jobseeker/, employer/, admin/ route pages
backend/
  app/
    core/       settings, JWT/password security, rate limiter
    db/         SQLAlchemy engine/session
    models/     User, Job, Application, CreditLedgerEntry, Resume, JobMatch,
                IngestionRun, GmailConnection, EmailSyncRun,
                RecruiterContact, Outreach
    schemas/    Pydantic request/response models, AI response schemas
    routers/    auth, users, jobs, applications, billing, resumes, matches,
                integrations (Gmail), outreach, digest, admin, health
    services/   credits ledger, Stripe billing, AI client, résumé parsing,
                notifications (SMTP digest/alerts), daily digest builder,
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

API is at `http://localhost:8000`, the app is at `http://localhost:5173`.
Run migrations once the DB is up:

```bash
docker compose exec api alembic upgrade head
```

**Option B — Local Python + Node:**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # point DATABASE_URL at a Postgres you have running
alembic upgrade head
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` and `/health` to `http://localhost:8000`
by default (see `vite.config.ts`; override with `VITE_API_BASE_URL`).

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

## Digest + admin alerting setup

1. Set `SMTP_HOST` (and `SMTP_USERNAME`/`SMTP_PASSWORD` if your relay needs
   auth) to any SMTP provider — SendGrid, Postmark, SES, or a real mailbox
   in dev. Without it, `send_email` logs and returns `False` instead of
   raising, so nothing else breaks.
2. `GET /api/digest/preview` renders a job seeker's digest from whatever's
   already scored (call `GET /api/ai/match-jobs` first if it looks empty).
   The scheduled job at 07:30 UTC scores fresh matches for every job seeker
   with a résumé, then emails the digest — no manual step needed.
3. Set `ADMIN_ALERT_EMAIL` to get emailed if the aggregation, email-sync, or
   digest scheduled job crashes outright. Per-item failures (one bad
   aggregation source, one user's AI hiccup) are logged and skipped, not
   alerted on — only a crash of the whole scheduled run pages you.
4. `GET /api/admin/analytics` (admin-only) is the one-stop view: user/job/
   application counts, revenue estimate, outreach send success rate, and
   recent ingestion success rate.

## What's next

The core loop (find → score → reach out) is now clickable end to end for
job seekers, employers, and admins, with a real marketing page in front
of it, ghost listings flagged in the feed, interview practice behind the
Pro tier, and a momentum dashboard closing the loop. The last item still
on the deferred wow-features list is the negotiation coach.
