#!/usr/bin/env bash
#
# Set the secrets in backend/.env without them touching shell history,
# the screen, or anyone's chat log.
#
#   sudo bash deploy/set-secrets.sh
#
# Prompts for each value with the input hidden. Press Enter to leave one
# unchanged. Existing keys not listed here are preserved untouched.

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

# Backed up before anything is written. A fumbled secrets edit on a live box
# is a bad thing to have no way back from.
BACKUP="${ENV_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$ENV_FILE" "$BACKUP"
chmod 600 "$BACKUP"
echo "Backed up to $BACKUP"
echo

KEYS=(
  ANTHROPIC_API_KEY
  SMTP_HOST SMTP_PORT SMTP_USERNAME SMTP_PASSWORD SMTP_FROM_EMAIL ADMIN_ALERT_EMAIL
  PAYSTACK_SECRET_KEY PAYSTACK_PLAN_PRO PAYSTACK_PLAN_ELITE BILLING_CURRENCY PRO_PRICE ELITE_PRICE
  APOLLO_API_KEY
  WHATSAPP_PHONE_NUMBER_ID WHATSAPP_ACCESS_TOKEN WHATSAPP_TEMPLATE_NAME
)

# Values that are not secret are echoed while typing — hiding a port number
# helps nobody and makes typos likelier.
is_secret() {
  case "$1" in
    *KEY|*SECRET|*TOKEN|*PASSWORD) return 0 ;;
    *) return 1 ;;
  esac
}

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
cp "$ENV_FILE" "$TMP"

for key in "${KEYS[@]}"; do
  current="$(grep -E "^${key}=" "$TMP" | head -1 | cut -d= -f2- || true)"

  if [ -n "$current" ]; then
    if is_secret "$key"; then
      shown="(set, ${#current} chars)"
    else
      shown="($current)"
    fi
  else
    shown="(empty)"
  fi

  if is_secret "$key"; then
    printf '%s %s: ' "$key" "$shown"
    read -rs value
    echo
  else
    printf '%s %s: ' "$key" "$shown"
    read -r value
  fi

  [ -z "$value" ] && continue

  # A leading space silently becomes part of the value on some parsers, and
  # that failure is very hard to see in a text editor.
  value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

  if grep -qE "^${key}=" "$TMP"; then
    # Rewritten in python rather than sed: a key can contain / and & , which
    # sed would interpret as delimiters and backreferences.
    python3 - "$TMP" "$key" "$value" <<'PY'
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
p.write_text("\n".join(out) + "\n")
PY
  else
    printf '%s=%s\n' "$key" "$value" >> "$TMP"
  fi
done

cat "$TMP" > "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo
echo "Written. Which secrets are now set (names only, no values):"
grep -oE '^[A-Z_]+=.+' "$ENV_FILE" | cut -d= -f1 | sort | sed 's/^/  /'
echo
echo "Apply with:"
echo "  docker compose -f docker-compose.prod.yml up -d --build"
echo
echo "Then check Admin -> Integrations, which calls each provider for real."
