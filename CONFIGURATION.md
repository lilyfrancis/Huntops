# Configuring every integration

Work through this in order. Step 0 is urgent; the rest can be done over a
few sittings.

Everything lives in `/opt/huntops/backend/.env` on the server. That file is
owned by root, so edit it with:

```bash
sudo nano /opt/huntops/backend/.env
```

Without `sudo` nano opens it read-only and silently discards your changes —
it says `[ File 'backend/.env' is unwritable ]` in the status bar.

**Never put a space after the `=`.** `KEY= value` is a different string from
`KEY=value` and some parsers keep the space.

---

## Step 0 — Rotate the exposed secrets (do this first)

Four secrets have been shown on screen: `JWT_SECRET`, `TOKEN_ENCRYPTION_KEY`,
`ANTHROPIC_API_KEY` and a **live** `PAYSTACK_SECRET_KEY`. Replace all four.

Generate the two local ones:

```bash
openssl rand -hex 32
```

```bash
docker run --rm python:3.11-slim python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The first is the new `JWT_SECRET`, the second the new `TOKEN_ENCRYPTION_KEY`.

**Do this before adding any mailbox.** `TOKEN_ENCRYPTION_KEY` encrypts stored
mailbox passwords; once mailboxes exist, changing it makes every one of them
undecryptable and they all have to be re-entered. You have none right now, so
rotating is free. The same is true of `JWT_SECRET` and sessions — rotating logs
everyone out, and there is nobody to log out.

---

## Step 1 — Anthropic

Powers everything AI: fit scoring, extracting jobs from alert emails, mock
interviews, outreach drafting. Without it the product does almost nothing.

1. [console.anthropic.com](https://console.anthropic.com) → **API Keys**
2. **Create Key**, name it `huntops-production`
3. Copy it immediately — it is shown once

```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

Check the account has credit. A valid key on an empty balance fails at the
point of use with a message about credit, not about the key.

---

## Step 2 — Outbound email (Hostinger SMTP)

Powers the daily digest and outreach sent on a user's behalf. **Its failure
mode is silence** — the code logs and moves on, so nothing errors anywhere and
mail simply never arrives.

1. In hPanel, create the mailbox `noreply@huntops.site` and set a password
2. **Emails → huntops.site → Configuration settings** — note the SMTP host

```
SMTP_HOST=smtp.hostinger.com
SMTP_PORT=587
SMTP_USERNAME=noreply@huntops.site
SMTP_PASSWORD=<that mailbox's password>
SMTP_FROM_EMAIL=noreply@huntops.site
SMTP_USE_TLS=true
ADMIN_ALERT_EMAIL=<your own address>
```

Use `smtp.titan.email` instead if Configuration settings says Titan.

`ADMIN_ALERT_EMAIL` is where you are told a mailbox stopped syncing or a
scheduled job crashed. Without it those failures are only in the logs.

---

## Step 3 — Paystack

### 3a. The secret key

