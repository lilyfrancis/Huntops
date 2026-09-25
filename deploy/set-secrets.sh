#!/usr/bin/env bash
#
# Set the secrets and the pricing in backend/.env without the secrets
# touching shell history, the screen, or anyone's chat log.
#
# Pricing lives here too because it is the other thing that changes without
# a code change, and hand-editing a live .env under sudo is how a stray
# character takes the site down. Non-secret values are echoed as you type
# them — hiding a credit count helps nobody and makes typos likelier.
#
#   sudo bash deploy/set-secrets.sh
#
# Prompts for each value with the input hidden. Press Enter to leave one
# unchanged. Existing keys not listed here are preserved untouched.
#
# Safe to stop half way through with Ctrl-C: each answer is written as soon
# as you give it, so a second run picks up where you left off rather than
# starting from nothing.

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

SAVED=0
DONE=0

# Whether the run finished or was cut short, say what actually landed on
# disk. Walking away unsure which half of your keys are set is worse than
# either outcome on its own.
on_exit() {
  rm -f "$TMP"
  if [ "$SAVED" -eq 0 ]; then
    # Nothing changed, so the backup is a byte-for-byte copy. Leaving those
    # to pile up means a directory of files full of secrets.
    rm -f "$BACKUP"
    [ "$DONE" -eq 1 ] || { echo; echo "Stopped. Nothing was changed."; }
  elif [ "$DONE" -eq 0 ]; then
    echo
    echo "Stopped after $SAVED value(s). Those are saved in $ENV_FILE already;"
    echo "the prompts you did not reach are unchanged. Re-run to carry on."
  fi
}

KEYS=(
  ANTHROPIC_API_KEY
  SMTP_HOST SMTP_PORT SMTP_USERNAME SMTP_PASSWORD SMTP_FROM_EMAIL ADMIN_ALERT_EMAIL
  PAYSTACK_SECRET_KEY PAYSTACK_PLAN_PRO PAYSTACK_PLAN_ELITE BILLING_CURRENCY PRO_PRICE ELITE_PRICE
  FREE_TIER_CREDITS PRO_TIER_CREDITS ELITE_TIER_CREDITS
  CONCIERGE_CREDIT_COST UNLOCK_CREDIT_COST CREDIT_PACKS
  APOLLO_API_KEY
  WHATSAPP_API_BASE WHATSAPP_PHONE_NUMBER_ID WHATSAPP_ACCESS_TOKEN
  WHATSAPP_WABA_ID WHATSAPP_TEMPLATE_NAME WHATSAPP_TEMPLATE_LANGUAGE
  WHATSAPP_BUSINESS_NUMBER WHATSAPP_WEBHOOK_VERIFY_TOKEN WHATSAPP_APP_SECRET
)

# A few keys have a format that is not obvious from the name, and getting one
# wrong costs a morning of silence rather than an error. Shown with the prompt.
hint_for() {
  case "$1" in
    WHATSAPP_TEMPLATE_LANGUAGE)
      echo "Meta's language CODE, not the language's name — e.g. en or en_US" ;;
    WHATSAPP_BUSINESS_NUMBER)
      echo "the number users message to opt in, with country code — e.g. +12268010899" ;;
    WHATSAPP_API_BASE)
      echo "host only, no /vNN.N" ;;
    CREDIT_PACKS)
      echo "code:credits:price, comma separated" ;;
    *) echo "" ;;
  esac
}

# Rejected rather than stored: "English" here sends fine as far as this
# machine can tell, and Meta answers 132001 at 07:30 where nobody sees it.
is_valid() {
  case "$1" in
    WHATSAPP_TEMPLATE_LANGUAGE)
      printf '%s' "$2" | grep -qE '^[a-z]{2}(_[A-Z]{2})?$' ;;
    WHATSAPP_BUSINESS_NUMBER)
      printf '%s' "$2" | tr -d ' ()-' | grep -qE '^\+[1-9][0-9]{7,14}$' ;;
    *) return 0 ;;
  esac
}

# Values that are not secret are echoed while typing — hiding a port number
# helps nobody and makes typos likelier.
is_secret() {
  case "$1" in
    *KEY|*SECRET|*TOKEN|*PASSWORD) return 0 ;;
    *) return 1 ;;
  esac
}

TMP="$(mktemp)"
trap on_exit EXIT
cp "$ENV_FILE" "$TMP"

echo "Backed up to $BACKUP"
echo "Where things stand (names and lengths only, never values):"
for key in "${KEYS[@]}"; do
  existing="$(grep -E "^${key}=" "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  if [ -n "$existing" ]; then
    printf '  %-26s set\n' "$key"
  else
    printf '  %-26s -- empty\n' "$key"
  fi
done
echo
echo "Enter leaves a value alone. Ctrl-C is safe; answers are saved as you go."
echo

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

  hint="$(hint_for "$key")"
  [ -n "$hint" ] && printf '  # %s\n' "$hint"

  while :; do
    if is_secret "$key"; then
      printf '%s %s: ' "$key" "$shown"
      read -rs value
      echo
    else
      printf '%s %s: ' "$key" "$shown"
      read -r value
    fi
    [ -z "$value" ] && break
    if is_valid "$key" "$value"; then
      break
    fi
    echo "  that is not the expected format — $hint" >&2
  done

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

  # Written now, not at the end. Sixteen prompts is long enough that people
  # stop half way, and losing everything they typed is a poor reward.
  cat "$TMP" > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  SAVED=$((SAVED + 1))
done

DONE=1

echo
echo "Written. Which secrets are now set (names only, no values):"
grep -oE '^[A-Z_]+=.+' "$ENV_FILE" | cut -d= -f1 | sort | sed 's/^/  /'
echo
echo "Apply with:"
echo "  docker compose -f docker-compose.prod.yml up -d --build"
echo
echo "Then check Admin -> Integrations, which calls each provider for real."
