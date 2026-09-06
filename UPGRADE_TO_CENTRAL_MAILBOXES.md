# Upgrading the live server: central mailboxes + huntops.site

Run these on the Lightsail box, in order. Everything is one line so nothing
breaks on a lost newline when pasting.

This release does two things at once: it changes the domain to `huntops.site`,
and it moves the job supply from per-user Gmail to admin-connected alert
mailboxes. The database changes are additive — no existing data is deleted.

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
cd /opt/huntops && sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://huntops.site|' backend/.env && sed -i 's|^FRONTEND_URL=.*|FRONTEND_URL=https://huntops.site|' backend/.env && sed -i 's|^GOOGLE_OAUTH_REDIRECT_URI=.*|GOOGLE_OAUTH_REDIRECT_URI=https://huntops.site/api/integrations/gmail/callback|' backend/.env
```

Check all three actually took — `sed` silently does nothing if the key wasn't
already in the file:

```bash
cd /opt/huntops && grep -E '^(CORS_ORIGINS|FRONTEND_URL|GOOGLE_OAUTH_REDIRECT_URI)=' backend/.env
```

You must see all three lines with `huntops.site` in them. If one is missing,
append it:

```bash
cd /opt/huntops && echo 'GOOGLE_OAUTH_REDIRECT_URI=https://huntops.site/api/integrations/gmail/callback' >> backend/.env
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

## 6. Update Google Cloud Console

The redirect URI is checked byte for byte by Google, so it has to be
registered before any mailbox can be connected.

1. Go to **Google Cloud Console → APIs & Services → Credentials**
2. Open your OAuth 2.0 Client ID
3. Under **Authorized redirect URIs**, add exactly:
   `https://huntops.site/api/integrations/gmail/callback`
4. Under **Authorized JavaScript origins**, add `https://huntops.site`
5. Save. Changes can take a few minutes to take effect.

Leave the old URI in place until you are sure the new one works.

---

## 7. Make yourself admin

Nothing appears in anyone's feed until an admin connects a mailbox.

```bash
cd /opt/huntops && docker compose -f docker-compose.prod.yml exec api python -m app.scripts.create_admin you@huntops.site --name "Ops Admin"
```

It prompts for a password twice. If that email already has an account, it
promotes it instead.

---

## 8. Connect a mailbox per market

Open `https://huntops.site`, sign in as the admin, go to
**Alert mailboxes → Connect mailbox**.

For each market:

1. Type the market name — `Canada`, `Nigeria`, `United Kingdom`. This exact
   string is what users pick at signup, so keep it clean and consistent.
2. Optionally name it and tag the job families it covers.
3. **Continue to Google** and sign in as the account that receives that
   country's job alerts.

HuntOps creates a `HuntOps` label in that inbox and filters routing your
LinkedIn/Indeed/Glassdoor alert mail into it. It only ever reads what those
filters catch.

Then hit **Sync** on each one to pull immediately rather than waiting for the
07:10 UTC run.

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

That drops the mailbox, preference and autopilot tables and deletes mailbox
sync-run rows, which have no user to attribute them to once mailboxes are
gone. Everything else is untouched.