1. [dashboard.paystack.com](https://dashboard.paystack.com) → **Settings →
   API Keys & Webhooks**
2. Copy the **Secret Key** — the one starting `sk_`, not the public `pk_` one

Live mode gives `sk_live_...`, test mode `sk_test_...`. Use test until you have
verified a full payment end to end.

### 3b. The plans — this is where `PLN_xxx` came from

`PLN_xxx` is a placeholder. Real codes only exist once you create the plans.

1. **Plans** in the left sidebar → **Create Plan**
2. Pro: name `Pro`, interval **Monthly**, amount in your currency
3. Repeat for `Elite`
4. Open each and copy its **Plan Code** — a real one looks like `PLN_a1b2c3d4e5`

**Plans created in test mode do not exist in live mode.** They are separate
worlds with separate codes. If you switch a `sk_test_` key for a `sk_live_` one
later, you must also swap the plan codes for the live plans' codes, or checkout
fails with a plan-not-found error while the key itself tests fine.

```
PAYSTACK_SECRET_KEY=sk_test_...
PAYSTACK_PLAN_PRO=PLN_<real code>
PAYSTACK_PLAN_ELITE=PLN_<real code>
BILLING_CURRENCY=NGN
PRO_PRICE=12000
ELITE_PRICE=45000
```

`PRO_PRICE` and `ELITE_PRICE` are display only — the card is charged whatever
the Paystack plan says. Keep them matching by hand.

### 3c. The webhook

Same **API Keys & Webhooks** page, set the webhook URL to:

```
https://huntops.site/api/billing/webhook
```

There is no separate signing secret; Paystack signs with the secret key you
already configured.

**The webhook is the only thing that grants a paid tier.** Without it a
customer pays, Paystack takes the money, and nothing happens in the app.

---

## Step 4 — Apollo

Finds a hiring contact so outreach has somewhere to go. Optional: without it,
pitches are still drafted, they just have no recipient.

1. [apollo.io](https://apollo.io) → **Settings → Integrations → API**
2. **Create new key**
3. **Tick "master key".**

That last step is the whole difficulty. A normal key works on every other
endpoint and returns **403 on people search**, which is the only call this app
makes. If Apollo returns 403, this is why.

```
APOLLO_API_KEY=<key>
```

Coverage is honest to expect: good for Canada and the UK, moderate for the
UAE, poor for Nigeria. Nigerian outreach will often find nobody and fall back
to draft-only, which is handled but worth knowing.

---

## Step 5 — WhatsApp

An alternative digest channel. Worth having where email open rates are poor,
which includes Nigeria and the Gulf.

### 5a. The app and phone number

1. [developers.facebook.com/apps](https://developers.facebook.com/apps) →
   **Create App** → type **Business**
2. Add the **WhatsApp** product
3. **API Setup** shows a test number and a **Phone number ID** — copy the ID
4. For production, add your own number under **Add phone number** and verify it

### 5b. A token that does not expire overnight

API Setup shows a temporary token. **Do not use it** — it lasts 24 hours, and
when it dies the digest stops with no error anywhere.

1. [business.facebook.com/settings](https://business.facebook.com/settings) →
   **Users → System Users**
2. **Add** a system user, role Admin
3. **Add Assets** → your WhatsApp app → full control
4. **Generate New Token** → select the app → tick
   `whatsapp_business_messaging` and `whatsapp_business_management`
5. Set expiry to **Never** and copy it

### 5c. The message template

A message your business initiates — which a daily digest always is — can only
be a template approved by Meta in advance. Free text is allowed only inside a
24-hour window the user opens by messaging you first, which never happens for
a digest.

1. **WhatsApp Manager → Message Templates → Create Template**
2. Name: `huntops_daily_digest`
3. Category: **Utility**
4. Language: English
5. Body, exactly:

```
Hi {{1}}, you have {{2}} new job matches on HuntOps today. Top one: {{3}}
```

6. Provide samples when asked (`Amara`, `4`, `Growth Lead at Shopify`)
7. Submit. Approval is usually minutes.

Category matters: **Utility** is cheaper than Marketing and less likely to be
rejected for a digest.

```
WHATSAPP_PHONE_NUMBER_ID=<from API Setup>
WHATSAPP_ACCESS_TOKEN=<system user token>
WHATSAPP_TEMPLATE_NAME=huntops_daily_digest
WHATSAPP_TEMPLATE_LANGUAGE=en
```

---

## Step 6 — Fix the two wrong values already in the file

```
GOOGLE_OAUTH_REDIRECT_URI=https://huntops.site/api/integrations/gmail/callback
```

It currently points at `jobquick.site`. Harmless today — that flow is off by
default — but wrong.

And remove the space in `ANTHROPIC_API_KEY= sk-ant-...`.

---

## Step 7 — Apply and verify

```bash
cd /opt/huntops && docker compose -f docker-compose.prod.yml up -d --build
```

`up -d`, never `restart`. A restart reuses the existing container with its old
baked-in environment, so every change above is ignored and it looks like the
edits did nothing.

Then open **Admin → Integrations** in the app. Every integration is listed with
a **Test** button that makes a real call to the provider and reports what came
back. That page is the answer to "is this key working" — a key that is present
but rejected looks identical to a working one everywhere else.

Expect:

| | |
|---|---|
| Anthropic | Working |
| Outbound email | Working |
| Paystack | Working, both plan codes found |
| Apollo | Working — or a 403 telling you the key is not a master key |
| WhatsApp | Connected, with the number's quality rating |

Anything red says what to fix.

---

## Keeping secrets off the screen

To confirm a key is loaded without printing it:

```bash
cd /opt/huntops && docker compose -f docker-compose.prod.yml exec -T api sh -c 'env | grep -oE "^[A-Z_]+_(KEY|SECRET|TOKEN|PASSWORD)=" ' | sort
```

That lists the names of the secrets that are set, and none of their values.
