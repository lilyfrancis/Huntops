"""WhatsApp delivery via Meta's Cloud API.

Email open rates for a daily digest are poor in the markets this serves, and
in Nigeria and the Gulf WhatsApp is where people actually read things. A
digest nobody opens is the whole feature wasted.

One constraint shapes everything below: a message the business initiates —
which a daily digest always is — can only be sent from a **template approved
in advance by Meta**. Free-form text is allowed solely inside a 24-hour window
opened by the user messaging first, which never happens for a digest.

So this does not send the digest. It sends a short, templated nudge with the
counts and the top match, and the app is where the list lives. That is better
anyway: ten jobs in a WhatsApp message is unreadable.
"""

import logging
import re

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

GRAPH_VERSION = "v21.0"
HTTP_TIMEOUT = 20.0


class WhatsAppError(Exception):
    pass


_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def normalise_number(raw: str | None) -> str | None:
    """To E.164, or None if it cannot be made into one.

    People type "0803 123 4567" or "+234 803-123-4567". The API accepts only
    digits with a country code, and silently fails on anything else — so a
    number that cannot be normalised is rejected at entry rather than stored
    and discovered broken at 07:30.
    """
    if not raw:
        return None
    cleaned = re.sub(r"[\s\-().]", "", raw.strip())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if not cleaned.startswith("+"):
        return None
    return cleaned if _E164.match(cleaned) else None


def is_configured() -> bool:
    return bool(settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ACCESS_TOKEN)


def send_template(*, to: str, params: list[str]) -> bool:
    """Send the configured template. Returns whether Meta accepted it.

    Returns rather than raises: the digest run must not abandon everyone else
    because one number is unreachable.
    """
    if not is_configured():
        logger.info("WhatsApp not configured — skipping message to %s", to)
        return False

    number = normalise_number(to)
    if number is None:
        logger.warning("Not a valid E.164 number, skipping: %r", to)
        return False

    try:
        resp = httpx.post(
            f"https://graph.facebook.com/{GRAPH_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
            json={
                "messaging_product": "whatsapp",
                "to": number.lstrip("+"),
                "type": "template",
                "template": {
                    "name": settings.WHATSAPP_TEMPLATE_NAME,
                    "language": {"code": settings.WHATSAPP_TEMPLATE_LANGUAGE},
                    "components": [{
                        "type": "body",
                        "parameters": [{"type": "text", "text": p} for p in params],
                    }],
                },
            },
            timeout=HTTP_TIMEOUT,
        )
    except httpx.HTTPError as e:
        logger.error("WhatsApp request failed for %s: %s", number, e)
        return False

    if resp.status_code >= 400:
        # Meta's errors are specific and worth keeping whole — a template name
        # mismatch and an expired token look nothing alike in the response and
        # need completely different fixes.
        logger.error("WhatsApp rejected message to %s (%s): %s", number, resp.status_code, resp.text[:400])
        return False
    return True
