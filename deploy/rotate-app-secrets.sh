#!/usr/bin/env bash
#
# Rotate the two secrets the application generates for itself, rather than
# ones a vendor issues: the JWT signing key and the mailbox-password
# encryption key.
#
#   sudo bash deploy/rotate-app-secrets.sh
#
# Both are generated here and written straight to backend/.env. Neither is
# ever printed, so neither ends up in scrollback, a screenshot or a chat log
# — which is the usual reason a key needs rotating in the first place.

set -euo pipefail

ENV_FILE="${1:-backend/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "No $ENV_FILE here. Run this from /opt/huntops." >&2
  exit 1
fi
if [ ! -w "$ENV_FILE" ]; then
  echo "$ENV_FILE is not writable — re-run with sudo." >&2
  exit 1
fi

BACKUP="${ENV_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$ENV_FILE" "$BACKUP"
chmod 600 "$BACKUP"
echo "Backed up to $BACKUP"
echo

write_key() {
  python3 - "$ENV_FILE" "$1" "$2" <<'PY'
import sys, pathlib
path, key, value = sys.argv[1], sys.argv[2], sys.argv[3]
p = pathlib.Path(path)
lines = p.read_text().splitlines()
out, done = [], False
for line in lines:
    if line.startswith(f"{key}=") and not done:
        out.append(f"{key}={value}")
        done = True
    else:
        out.append(line)
if not done:
    out.append(f"{key}={value}")
p.write_text("\n".join(out) + "\n")
PY
  chmod 600 "$ENV_FILE"
}

# ---------------------------------------------------------------- JWT_SECRET

echo "JWT_SECRET signs login sessions."
echo "Rotating it signs everyone out. Nothing is lost; they log in again."
read -rp "Rotate JWT_SECRET? [y/N] " reply
if [[ "$reply" =~ ^[Yy]$ ]]; then
  write_key JWT_SECRET "$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  echo "  Rotated."
else
  echo "  Left alone."
fi
echo

# ------------------------------------------------------- TOKEN_ENCRYPTION_KEY

echo "TOKEN_ENCRYPTION_KEY encrypts the stored IMAP passwords for the alert"
echo "mailboxes. Rotating it does NOT re-encrypt them: every mailbox already"
echo "saved becomes permanently unreadable and has to be re-entered by hand."
echo

# Better to count them than to ask someone to remember. A wrong answer here
# costs real work, and the number is two seconds away.
mailboxes=""
if command -v docker >/dev/null 2>&1 && [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
  mailboxes="$(docker compose -f docker-compose.prod.yml exec -T db \
      psql -U "${POSTGRES_USER:-huntops}" -d "${POSTGRES_DB:-huntops}" \
      -tAc 'select count(*) from alert_mailboxes' 2>/dev/null | tr -d '[:space:]' || true)"
fi

case "$mailboxes" in
  "")  echo "Could not reach the database to check how many mailboxes exist." ;;
  0)   echo "No mailboxes are saved yet — this is the free moment to rotate it." ;;
  *)   echo "WARNING: $mailboxes mailbox(es) are saved. Rotating now breaks all of"
       echo "them, and you will have to re-enter every IMAP password afterwards." ;;
esac

read -rp "Rotate TOKEN_ENCRYPTION_KEY? [y/N] " reply
if [[ "$reply" =~ ^[Yy]$ ]]; then
  # Fernet's key format exactly: 32 random bytes, urlsafe-base64.
  write_key TOKEN_ENCRYPTION_KEY "$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  echo "  Rotated."
  [ "${mailboxes:-0}" != "0" ] && [ -n "$mailboxes" ] && \
    echo "  Re-enter the IMAP password on each mailbox in Admin -> Mailboxes."
else
  echo "  Left alone."
fi

echo
echo "Apply with:"
echo "  docker compose -f docker-compose.prod.yml up -d"
