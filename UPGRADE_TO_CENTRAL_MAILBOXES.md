# Upgrading the live server: central mailboxes + huntops.site

Run these on the Lightsail box, in order. Everything is one line so nothing
breaks on a lost newline when pasting.

This release changes the domain to `huntops.site` and moves the job supply
from per-user Gmail to admin-configured alert mailboxes read over IMAP. It also
switches billing from Stripe to Paystack.

No Google Cloud project, OAuth client or verification is needed for any of it.

---

## 1. Get on the box and take a backup first

```bash
sudo -i
```

```bash
cd /opt/huntops && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U huntops huntops > /root/huntops-backup-$(date +%F).sql && ls -lh /root/huntops-backup-*.sql
```

Do not skip this. It is the only thing standing between a bad migration and a
lost database, and it takes seconds.

---

## 2. Pull the new code

```bash
cd /opt/huntops && git fetch origin && git checkout claude/busy-hamilton-4zazvl && git pull origin claude/busy-hamilton-4zazvl
```

This deploys the feature branch. Once it has been running happily for a day,
merge it into `main` and switch the server back to `main` — running production
off a long-lived feature branch is fine for a cutover, not as a habit.

---

## 3. Point the deployment at huntops.site

Two files hold the domain. First the compose env:

```bash
cd /opt/huntops && sed -i 's/^DOMAIN=.*/DOMAIN=huntops.site/' .env && grep '^DOMAIN=' .env
```

Then the application env:

```bash
cd /opt/huntops && sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://huntops.site|' backend/.env && sed -i 's|^FRONTEND_URL=.*|FRONTEND_URL=https://huntops.site|' backend/.env
```

Check both actually took — `sed` silently does nothing if the key wasn't
already in the file:

```bash
cd /opt/huntops && grep -E '^(CORS_ORIGINS|FRONTEND_URL)=' backend/.env
```

Then add the Paystack keys, which are new in this release:

```bash
cd /opt/huntops && printf 'PAYSTACK_SECRET_KEY=sk_live_xxx\nPAYSTACK_PLAN_PRO=PLN_xxx\nPAYSTACK_PLAN_ELITE=PLN_xxx\nBILLING_CURRENCY=NGN\n' >> backend/.env
```

---

## 4. Confirm DNS actually resolves here before restarting

Caddy asks Let's Encrypt for a certificate the moment it boots with the new
domain. If DNS is not pointing here yet, that request fails and it will keep
retrying against a rate limit.

```bash
dig +short huntops.site && curl -s ifconfig.me && echo
```

The two must print the same IP address. If they don't, stop and wait for DNS
to propagate — everything below still works later.

---

## 5. Rebuild and restart

```bash
cd /opt/huntops && docker compose -f docker-compose.prod.yml up -d --build
```

`up -d` and not `restart`: restart reuses the existing container with its old
baked-in environment, so every value you just changed would be ignored and it
would look like the edits did nothing.

Migrations run automatically in the `migrate` container. Check it finished:

```bash
cd /opt/huntops && docker compose -f docker-compose.prod.yml ps
```

`db`, `api`, `scheduler`, `web`, `caddy` **running**; `migrate` **exited (0)**.

If `migrate` exited non-zero, nothing else will work — read why:

```bash
cd /opt/huntops && docker compose -f docker-compose.prod.yml logs migrate | tail -40
```

---

## 6. Point the Paystack webhook at the new domain

In the Paystack dashboard, **Settings → API Keys & Webhooks**, set the webhook
URL to:

```
https://huntops.site/api/billing/webhook
```

There is no separate signing secret — Paystack signs with the same secret key
you configured above. The webhook is the **only** thing that grants a paid
tier, so without it subscriptions take payment and never activate.

---

## 7. Make yourself admin

Nothing appears in anyone's feed until an admin connects a mailbox.

```bash
cd /opt/huntops && docker compose -f docker-compose.prod.yml exec api python -m app.scripts.create_admin you@huntops.site --name "Ops Admin"
```

It prompts for a password twice. If that email already has an account, it
promotes it instead.

---

## 8. Add a mailbox per market

Open `https://huntops.site`, sign in as the admin, go to
**Alert mailboxes → Add mailbox**.

For each market you want to serve:

1. **Mailbox address** — e.g. `alerts-canada@huntops.site`. Create it on
   whatever mail host you already use for the domain; it does not have to be
   Google.
2. **Market** — `Canada`, `Nigeria`, `United Kingdom`. This exact string is
   what users pick at signup, so keep it clean and consistent.
3. **IMAP host, username and password.** If the mailbox has two-factor
   authentication, this must be an **app password**, not the account password.

Saving runs a connection test straight away, so a wrong password shows up while
you are still looking at the form rather than as an empty feed tomorrow. The
password is encrypted at rest and never sent back to the browser.

Then subscribe each mailbox to that country's LinkedIn, Indeed or Glassdoor
job alerts, and hit **Sync** to pull immediately rather than waiting for the
07:10 UTC run.

The first sync reads the last few days; every sync after that resumes from
where it stopped, so nothing is read — or paid for — twice.

---

## 9. Verify

```bash
curl -sI https://huntops.site | head -3
```

Then, in the browser:

- **Signup** now has a second step asking for market and job family. The
  markets offered are exactly the mailboxes you connected — if that list is
  empty, go back to step 8.
- **Job feed** shows only jobs matching what the account picked, each with a
  fit score, and an Apply button on jobs posted on HuntOps or a link out on
  jobs found elsewhere.
- **Autopilot** is off by default. Turning it on and pressing *Run autopilot
  now* should either act or tell you why it didn't.
- **Admin → Ops health** lists each mailbox sync with its own name.
- **Profile → Billing** shows plan prices in your configured currency, and a
  test Paystack payment activates the tier via the webhook.

---

## Rolling back

```bash
cd /opt/huntops && git checkout main && docker compose -f docker-compose.prod.yml up -d --build
```

The schema change is additive, so the previous release runs fine against the
new database — the new tables are simply ignored. (Verified, not assumed: the
previous release's models were pointed at a migrated database and still read
and wrote every existing table.) If you also need the old
schema back:

```bash
cd /opt/huntops && docker compose -f docker-compose.prod.yml run --rm migrate alembic downgrade 0009_dedupe_uniques
```

That drops the mailbox, preference and autopilot tables, reverts the billing
columns to their Stripe names, and deletes mailbox sync-run rows, which have no
user to attribute them to once mailboxes are gone. Ingested jobs, users,
applications and everything else are untouched.
