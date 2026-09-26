# Setting up your first alert mailbox

Do **Canada only**, all the way through, before touching UK or Dubai. You will
learn something from the first real extraction run that changes how you set up
the other two, and debugging one market is far easier than three.

Assumes you already created `alerts-canada@jobquickai.site` in Hostinger, and
that the release with the mailboxes page is deployed.

---

## Step 1 — Find your IMAP settings

Hostinger sells two mail products and they use different servers, so check
rather than guess.

1. Log in to **hPanel**
2. **Emails** → select `jobquickai.site`
3. Look for **Configuration settings** (sometimes under "Connect apps &
   devices" → "Other apps")

Write down the **IMAP host** and **port**. It will be one of:

| Product | IMAP host | Port |
|---|---|---|
| Hostinger Email | `imap.hostinger.com` | 993 |
| Titan | `imap.titan.email` | 993 |

Also note the **SMTP host** on the same page — you need it in Step 5.

---

## Step 2 — Confirm mail can actually reach the mailbox

Before subscribing to anything, prove the mailbox works. Send an email from
your personal address to `alerts-canada@jobquickai.site`, then open Hostinger
webmail and check it arrived.

If it did not arrive, mail is not being routed to Hostinger and nothing else in
this guide will work. On the server:

```bash
dig +short MX jobquickai.site
```

You want Hostinger's servers (`mx1.hostinger.com` / `mx2.hostinger.com`, or the
Titan equivalents). If it is empty or points elsewhere, add Hostinger's MX
records in whichever DNS zone is authoritative for `jobquickai.site`.

**Do not change the A record.** Web and mail are separate; the site stays on
AWS.

---

## Step 3 — Subscribe the mailbox to Canadian job alerts

This is the step that actually creates supply. Everything else is plumbing.

For each board below: create an account using `alerts-canada@jobquickai.site`,
confirm the verification email in Hostinger webmail, then create the alerts.

### Settings that apply to every board

- **Frequency: Daily.** Not instant, not weekly. One email with twenty jobs
  costs one AI call; twenty instant emails cost twenty, for the same jobs.
- **Location: Canada.** Country-wide, not a city. Users narrow to a city
  themselves in their own preferences; a Toronto-only alert just means you
  never carry Vancouver.
- **Do not** create a separate "remote" alert. Remote roles appear in the
  country alerts anyway.

### The boards

**LinkedIn** — Jobs → search a title → set Location to Canada → toggle
**Job alert** on → set to Daily.

**Indeed.ca** — search a title, set location to Canada → **Activate** the job
alert under the results → choose Daily.

**Job Bank** (jobbank.gc.ca) — Job Search → run a search → **Create job alert**
→ Daily.

**Workopolis** — search → "Get job alerts" → Daily.

### Which searches

Three job families to start. One alert per family per board:

| Family | Search terms |
|---|---|
| Marketing | `marketing manager`, `growth marketing`, `digital marketing` |
| Sales | `sales manager`, `business development`, `account executive` |
| Operations | `operations manager`, `project manager`, `business operations` |

That is roughly 9–12 alerts for Canada. Do not add more families yet — the
signup form only offers a job family once it has five real listings, so extra
families with thin supply are invisible to users anyway.

**Wait 24 hours.** Alerts are daily, so the mailbox will be empty until the
first digests arrive. There is nothing to sync before then.

---

## Step 4 — Add the mailbox in JobQuick AI

Sign in at `https://jobquickai.site` as your admin, then **Alert mailboxes** →
**Add mailbox**.

| Field | What to enter |
|---|---|
| Mailbox address | `alerts-canada@jobquickai.site` |
| Market | `Canada` |
| Mail host | Click the **Hostinger Email** or **Hostinger (Titan)** preset, matching Step 1 |
| Port | 993 (the preset fills this) |
| Username | Leave blank — it defaults to the full address, which Hostinger expects |
| Password | The mailbox password you set when creating it in hPanel |
| Folder | `INBOX` |
| Job families | Leave empty |

On **Market**: this exact string is what job seekers pick at signup. Type it
once, carefully. `Canada` and `canada` would appear as two separate countries,
and changing it later strands everyone who chose the old spelling.

On **Job families**: only fill this in if a mailbox receives *one* family of
work. It is a fallback used when a job's own title gives nothing away. Since
this mailbox carries marketing, sales and operations, leave it empty and let
each listing speak for itself.

Click **Add and test**. It logs in immediately.

