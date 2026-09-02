# Deploying HuntOps to AWS Lightsail — step by step

Lightsail is the simplest thing on AWS that runs this stack: one fixed monthly
price, one Linux box, no VPC/NAT/load-balancer bill to trip over. Everything
below is copy-paste.

**Time:** about 30 minutes, most of it waiting for builds.

---

## Step 0 — Stop the old JobQuick app first

It is still consuming your credit. Do this before anything else.

**If there is data in it you want**, take a backup first — deleting is
permanent and AWS keeps nothing.

1. Go to the [Billing console → Bills](https://console.aws.amazon.com/billing/home#/bills),
   pick the current month, and expand **"Charges by service"**. That tells you
   exactly which services the $20 went to — usually EC2, RDS, or Lightsail.
2. Delete what you find, in whichever consoles it names:
   - **Lightsail** → instance → ⋮ → **Delete**. Also check the **Storage** and
     **Networking** tabs — detached disks and static IPs still bill.
   - **EC2** → Instances → **Terminate** (not "Stop" — a stopped instance still
     bills for its EBS volume). Then EC2 → **Volumes** and delete leftovers,
     and **Elastic IPs** → release any unattached ones.
   - **RDS** → Databases → **Delete**. This is usually the expensive one.
     It will offer a final snapshot; snapshots also cost, so skip it unless you
     want the data.
3. Re-check Bills tomorrow. Charges lag ~24h, so confirm it actually stopped.

---

## Step 1 — Switch off the AWS Free plan

Since July 2025, the Free plan **closes your account** when credits run out or
after 6 months — your site and database would go with it.

Go to [Billing → Account plan](https://console.aws.amazon.com/billing/home#/account)
and switch to the **Paid plan**, adding a card. Your credits are still spent
first; you just don't get cut off when they run out.

---

## Step 2 — Create the server

1. Open [Lightsail](https://lightsail.aws.amazon.com/) → **Create instance**
2. **Region:** pick the one closest to your users
3. **Platform:** Linux/Unix → **Blueprint:** *OS Only* → **Ubuntu 24.04 LTS*
4. **Plan:** the **$12/mo** one (2 GB RAM, 2 vCPU, 60 GB SSD)
   — 1.3 GB is what the app actually uses, so the $5 and $7 plans are too small
5. **Name:** `huntops`
6. **Create instance** — ready in about a minute

### Give it a fixed IP

Instance → **Networking** tab → **Attach static IP** → create one → attach.

Do this before pointing DNS at it. Without a static IP the address changes when
the instance restarts, and your domain silently breaks. (Attached static IPs are
free; unattached ones are billed, so don't leave spares lying around.)

### Open the firewall

Same **Networking** tab → **IPv4 Firewall** → **Add rule**:

| Application | Port |
|---|---|
| HTTP | 80 |
| HTTPS | 443 |

SSH (22) is already open. **Do not open 5432** — Postgres stays internal.

---

## Step 3 — Point your domain at it

At your domain registrar, create an **A record** pointing to the static IP:

```
Type: A     Name: @  (or a subdomain like app)     Value: <your static IP>
```

Verify it resolves before continuing — Caddy requests your HTTPS certificate on
first boot and will fail if DNS isn't live yet:

```bash
dig +short yourdomain.com
```

DNS can take anywhere from a minute to an hour. Wait for it.

---

## Step 4 — Connect and prepare the server

In Lightsail, click **Connect using SSH** (browser terminal — no key setup
needed). Then:

```bash
sudo -i                                    # become root
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh     # Docker + Compose
```

**Add swap.** On a 2 GB box the frontend build will otherwise run out of memory:

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

---

## Step 5 — Get the code

```bash
git clone https://github.com/lilyfrancis/huntops.git /opt/huntops
cd /opt/huntops
cp .env.prod.example .env
cp backend/.env.example backend/.env
```

### Generate your secrets

Run this and keep the output — you'll paste these into the next step:

```bash
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32)"
echo "JWT_SECRET=$(openssl rand -hex 32)"
docker run --rm python:3.11-slim sh -c "pip install -q cryptography && python -c 'from cryptography.fernet import Fernet; print(\"TOKEN_ENCRYPTION_KEY=\" + Fernet.generate_key().decode())'"
```

⚠️ **Save `TOKEN_ENCRYPTION_KEY` somewhere safe.** If you lose it, every stored
Gmail connection becomes unreadable and users must reconnect.

### Fill in the two config files

```bash
nano .env
```

```
DOMAIN=yourdomain.com
TLS_EMAIL=you@yourdomain.com
POSTGRES_USER=huntops
POSTGRES_PASSWORD=<the generated one>
POSTGRES_DB=huntops
```

Save with `Ctrl+O`, `Enter`, then `Ctrl+X`.

```bash
nano backend/.env
```

Change these (leave `DATABASE_URL` alone — compose sets it):

```
ENVIRONMENT=production
JWT_SECRET=<generated>
TOKEN_ENCRYPTION_KEY=<generated>
CORS_ORIGINS=https://yourdomain.com
FRONTEND_URL=https://yourdomain.com
ANTHROPIC_API_KEY=sk-ant-...
```

Everything else can stay empty for now — the app runs without Stripe, Gmail,
and Apollo; those features simply stay off until you add their keys.

---

## Step 6 — Launch

```bash
cd /opt/huntops
docker compose -f docker-compose.prod.yml up -d --build
```

First build takes 3–5 minutes. Then check it:

```bash
docker compose -f docker-compose.prod.yml ps
```

You want `db`, `api`, `scheduler`, `web`, `caddy` all **running**, and `migrate`
**exited (0)** — that one is supposed to finish and stop.

**If `migrate` exited non-zero, stop and read its log** — nothing else will work:

```bash
docker compose -f docker-compose.prod.yml logs migrate
```

Now open **https://yourdomain.com**. You should get the landing page with a
valid certificate.

---

## Step 7 — Make yourself admin

Register through the site normally first, then:

```bash
cd /opt/huntops
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

Log out and back in — you'll land on the admin dashboard.

---

## Step 8 — Protect yourself

### Budget alert (2 minutes, prevents surprise bills)

[Billing → Budgets](https://console.aws.amazon.com/billing/home#/budgets) →
**Create budget** → Monthly cost budget → **$20** → email yourself at 80%.

### Nightly database backup

The database is the only thing you can't rebuild.

```bash
mkdir -p /root/backups
cat > /etc/cron.daily/huntops-backup << 'EOF'
#!/bin/bash
cd /opt/huntops
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U huntops huntops | gzip > /root/backups/huntops-$(date +%F).sql.gz
find /root/backups -name 'huntops-*.sql.gz' -mtime +14 -delete
EOF
chmod +x /etc/cron.daily/huntops-backup
/etc/cron.daily/huntops-backup && ls -lh /root/backups   # test it now
```

**Copy those off the server.** A backup living only on the machine it protects
is not a backup. Easiest option is a Lightsail snapshot on a schedule
(Instance → Snapshots → enable automatic snapshots, ~$0.05/GB-month).

---

## Everyday commands

```bash
cd /opt/huntops

docker compose -f docker-compose.prod.yml logs -f api      # watch API logs
docker compose -f docker-compose.prod.yml restart api      # restart the API
docker compose -f docker-compose.prod.yml ps               # what's running
free -h                                                     # memory check

git pull && docker compose -f docker-compose.prod.yml up -d --build   # deploy an update
```

Migrations run automatically on every update, before the new API starts.

---

## When something is wrong

| Symptom | Cause | Fix |
|---|---|---|
| Site won't load, no certificate | DNS not resolving when Caddy started | Fix the A record, then `docker compose -f docker-compose.prod.yml restart caddy` |
| `migrate` exited 1 | Migration failed | `logs migrate` — do not ignore this, the app will not work |
| Build killed / out of memory | Swap missing | Re-run the Step 4 swap commands |
| 502 from the site | API still starting or crashed | `logs api` |
| AI features error out | `ANTHROPIC_API_KEY` unset or invalid | Set it in `backend/.env`, then `up -d` |

---

## Before you take real users

- **Stripe, Gmail OAuth, Apollo and Anthropic have only ever run against
  mocks.** Do one real transaction through each before launch — especially the
  Stripe webhook (`https://yourdomain.com/api/billing/webhook`), because it is
  the only thing that can activate a paid subscription.
- There is **no CI and no committed end-to-end suite** — verification so far has
  been manual.
