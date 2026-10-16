"""Turn the free-text salary strings our sources publish into numbers.

Every aggregation source hands us salary as prose — "$120,000–$150,000",
"£45k - £60k", "₦500,000 per month" — which is fine for display and useless for
comparison. This normalizes what it can into (min, max, currency, annualized)
and returns None for anything it can't read with confidence.

Deliberately conservative: a string it cannot parse cleanly yields nothing
rather than a guess. These numbers become salary benchmarks a candidate may
negotiate against, so a wrong parse is worse than a missing one.
"""

import re

# "$" is genuinely ambiguous (USD/CAD/AUD/NZD). We default it to USD and accept
# that; the alternative is dropping every "$" listing, which would gut the corpus.
_SYMBOLS = {"$": "USD", "£": "GBP", "€": "EUR", "₦": "NGN", "₹": "INR", "R$": "BRL"}
_CODES = {
    "USD", "GBP", "EUR", "NGN", "CAD", "AUD", "NZD", "INR", "ZAR", "KES",
    "GHS", "CHF", "SEK", "JPY", "SGD", "BRL",
    # Gulf and Egypt: the mailboxes cover these markets, and a listing whose
    # currency we fail to detect cannot be compared to a floor at all —
    # "AED 28,000 per month" was parsing its numbers and then storing them
    # against no currency, which is the same as not storing them.
    "AED", "SAR", "QAR", "EGP",
}

_HOURS_PER_YEAR = 2080  # 40h x 52w — the standard FTE convention
_MONTHS_PER_YEAR = 12

# "a month" is in here because it is what Indeed and Jobberman actually print
# — "₦400,000 - ₦600,000 a month". Without it the figure was read as annual,
# so a Lagos listing paying ₦600k a month was stored as ₦600k a year and
# compared against a floor twelve times too small. Wrong in the one direction
# that is invisible: the job still appears, with a plausible-looking number.
_PERIOD_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(per\s+hour|/\s*hour|hourly|/\s*hr|\bp/?h\b|\ban\s+hour\b)", re.I), "hour"),
    (re.compile(r"(per\s+month|/\s*month|monthly|/\s*mo\b|\bpcm\b|\ba\s+month\b)", re.I), "month"),
    (re.compile(r"(per\s+week|/\s*week|weekly|/\s*wk\b|\ba\s+week\b)", re.I), "week"),
    (re.compile(r"(per\s+day|/\s*day|daily|/\s*d\b|\ba\s+day\b)", re.I), "day"),
    (re.compile(r"(per\s+(year|annum)|/\s*year|annual(ly)?|\bpa\b|\bp\.a\.|\byr\b|"
                r"\ba\s+year\b|\ban\s+annum\b)", re.I), "year"),
]

# A number with optional thousands separators and an optional k/m suffix.
#
# The negative lookahead is the whole point of the second group. Without it
# the "m" of "monthly" was read as a millions suffix, so "₦250,000 monthly"
# parsed as two hundred and fifty billion naira, blew past the plausibility
# ceiling, and was discarded. The listing then had no salary at all and could
# not be filtered on — a silent failure, which is why it survived this long.
_NUMBER_RE = re.compile(r"(\d[\d,\. ]*\d|\d)\s*([km])?(?![a-z])", re.I)

_ANNUALIZE = {
    "year": 1.0,
    "month": float(_MONTHS_PER_YEAR),
    "week": 52.0,
    "day": 260.0,  # working days
    "hour": float(_HOURS_PER_YEAR),
}

# Below these an "annual" figure is almost certainly a different period that we
# misread, or a typo. Above the ceiling it's noise (a phone number, an ID).
#
# Per currency, because one global band of 1,000–10,000,000 was calibrated on
# dollars and silently deleted most of the emerging-market supply. ₦1.5m a
# month is an ordinary senior salary in Lagos; it annualises to ₦18m, which
# the old ceiling read as noise. Every Nigerian listing paying above about
# ₦833k a month therefore arrived with no salary on it, which is exactly the
# supply somebody filtering by amount most wants to compare.
#
# The ceilings stay well under a local phone number — eleven digits in Nigeria
# — since rejecting those is what the ceiling is for.
_PLAUSIBLE_ANNUAL: dict[str, tuple[float, float]] = {
    "NGN": (240_000, 500_000_000),
    "KES": (120_000, 200_000_000),
    "GHS": (6_000, 10_000_000),
    "ZAR": (24_000, 50_000_000),
    "INR": (60_000, 200_000_000),
    "JPY": (500_000, 500_000_000),
    "BRL": (12_000, 20_000_000),
    "SEK": (50_000, 50_000_000),
    "AED": (24_000, 20_000_000),
    "SAR": (24_000, 20_000_000),
    "QAR": (24_000, 20_000_000),
    "EGP": (60_000, 200_000_000),
}

# Used for the hard currencies and for a string that named no currency at all,
# where a wide band would let a reference number through as pay.
_DEFAULT_PLAUSIBLE_ANNUAL = (1_000, 10_000_000)


def _detect_currency(text: str) -> str | None:
    upper = text.upper()
    for code in _CODES:
        if re.search(rf"\b{code}\b", upper):
            return code
    for symbol, code in _SYMBOLS.items():
        if symbol in text:
            return code
    return None


def _detect_period(text: str) -> tuple[str, bool]:
    """Return (period, was_explicit). Unmarked listings are annual by convention."""
    for pattern, period in _PERIOD_PATTERNS:
        if pattern.search(text):
            return period, True
    return "year", False


def _to_number(raw: str, suffix: str | None) -> float | None:
    cleaned = raw.replace(",", "").replace(" ", "")
    # A trailing ".000"-style group is a thousands separator, not decimals.
    if re.fullmatch(r"\d+\.\d{3}", cleaned):
        cleaned = cleaned.replace(".", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None

    if suffix:
        value *= 1_000 if suffix.lower() == "k" else 1_000_000
    return value


def parse_salary(text: str | None) -> dict | None:
    """Parse a salary string into normalized annual figures.

    Returns {min, max, currency, period, annual_min, annual_max} or None.
    """
    if not text or not text.strip():
        return None

    currency = _detect_currency(text)
    period, explicit_period = _detect_period(text)

    numbers: list[float] = []
    scaled_or_grouped = False
    for raw, suffix in _NUMBER_RE.findall(text):
        value = _to_number(raw, suffix or None)
        if value is not None and value > 0:
            numbers.append(value)
            if suffix or "," in raw or "." in raw or " " in raw:
                scaled_or_grouped = True

    if not numbers:
        return None

    # Require some evidence the string is actually about money. Without it a
    # bare number reads as a salary when it is a year, a reference, or a
    # headcount — "Ref 2024 posting" must not become a $2,024 benchmark.
    if not (currency or explicit_period or scaled_or_grouped):
        return None

    low, high = min(numbers), max(numbers)

    factor = _ANNUALIZE[period]
    annual_min, annual_max = low * factor, high * factor

    # A parse that lands outside plausible annual pay means we misread the
    # string (picked up a year, a headcount, a percentage). Drop it.
    floor, ceiling = _PLAUSIBLE_ANNUAL.get(currency or "", _DEFAULT_PLAUSIBLE_ANNUAL)
    if not (floor <= annual_min <= ceiling):
        return None
    if not (floor <= annual_max <= ceiling):
        return None

    return {
        "min": low,
        "max": high,
        "currency": currency,
        "period": period,
        "annual_min": round(annual_min, 2),
        "annual_max": round(annual_max, 2),
    }