- **"alerts-canada@jobquickai.site connected"** — good, continue.
- **"Login failed… use an app password"** — the password is wrong, or
  Hostinger wants an app-specific one. Regenerate it in hPanel.
- **"Could not connect to …"** — wrong host or port. Recheck Step 1.
- **"Mailbox has no folder named 'INBOX'"** — rare; check the folder name in
  webmail, some hosts capitalise differently.

---

## Step 5 — Point the app's own outbound mail at Hostinger

Separate from the mailboxes. This is how digests and outreach get *sent*.

Create `noreply@jobquickai.site` in hPanel, then on the server:

```bash
cd /opt/huntops && nano backend/.env
```

Set these (matching the SMTP host from Step 1):

```
SMTP_HOST=smtp.hostinger.com
SMTP_PORT=587
SMTP_USERNAME=noreply@jobquickai.site
SMTP_PASSWORD=<that mailbox's password>
SMTP_FROM_EMAIL=noreply@jobquickai.site
SMTP_USE_TLS=true
ADMIN_ALERT_EMAIL=<your own address>
```

Then recreate the containers:

```bash
cd /opt/huntops && docker compose -f docker-compose.prod.yml up -d api scheduler
```

`up -d`, not `restart`. Restart reuses the old container with its baked-in
environment, so the edits are ignored and it looks like nothing happened.

Without SMTP the digest fails **silently** — it logs and moves on, so no error
appears anywhere and mail simply never arrives. `ADMIN_ALERT_EMAIL` is how you
find out when a mailbox stops working.

---

## Step 6 — Sync, and read what it tells you

Once the first daily digests have arrived (check Hostinger webmail — if the
inbox is empty, wait), go to **Alert mailboxes** and click **Sync** on the
Canada mailbox.

### What the outcomes mean

**"12 new jobs"** — working. Go to the job feed and look at them. Check the
titles are real roles, the companies look right, and the locations are
Canadian. This is the first time the AI extractor has seen real mail, and it
is the thing I cannot predict for you.

**"Read 14 message(s) but recognised no job-alert senders. Saw: …"** — mail is
arriving but from a board not on the allowlist. Send me the domains listed and
I will add them.

**"0 fetched"** — the mailbox is empty. Either the alerts have not arrived yet,
or the subscriptions did not complete. Check webmail directly.

**A red "Failing" badge** — the error text on the card says what happened.
Login failures usually mean a rotated or mistyped password.

### Then check the signup form

Open `https://jobquickai.site/register` in a private window and go to the second
step. You should now see **Canada** as a market. Job families appear once each
has five live listings, ordered by how much supply each actually has.

If Canada is missing, the mailbox is not active or has not synced successfully.

---

## Step 7 — Only now, repeat for UK and Dubai

Same steps, with:

| Market string | Mailbox | Boards |
|---|---|---|
| `United Kingdom` | alerts-uk@jobquickai.site | LinkedIn, Indeed.co.uk, Reed, Totaljobs |
| `United Arab Emirates` | alerts-dubai@jobquickai.site | LinkedIn, Bayt, Naukrigulf, Indeed.ae |

On the last one: you named the mailbox "dubai", but the **market** is what
users choose. `United Arab Emirates` covers the supply your alerts will
actually carry — a Dubai-only label reads as a city and would make someone skip
Abu Dhabi roles. The mailbox name does not have to match the market.


## Forwarding from an existing inbox

Pointing a mailbox you already own at an alert address is the fastest way to
get supply, and both kinds of forwarding now work — but they work for
different reasons, and one of them is worth preferring.

**Automatic forwarding (recommended).** A rule at the source mailbox —
Gmail's Settings → Forwarding, or a filter that forwards matching mail —
resends the message with its `From` header untouched. LinkedIn still looks
like LinkedIn, so it is recognised the same as mail delivered directly.

**Manual forwarding.** Pressing Forward creates a *new* message: `From`
becomes you, and the original is quoted in the body. The sync reads the
quoted header block, so these are recognised too, but only the top of the
message is scanned and an alert buried under a long reply chain can be
missed.

Prefer automatic forwarding where you can. It is the more reliable of the
two, and it keeps working without anyone remembering to press anything.

Either way the allowlist still decides: forwarding changes where the original
sender is looked for, never which senders count. Forwarding a newsletter, or
an employer-side "someone applied to your posting" notice, is still ignored.

If you forward from Gmail, set the filter to forward only job alerts rather
than everything. Anything else that arrives costs nothing in AI calls — it is
skipped on the sender check — but it fills the mailbox and makes the sync
report harder to read.
